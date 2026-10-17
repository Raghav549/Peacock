"""The PEACOCK stack virtual machine.

This is an original bytecode interpreter for PEACOCK's own instruction set. It is
not a Python interpreter wrapper: PEACOCK programs are lexed, parsed, type
checked, lowered to PIR, optimised, lowered to PEACOCK bytecode, verified, and
executed here. Python objects are used as the current bootstrap runtime's value
representation, which is documented as a temporary implementation detail.

Security properties enforced here:
* capabilities declared by a bytecode function are checked against the host grant
  set before every capability-requiring native call;
* fs access is separately confined to a host sandbox root;
* instruction, call-depth and output budgets are enforced.

These are best-effort process-level controls, not a hardened multi-tenant sandbox.
See SECURITY.md.
"""

from __future__ import annotations

import io
import math
import sys
import time
from dataclasses import dataclass, field

from peacock.compiler import builtins as B
from peacock.compiler.bytecode import BytecodeError, verify_image
from peacock.compiler.diagnostics import (
    CapabilityError,
    PeacockError,
    PanicError,
    ResourceLimitError,
    RuntimeError_,
)
from peacock.intelligence import tensor as TI
from peacock.intelligence.datasets import Dataset
from peacock.intelligence.layers import Model, build_model
from peacock.intelligence.training import evaluate_accuracy, train_model

from .artifact import ArtifactFormatError
from .errors import VMFault, add_trace
from .host import HostPolicy
from .native import (
    NativeContext,
    call_method,
    call_native,
    get_property,
    method_capability,
    native_capability,
)
from .values import UNIT, RangeValue, StructInstance, format_value, is_int

INT_MIN = -(2**63)
INT_MAX = 2**63 - 1


@dataclass
class Handler:
    start: int
    end: int
    target: int
    stack_len: int


@dataclass
class Frame:
    name: str
    code: list
    lines: list
    slots: list
    stack: list = field(default_factory=list)
    pc: int = 0
    handlers: list[Handler] = field(default_factory=list)
    caps: frozenset[str] = frozenset()
    pending_error: str | None = None


@dataclass
class ExecutionResult:
    value: object
    steps: int
    elapsed_seconds: float
    output_chars: int
    calls: int


def _checked_int(value: int, what: str) -> int:
    if not (INT_MIN <= value <= INT_MAX):
        raise VMFault(f"integer overflow in {what}", "PE4004")
    return value


class VM:
    def __init__(
        self,
        image: dict,
        host: HostPolicy | None = None,
        stdout=None,
        stderr=None,
        argv: list[str] | None = None,
    ):
        try:
            verify_image(image)
        except BytecodeError as exc:
            raise ArtifactFormatError(str(exc)) from exc
        self.image = image
        self.host = host or HostPolicy()
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stderr = stderr if stderr is not None else sys.stderr
        self.argv = list(argv or [])
        self.functions: dict = image["functions"]
        self.structs: dict = image.get("structs", {})
        self.models: dict = image.get("models", {})
        self.trainings: dict = image.get("trainings", {})
        self.steps = 0
        self.calls = 0
        self.depth = 0
        self.output_chars = 0
        self.last_training_report = None
        self._ctx = NativeContext(self, self.host)

    # -- public API --------------------------------------------------------
    def write_output(self, text: str) -> None:
        if not isinstance(text, str):
            raise VMFault("output must be a String", "PE4999")
        if self.output_chars + len(text) > self.host.max_output_chars:
            raise ResourceLimitError(
                f"program exceeded the host output limit of {self.host.max_output_chars} characters",
                "PE4003",
            )
        self.output_chars += len(text)
        self.stdout.write(text)

    def run(self, entry: str = "main") -> ExecutionResult:
        if entry not in self.functions:
            raise VMFault(
                f"program has no '{entry}' function; a runnable PEACOCK program must define main() -> Unit",
                "PE4002",
            )
        fn = self.functions[entry]
        if fn["arity"] != 0:
            raise VMFault(f"entry function '{entry}' must take no parameters", "PE4002")
        self.steps = 0
        self.calls = 0
        self.depth = 0
        started = time.perf_counter()
        value = self._call_function(entry, [])
        elapsed = time.perf_counter() - started
        return ExecutionResult(value, self.steps, elapsed, self.output_chars, self.calls)

    # -- calls & execution -------------------------------------------------
    def _call_function(self, name: str, args: list):
        if self.depth >= self.host.max_call_depth:
            raise ResourceLimitError(
                f"call depth exceeded the host limit of {self.host.max_call_depth}",
                "PE4003",
            )
        fn = self.functions.get(name)
        if fn is None:
            raise VMFault(f"call to unknown function '{name}'", "PE4999")
        arity = fn["arity"]
        if len(args) != arity:
            raise VMFault(
                f"function '{name}' expects {arity} argument(s), got {len(args)}", "PE4999"
            )
        slots: list = [None] * fn["slots"]
        slots[:arity] = args
        frame = Frame(
            name=name,
            code=fn["code"],
            lines=fn["lines"],
            slots=slots,
            caps=frozenset(fn.get("caps", ())),
        )
        self.calls += 1
        self.depth += 1
        try:
            return self._execute(frame)
        finally:
            self.depth -= 1

    def _pop_args(self, stack: list, count: int) -> list:
        if count < 0 or count > len(stack):
            raise VMFault("bytecode stack underflow", "PE4999")
        if count == 0:
            return []
        args = stack[-count:]
        del stack[-count:]
        return args

    def _execute(self, frame: Frame):
        while True:
            if frame.pc < 0 or frame.pc >= len(frame.code):
                raise VMFault(f"instruction pointer escaped function '{frame.name}'", "PE4999")
            ip = frame.pc
            instr = frame.code[ip]
            frame.pc += 1
            self.steps += 1
            if self.steps > self.host.max_steps:
                raise ResourceLimitError(
                    f"program exceeded the host step limit of {self.host.max_steps}",
                    "PE4003",
                )
            try:
                returned, value = self._dispatch(frame, instr, ip)
                if returned:
                    return value
            except (PanicError, ResourceLimitError):
                raise
            except PeacockError as exc:
                line, column = frame.lines[ip] if ip < len(frame.lines) else (0, 0)
                add_trace(exc, frame.name, line, column)
                handled = self._handle_exception(frame, ip, exc)
                if not handled:
                    raise

    def _dispatch(self, frame: Frame, instr: list, ip: int):
        op = instr[0]
        stack = frame.stack
        if op == "PUSH_CONST":
            stack.append(instr[1])
        elif op == "PUSH_SLOT":
            slot = instr[1]
            value = frame.slots[slot]
            if value is None:
                raise VMFault("read of an uninitialised local variable", "PE4002")
            stack.append(value)
        elif op == "STORE_SLOT":
            if not stack:
                raise VMFault("stack underflow in STORE_SLOT", "PE4999")
            frame.slots[instr[1]] = stack.pop()
        elif op == "POP":
            if not stack:
                raise VMFault("stack underflow in POP", "PE4999")
            stack.pop()
        elif op == "BINOP":
            if len(stack) < 2:
                raise VMFault("stack underflow in BINOP", "PE4999")
            b = stack.pop()
            a = stack.pop()
            stack.append(self._eval_binary(instr[1], a, b))
        elif op == "UNOP":
            if not stack:
                raise VMFault("stack underflow in UNOP", "PE4999")
            stack.append(self._eval_unary(instr[1], stack.pop()))
        elif op == "CALL":
            args = self._pop_args(stack, instr[2])
            stack.append(self._call_function(instr[1], args))
        elif op == "CALL_NATIVE":
            name = instr[1]
            cap = native_capability(name)
            if cap is not None:
                self._require_capability(frame, cap, f"native function '{name}'")
            args = self._pop_args(stack, instr[2])
            stack.append(call_native(self._ctx, name, args))
        elif op == "METHOD":
            name = instr[1]
            cap = method_capability(name)
            if cap is not None:
                self._require_capability(frame, cap, f"method '{name}'")
            args = self._pop_args(stack, instr[2])
            if not args:
                raise VMFault("method call has no receiver", "PE4999")
            receiver = args[0]
            stack.append(call_method(self._ctx, receiver, name, args[1:]))
        elif op == "MODEL_INIT":
            self._require_capability(frame, "compute", f"model initialisation '{instr[1]}'")
            args = self._pop_args(stack, instr[2])
            stack.append(self._model_init(instr[1], args))
        elif op == "TRAINING_METHOD":
            self._require_capability(frame, "compute", f"training method '{instr[2]}'")
            args = self._pop_args(stack, instr[3])
            stack.append(self._training_method(instr[1], instr[2], args))
        elif op == "STRUCT_NEW":
            name = instr[1]
            fields = self.structs.get(name)
            if fields is None:
                raise VMFault(f"unknown struct '{name}'", "PE4999")
            args = self._pop_args(stack, instr[2])
            if len(args) != len(fields):
                raise VMFault(f"struct '{name}' expects {len(fields)} fields", "PE4999")
            stack.append(StructInstance(name, list(fields), dict(zip(fields, args))))
        elif op == "FIELD_GET":
            if not stack:
                raise VMFault("stack underflow in FIELD_GET", "PE4999")
            base = stack.pop()
            name, kind = instr[1], instr[2]
            if kind == "property":
                stack.append(get_property(self._ctx, base, name))
            else:
                if not isinstance(base, StructInstance):
                    raise VMFault(f"cannot read field '{name}' of {type(base).__name__}", "PE4002")
                try:
                    stack.append(base.get(name))
                except KeyError:
                    raise VMFault(f"struct '{base.type_name}' has no field '{name}'", "PE4002")
        elif op == "FIELD_SET":
            if len(stack) < 2:
                raise VMFault("stack underflow in FIELD_SET", "PE4999")
            value = stack.pop()
            base = stack.pop()
            if not isinstance(base, StructInstance):
                raise VMFault(f"cannot set field '{instr[1]}' of {type(base).__name__}", "PE4002")
            try:
                base.set(instr[1], value)
            except KeyError:
                raise VMFault(f"struct '{base.type_name}' has no field '{instr[1]}'", "PE4002")
        elif op == "INDEX_GET":
            if len(stack) < 2:
                raise VMFault("stack underflow in INDEX_GET", "PE4999")
            index = stack.pop()
            base = stack.pop()
            if not is_int(index):
                raise VMFault("index must be an Int", "PE4002")
            if isinstance(base, (list, str)):
                if not (0 <= index < len(base)):
                    raise VMFault(
                        f"index {index} out of bounds for {type(base).__name__} of length {len(base)}",
                        "PE4002",
                    )
                stack.append(base[index])
            else:
                raise VMFault(f"cannot index {type(base).__name__}", "PE4002")
        elif op == "INDEX_SET":
            if len(stack) < 3:
                raise VMFault("stack underflow in INDEX_SET", "PE4999")
            value = stack.pop()
            index = stack.pop()
            base = stack.pop()
            if not is_int(index):
                raise VMFault("index must be an Int", "PE4002")
            if not isinstance(base, list):
                raise VMFault(f"cannot assign through an index of {type(base).__name__}", "PE4002")
            if not (0 <= index < len(base)):
                raise VMFault(
                    f"index {index} out of bounds for List of length {len(base)}", "PE4002"
                )
            base[index] = value
        elif op == "MAKE_LIST":
            elements = self._pop_args(stack, instr[1])
            stack.append(elements)
        elif op == "MAKE_RANGE":
            if len(stack) < 2:
                raise VMFault("stack underflow in MAKE_RANGE", "PE4999")
            end = stack.pop()
            start = stack.pop()
            if not is_int(start) or not is_int(end):
                raise VMFault("range bounds must be Int", "PE4002")
            stack.append(RangeValue(start, end))
        elif op == "LEN":
            if not stack:
                raise VMFault("stack underflow in LEN", "PE4999")
            value = stack.pop()
            if isinstance(value, (list, str)):
                stack.append(len(value))
            elif isinstance(value, TI.Tensor):
                stack.append(value.size)
            elif isinstance(value, RangeValue):
                stack.append(len(value))
            elif isinstance(value, Dataset):
                stack.append(len(value))
            else:
                raise VMFault(f"len() is not defined for {type(value).__name__}", "PE4002")
        elif op == "ASSERT":
            if len(stack) < 2:
                raise VMFault("stack underflow in ASSERT", "PE4999")
            message = stack.pop()
            condition = stack.pop()
            if condition is not True:
                text = message if isinstance(message, str) else "assertion failed"
                raise VMFault(text, "PE4010")
        elif op == "THROW":
            if not stack:
                raise VMFault("stack underflow in THROW", "PE4999")
            message = stack.pop()
            if not isinstance(message, str):
                raise VMFault("throw requires a String message", "PE4002")
            raise VMFault(message, "PE4020")
        elif op == "JUMP":
            target = instr[1]
            self._prune_handlers(frame, target)
            frame.pc = target
        elif op == "JUMP_IF_FALSE":
            if not stack:
                raise VMFault("stack underflow in JUMP_IF_FALSE", "PE4999")
            condition = stack.pop()
            if not isinstance(condition, bool):
                raise VMFault("branch condition must be Bool", "PE4002")
            if not condition:
                target = instr[1]
                self._prune_handlers(frame, target)
                frame.pc = target
        elif op == "TRY_BEGIN":
            target, end = instr[1], instr[2]
            if end < frame.pc:
                raise VMFault("invalid try region", "PE4999")
            frame.handlers.append(Handler(frame.pc, end, target, len(stack)))
        elif op == "TRY_END":
            if frame.handlers:
                frame.handlers.pop()
        elif op == "CATCH":
            if frame.pending_error is None:
                raise VMFault("CATCH executed without a pending error", "PE4999")
            stack.append(frame.pending_error)
            frame.pending_error = None
        elif op == "RET":
            if instr[1]:
                if not stack:
                    raise VMFault("stack underflow in RET", "PE4999")
                return True, stack.pop()
            return True, UNIT
        elif op == "NOP":
            pass
        else:
            raise VMFault(f"unknown opcode '{op}'", "PE4999")
        return False, None

    # -- exception handling ------------------------------------------------
    def _find_handler(self, frame: Frame, ip: int):
        for index in range(len(frame.handlers) - 1, -1, -1):
            handler = frame.handlers[index]
            if handler.start <= ip < handler.end:
                return index, handler
        return None, None

    def _handle_exception(self, frame: Frame, ip: int, exc: PeacockError) -> bool:
        index, handler = self._find_handler(frame, ip)
        if handler is None:
            return False
        del frame.handlers[index:]
        frame.stack = frame.stack[: handler.stack_len]
        frame.pending_error = exc.message
        frame.pc = handler.target
        return True

    def _prune_handlers(self, frame: Frame, target: int) -> None:
        frame.handlers = [
            h for h in frame.handlers if h.start <= target < h.end
        ]

    # -- capabilities ------------------------------------------------------
    def _require_capability(self, frame: Frame, capability: str, what: str) -> None:
        if capability not in frame.caps:
            raise CapabilityError(
                f"{what} requires capability '{capability}', but function '{frame.name}' does not declare it",
                "PE4001",
            )
        if capability not in self.host.grants:
            raise CapabilityError(
                f"host has not granted capability '{capability}' required by {what}",
                "PE4001",
            )

    # -- runtime operations ------------------------------------------------
    def _model_init(self, name: str, args: list):
        spec = self.models.get(name)
        if spec is None:
            raise VMFault(f"unknown model '{name}'", "PE4999")
        if len(args) != 1 or not is_int(args[0]):
            raise VMFault("model.init expects an Int seed", "PE4002")
        try:
            model = build_model(
                spec["input_shape"],
                spec["output_shape"],
                spec["layers"],
                seed=args[0],
            )
        except Exception as exc:
            if isinstance(exc, PeacockError):
                raise
            raise VMFault(f"cannot build model '{name}': {exc}", "PE6001") from exc
        if model.parameter_count > self.host.max_tensor_elements:
            raise ResourceLimitError("model exceeds the host parameter limit", "PE4003")
        return model

    def _training_method(self, name: str, method: str, args: list):
        config = self.trainings.get(name)
        if config is None:
            raise VMFault(f"unknown training declaration '{name}'", "PE4999")
        if len(args) != 2:
            raise VMFault(f"training.{method} expects (model, dataset)", "PE4002")
        model, dataset = args
        if not isinstance(model, Model):
            raise VMFault("training method expects a Model", "PE4002")
        if not isinstance(dataset, Dataset):
            raise VMFault("training method expects a Dataset", "PE4002")
        if len(dataset) > self.host.max_dataset_samples:
            raise ResourceLimitError("dataset exceeds the host sample limit", "PE4003")
        epochs = int(config.get("epochs", 10))
        if epochs > self.host.max_training_epochs:
            raise ResourceLimitError(
                f"training epochs exceed the host limit of {self.host.max_training_epochs}",
                "PE4003",
            )
        try:
            if method == "run":
                report = train_model(
                    model,
                    dataset,
                    objective=str(config.get("objective", "cross_entropy")),
                    optimiser=str(config.get("optimiser", "adam")),
                    epochs=epochs,
                    learning_rate=float(config.get("learning_rate", 0.01)),
                    batch_size=int(config.get("batch_size", 16)),
                    seed=int(config.get("seed", 0)),
                )
                self.last_training_report = report
                return list(report.losses)
            if method == "evaluate":
                return evaluate_accuracy(model, dataset)
        except Exception as exc:
            if isinstance(exc, PeacockError):
                raise
            raise VMFault(str(exc), "PE6001") from exc
        raise VMFault(f"unknown training method '{method}'", "PE4999")

    # -- arithmetic & comparison ------------------------------------------
    def _eval_unary(self, op: str, a):
        if op == "not":
            if not isinstance(a, bool):
                raise VMFault("'not' requires Bool", "PE4006")
            return not a
        if op == "-":
            if is_int(a):
                return _checked_int(-a, "unary minus")
            if isinstance(a, float):
                return -a
            if isinstance(a, TI.Tensor):
                return TI.negative(a)
        raise VMFault(f"unary '{op}' is not defined for {type(a).__name__}", "PE4006")

    def _tensor_binary(self, op: str, a, b):
        try:
            if op == "**":
                exponent = b
                if isinstance(exponent, TI.Tensor):
                    if exponent.size != 1:
                        raise VMFault("tensor exponent must be a scalar", "PE6001")
                    exponent = exponent.item()
                return TI.power(a, exponent)
            if op == "+":
                return TI.add(a, b)
            if op == "-":
                return TI.sub(a, b)
            if op == "*":
                return TI.mul(a, b)
            if op == "/":
                return TI.divide(a, b)
        except TI.TensorError as exc:
            raise VMFault(str(exc), "PE6001") from exc
        raise VMFault(f"operator '{op}' is not defined for tensors", "PE4006")

    def _eval_binary(self, op: str, a, b):
        if isinstance(a, TI.Tensor) or isinstance(b, TI.Tensor):
            return self._tensor_binary(op, a, b)
        if op in ("and", "or"):
            if not isinstance(a, bool) or not isinstance(b, bool):
                raise VMFault(f"'{op}' requires Bool operands", "PE4006")
            return (a and b) if op == "and" else (a or b)
        if op in ("==", "!="):
            if type(a) is not type(b):
                raise VMFault(
                    f"cannot compare {type(a).__name__} with {type(b).__name__}", "PE4006"
                )
            if not isinstance(a, (bool, int, float, str)):
                raise VMFault(f"equality is not defined for {type(a).__name__}", "PE4006")
            return (a == b) if op == "==" else (a != b)
        if op in ("<", "<=", ">", ">="):
            if type(a) is not type(b) or not isinstance(a, (int, float, str)):
                raise VMFault(
                    f"ordering comparison '{op}' requires two Ints, two Floats or two Strings",
                    "PE4006",
                )
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            return a >= b
        if op == "+" and isinstance(a, str) and isinstance(b, str):
            return a + b
        if is_int(a) and is_int(b):
            if op == "+":
                return _checked_int(a + b, "addition")
            if op == "-":
                return _checked_int(a - b, "subtraction")
            if op == "*":
                return _checked_int(a * b, "multiplication")
            if op == "/":
                if b == 0:
                    raise VMFault("division by zero", "PE4005")
                q = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    q = -q
                return _checked_int(q, "division")
            if op == "%":
                if b == 0:
                    raise VMFault("remainder by zero", "PE4005")
                q = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    q = -q
                return _checked_int(a - q * b, "remainder")
            if op == "**":
                if b < 0:
                    raise VMFault("integer exponent must be non-negative", "PE4004")
                if b > 63 and abs(a) > 1:
                    raise VMFault("integer overflow in exponentiation", "PE4004")
                return _checked_int(a**b, "exponentiation")
        if isinstance(a, float) and isinstance(b, float):
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0.0:
                    raise VMFault("float division by zero", "PE4005")
                return a / b
            if op == "**":
                try:
                    result = math.pow(a, b)
                except (ValueError, OverflowError) as exc:
                    raise VMFault(f"float exponentiation: {exc}", "PE4004") from exc
                return result
        if isinstance(a, str) and isinstance(b, str):
            raise VMFault(f"operator '{op}' is not defined for two Strings", "PE4006")
        raise VMFault(
            f"operator '{op}' is not defined for {type(a).__name__} and {type(b).__name__}",
            "PE4006",
        )
