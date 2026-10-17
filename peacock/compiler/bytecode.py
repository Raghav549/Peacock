"""Lower PIR to PEACOCK bytecode and validate the resulting program image.

The bytecode is a stack machine with named functions, numbered local slots and
relative-free absolute jump targets. It is the unit of execution for the
original PEACOCK VM (``peacock/runtime/vm.py``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from peacock import __version__

from . import builtins as B
from .ir import IRFunction, IRModule
from .tokens import KNOWN_CAPABILITIES
from .types import UnitType


class BytecodeError(Exception):
    pass


#: Opcode -> (minimum args, maximum args). Arguments are positional and typed.
OPCODES: dict[str, tuple[int, int]] = {
    "PUSH_CONST": (1, 1),
    "PUSH_SLOT": (1, 1),
    "STORE_SLOT": (1, 1),
    "POP": (0, 0),
    "BINOP": (1, 1),
    "UNOP": (1, 1),
    "CALL": (2, 2),
    "CALL_NATIVE": (2, 2),
    "METHOD": (2, 2),
    "MODEL_INIT": (2, 2),
    "TRAINING_METHOD": (3, 3),
    "STRUCT_NEW": (2, 2),
    "FIELD_GET": (2, 2),
    "FIELD_SET": (1, 1),
    "INDEX_GET": (0, 0),
    "INDEX_SET": (0, 0),
    "MAKE_LIST": (1, 1),
    "MAKE_RANGE": (0, 0),
    "LEN": (0, 0),
    "ASSERT": (1, 1),
    "THROW": (0, 0),
    "JUMP": (1, 1),
    "JUMP_IF_FALSE": (1, 1),
    "RET": (1, 1),
    "TRY_BEGIN": (2, 2),
    "TRY_END": (0, 0),
    "CATCH": (0, 0),
    "NOP": (0, 0),
}

_BINOPS = {"+", "-", "*", "/", "%", "**", "==", "!=", "<", "<=", ">", ">="}
_UNOPS = {"-", "not"}


@dataclass
class BytecodeResult:
    image: dict[str, Any]
    instruction_count: int


class BytecodeCompiler:
    def __init__(self, module: IRModule):
        self.module = module
        self.instruction_count = 0

    def compile(self) -> BytecodeResult:
        functions = {}
        for name, fn in self.module.functions.items():
            functions[name] = self.compile_function(fn)
        models = {
            name: {
                "input_dtype": spec.input_dtype,
                "input_shape": list(spec.input_shape),
                "output_dtype": spec.output_dtype,
                "output_shape": list(spec.output_shape),
                "layers": [[units, activation] for units, activation in spec.layers],
            }
            for name, spec in self.module.models.items()
        }
        image = {
            "format": "peacock-bytecode",
            "format_version": 1,
            "language_version": "0.1",
            "compiler_version": __version__,
            "module": self.module.name or "",
            "uses": list(self.module.uses),
            "source_path": self.module.source_path,
            "source_sha256": hashlib.sha256(self.module.source.encode("utf-8")).hexdigest(),
            "functions": functions,
            "structs": {name: list(fields) for name, fields in self.module.structs.items()},
            "models": models,
            "trainings": self.module.trainings,
        }
        verify_image(image)
        return BytecodeResult(image, self.instruction_count)

    def compile_function(self, fn: IRFunction) -> dict[str, Any]:
        code: list[list[Any]] = []
        lines: list[list[int]] = []
        labels: dict[str, int] = {}
        patches: list[tuple[int, int, str]] = []  # (instruction index, arg index, label)
        try_stack: list[tuple[int, str]] = []  # (TRY_BEGIN index, catch label)

        def emit(instr: list[Any], span) -> int:
            code.append(instr)
            lines.append([span.line, span.column] if span else [0, 0])
            self.instruction_count += 1
            return len(code) - 1

        for instr in fn.instrs:
            op = instr.op
            span = instr.span
            if op == "label":
                labels[instr.args[0]] = len(code)
                continue
            if op == "const":
                emit(["PUSH_CONST", instr.args[0]], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "slot_get":
                emit(["PUSH_SLOT", instr.args[0]], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "slot_set":
                emit(["PUSH_SLOT", instr.args[1]], span)
                emit(["STORE_SLOT", instr.args[0]], span)
            elif op == "move":
                emit(["PUSH_SLOT", instr.args[0]], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "binop":
                binop, a, b = instr.args
                emit(["PUSH_SLOT", a], span)
                emit(["PUSH_SLOT", b], span)
                emit(["BINOP", binop], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "unop":
                unop, a = instr.args
                emit(["PUSH_SLOT", a], span)
                emit(["UNOP", unop], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "call":
                name, regs = instr.args
                for r in regs:
                    emit(["PUSH_SLOT", r], span)
                emit(["CALL", name, len(regs)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "call_native":
                name, regs = instr.args
                for r in regs:
                    emit(["PUSH_SLOT", r], span)
                emit(["CALL_NATIVE", name, len(regs)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "method":
                method, receiver, regs = instr.args
                emit(["PUSH_SLOT", receiver], span)
                for r in regs:
                    emit(["PUSH_SLOT", r], span)
                emit(["METHOD", method, 1 + len(regs)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "model_init":
                name, regs = instr.args
                for r in regs:
                    emit(["PUSH_SLOT", r], span)
                emit(["MODEL_INIT", name, len(regs)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "training_method":
                name, method, regs = instr.args
                for r in regs:
                    emit(["PUSH_SLOT", r], span)
                emit(["TRAINING_METHOD", name, method, len(regs)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "struct_new":
                name, regs = instr.args
                for r in regs:
                    emit(["PUSH_SLOT", r], span)
                emit(["STRUCT_NEW", name, len(regs)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "field_get":
                base, field, kind = instr.args
                emit(["PUSH_SLOT", base], span)
                emit(["FIELD_GET", field, kind], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "field_set":
                base, field, value = instr.args
                emit(["PUSH_SLOT", base], span)
                emit(["PUSH_SLOT", value], span)
                emit(["FIELD_SET", field], span)
            elif op == "index_get":
                base, index = instr.args
                emit(["PUSH_SLOT", base], span)
                emit(["PUSH_SLOT", index], span)
                emit(["INDEX_GET"], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "index_set":
                base, index, value = instr.args
                emit(["PUSH_SLOT", base], span)
                emit(["PUSH_SLOT", index], span)
                emit(["PUSH_SLOT", value], span)
                emit(["INDEX_SET"], span)
            elif op == "make_list":
                for r in instr.args:
                    emit(["PUSH_SLOT", r], span)
                emit(["MAKE_LIST", len(instr.args)], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "make_range":
                emit(["PUSH_SLOT", instr.args[0]], span)
                emit(["PUSH_SLOT", instr.args[1]], span)
                emit(["MAKE_RANGE"], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "len":
                emit(["PUSH_SLOT", instr.args[0]], span)
                emit(["LEN"], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "assert":
                cond, msg = instr.args
                emit(["PUSH_SLOT", cond], span)
                if msg is not None:
                    emit(["PUSH_SLOT", msg], span)
                else:
                    emit(["PUSH_CONST", None], span)
                emit(["ASSERT", 1 if msg is not None else 0], span)
            elif op == "throw":
                emit(["PUSH_SLOT", instr.args[0]], span)
                emit(["THROW"], span)
            elif op == "jump":
                idx = emit(["JUMP", "@"], span)
                patches.append((idx, 1, instr.args[0]))
            elif op == "branch":
                cond, true_label, false_label = instr.args
                emit(["PUSH_SLOT", cond], span)
                idx = emit(["JUMP_IF_FALSE", "@"], span)
                patches.append((idx, 1, false_label))
                idx2 = emit(["JUMP", "@"], span)
                patches.append((idx2, 1, true_label))
            elif op == "return":
                value = instr.args[0]
                if value is not None:
                    emit(["PUSH_SLOT", value], span)
                    emit(["RET", 1], span)
                else:
                    emit(["RET", 0], span)
            elif op == "try_begin":
                idx = emit(["TRY_BEGIN", "@", -1], span)
                catch_label = instr.args[0]
                patches.append((idx, 1, catch_label))
                try_stack.append((idx, catch_label))
            elif op == "try_end":
                if not try_stack:
                    raise BytecodeError("try_end without try_begin in IR")
                begin_idx, _ = try_stack.pop()
                code[begin_idx][2] = len(code)
                emit(["TRY_END"], span)
            elif op == "catch":
                emit(["CATCH"], span)
                emit(["STORE_SLOT", instr.dest], span)
            elif op == "nop":
                emit(["NOP"], span)
            else:
                raise BytecodeError(f"unknown IR op '{op}' while lowering")

        while patches:
            idx, argi, label = patches.pop()
            if label not in labels:
                raise BytecodeError(f"unknown label '{label}'")
            code[idx][argi] = labels[label]
        if try_stack:
            raise BytecodeError("unclosed try_begin while lowering")
        if not code:
            code.append(["RET", 0])
            lines.append([0, 0])

        return {
            "arity": len(fn.decl.params),
            "slots": fn.slot_count,
            "caps": sorted(fn.capabilities),
            "return_type": fn.return_type.display(),
            "params": [p.name for p in fn.decl.params],
            "code": code,
            "lines": lines,
        }


def compile_bytecode(module: IRModule) -> BytecodeResult:
    return BytecodeCompiler(module).compile()


def verify_image(image: dict[str, Any]) -> None:
    """Validate a bytecode program image; raises BytecodeError on invalid input."""
    if not isinstance(image, dict):
        raise BytecodeError("program image must be an object")
    for key in (
        "format",
        "format_version",
        "language_version",
        "compiler_version",
        "functions",
        "structs",
        "models",
        "trainings",
    ):
        if key not in image:
            raise BytecodeError(f"program image is missing '{key}'")
    if image["format"] != "peacock-bytecode":
        raise BytecodeError("not a PEACOCK bytecode image")
    if image["format_version"] != 1:
        raise BytecodeError(f"unsupported bytecode format version {image['format_version']}")
    functions = image["functions"]
    if not isinstance(functions, dict) or not functions:
        raise BytecodeError("program image has no functions")
    models = set(image["models"]) if isinstance(image["models"], dict) else set()
    trainings = set(image["trainings"]) if isinstance(image["trainings"], dict) else set()
    structs = image["structs"] if isinstance(image["structs"], dict) else {}
    for name, fn in functions.items():
        if not isinstance(fn, dict):
            raise BytecodeError(f"function '{name}' is not an object")
        for key in ("arity", "slots", "caps", "code", "lines"):
            if key not in fn:
                raise BytecodeError(f"function '{name}' is missing '{key}'")
        arity = fn["arity"]
        slots = fn["slots"]
        if not isinstance(arity, int) or arity < 0:
            raise BytecodeError(f"function '{name}' has invalid arity")
        if not isinstance(slots, int) or slots < arity or slots > 65536:
            raise BytecodeError(f"function '{name}' has invalid slot count")
        if not isinstance(fn["caps"], list) or any(
            cap not in KNOWN_CAPABILITIES for cap in fn["caps"]
        ):
            raise BytecodeError(f"function '{name}' declares unknown capabilities")
        code = fn["code"]
        lines = fn["lines"]
        if not isinstance(code, list) or not code:
            raise BytecodeError(f"function '{name}' has no code")
        if not isinstance(lines, list) or len(lines) != len(code):
            raise BytecodeError(f"function '{name}' line table does not match code length")
        for ip, instr in enumerate(code):
            if not isinstance(instr, list) or not instr:
                raise BytecodeError(f"function '{name}' instruction {ip} is malformed")
            op = instr[0]
            if op not in OPCODES:
                raise BytecodeError(f"function '{name}' uses unknown opcode '{op}'")
            lo, hi = OPCODES[op]
            if not (lo <= len(instr) - 1 <= hi):
                raise BytecodeError(
                    f"function '{name}' instruction {ip} ('{op}') has wrong argument count"
                )
            if op in ("PUSH_SLOT", "STORE_SLOT"):
                slot = instr[1]
                if not isinstance(slot, int) or not (0 <= slot < slots):
                    raise BytecodeError(f"function '{name}' instruction {ip}: slot out of range")
            elif op in ("JUMP", "JUMP_IF_FALSE"):
                target = instr[1]
                if not isinstance(target, int) or not (0 <= target < len(code)):
                    raise BytecodeError(f"function '{name}' instruction {ip}: jump target invalid")
            elif op == "TRY_BEGIN":
                target, end = instr[1], instr[2]
                if not isinstance(target, int) or not (0 <= target < len(code)):
                    raise BytecodeError(f"function '{name}' instruction {ip}: catch target invalid")
                if not isinstance(end, int) or not (0 <= end <= len(code)):
                    raise BytecodeError(f"function '{name}' instruction {ip}: try end invalid")
            elif op == "BINOP":
                if instr[1] not in _BINOPS:
                    raise BytecodeError(f"function '{name}' instruction {ip}: unknown binop")
            elif op == "UNOP":
                if instr[1] not in _UNOPS:
                    raise BytecodeError(f"function '{name}' instruction {ip}: unknown unop")
            elif op == "CALL":
                callee = instr[1]
                argc = instr[2]
                if callee not in functions:
                    raise BytecodeError(f"function '{name}' calls unknown function '{callee}'")
                if not isinstance(argc, int) or argc < 0:
                    raise BytecodeError(f"function '{name}' instruction {ip}: bad argc")
                if argc != functions[callee]["arity"]:
                    raise BytecodeError(
                        f"function '{name}' calls '{callee}' with {argc} args, expects {functions[callee]['arity']}"
                    )
            elif op == "CALL_NATIVE":
                callee = instr[1]
                argc = instr[2]
                if callee not in B.NATIVES:
                    raise BytecodeError(f"function '{name}' calls unknown native '{callee}'")
                if not isinstance(argc, int) or not any(
                    len(sig.params) == argc for sig in B.NATIVES[callee]
                ):
                    raise BytecodeError(
                        f"function '{name}' calls native '{callee}' with unsupported arity"
                    )
            elif op == "METHOD":
                method = instr[1]
                if not isinstance(method, str) or not any(key[1] == method for key in B.METHODS):
                    raise BytecodeError(f"function '{name}' calls unknown method '{method}'")
            elif op == "MODEL_INIT":
                if instr[1] not in models:
                    raise BytecodeError(f"function '{name}' initialises unknown model '{instr[1]}'")
            elif op == "TRAINING_METHOD":
                if instr[1] not in trainings:
                    raise BytecodeError(f"function '{name}' uses unknown training '{instr[1]}'")
                if instr[2] not in ("run", "evaluate"):
                    raise BytecodeError(f"function '{name}' uses unknown training method")
            elif op == "STRUCT_NEW":
                if instr[1] not in structs:
                    raise BytecodeError(f"function '{name}' constructs unknown struct '{instr[1]}'")
            elif op == "FIELD_GET":
                if instr[2] not in ("struct_field", "property"):
                    raise BytecodeError(f"function '{name}' has invalid field kind")
    if "main" in functions and functions["main"]["arity"] != 0:
        raise BytecodeError("'main' must take no parameters")
