"""Ahead-of-time C code generation for a verified PEACOCK bytecode subset.

Every bytecode instruction is emitted as C statements and labels.  The result is
not a bytecode-array interpreter: program control flow is compiled to native
machine code by the host C compiler.  The small C runtime supplies values and
checked operations.  Unsupported instructions fail before a compiler is run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from peacock.compiler.bytecode import verify_image


class NativeCodegenError(ValueError):
    pass


SUPPORTED_OPS = frozenset({
    "PUSH_CONST", "PUSH_SLOT", "STORE_SLOT", "POP", "BINOP", "UNOP",
    "CALL", "CALL_NATIVE", "METHOD", "INDEX_GET", "INDEX_SET", "MAKE_LIST",
    "MAKE_RANGE", "LEN", "ASSERT", "THROW", "JUMP", "JUMP_IF_FALSE",
    "RET", "NOP",
})
SUPPORTED_NATIVES = frozenset({"print", "str", "len"})
SUPPORTED_METHODS = frozenset({
    "len", "push", "pop", "get", "contains", "index_of", "join", "sort",
    "reverse", "starts_with", "ends_with", "substring",
})


def _c_string(text: str) -> str:
    data = text.encode("utf-8")
    return '"' + "".join(f"\\x{byte:02x}" for byte in data) + '"'


def _c_op(op: str) -> str:
    return _c_string(op)


def _constant(value: Any) -> str:
    if value is None:
        return "p_unit()"
    if isinstance(value, bool):
        return f"p_bool({1 if value else 0})"
    if isinstance(value, int):
        if not -(2**63) <= value < 2**63:
            raise NativeCodegenError("integer constant exceeds the native int64 representation")
        if value == -(2**63):
            return "p_int(INT64_MIN)"
        return f"p_int(INT64_C({value}))"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise NativeCodegenError("non-finite constants are not supported by the native backend")
        return f"p_float({value!r})"
    if isinstance(value, str):
        return f"p_string({_c_string(value)}, {len(value.encode('utf-8'))})"
    raise NativeCodegenError(f"native constant type {type(value).__name__} is not implemented")


@dataclass
class _Function:
    internal_name: str
    c_name: str
    image: dict


class NativeCGenerator:
    def __init__(self, image: dict):
        verify_image(image)
        self.image = image
        self.functions = [
            _Function(name, f"p_fn_{index}", function)
            for index, (name, function) in enumerate(image["functions"].items())
        ]
        self.by_name = {function.internal_name: function for function in self.functions}
        if "main" not in self.by_name:
            raise NativeCodegenError("native programs require a मुख्य() entry function")
        if self.by_name["main"].image["arity"] != 0:
            raise NativeCodegenError("native entry function must take no arguments")
        if image.get("models") or image.get("trainings"):
            raise NativeCodegenError("model/training declarations are not implemented by the native AOT backend")
        self._validate()

    def _validate(self) -> None:
        for function in self.functions:
            for instruction in function.image["code"]:
                op = instruction[0]
                if op not in SUPPORTED_OPS:
                    raise NativeCodegenError(
                        f"opcode {op} in {function.internal_name} is not implemented by the native AOT backend"
                    )
                if op == "CALL_NATIVE" and instruction[1] not in SUPPORTED_NATIVES:
                    raise NativeCodegenError(f"native function {instruction[1]} is not implemented by the AOT backend")
                if op == "METHOD" and instruction[1] not in SUPPORTED_METHODS:
                    raise NativeCodegenError(f"method {instruction[1]} is not implemented by the AOT backend")
                if op == "CALL" and instruction[1] not in self.by_name:
                    raise NativeCodegenError(f"call to unknown generated function {instruction[1]}")
                if op == "PUSH_CONST":
                    _constant(instruction[1])

    @staticmethod
    def _pop_args(stack: str, count: int, variable: str) -> list[str]:
        lines = [f"PValue {variable}[{max(1, count)}];"]
        for index in range(count - 1, -1, -1):
            lines.append(f"{variable}[{index}] = p_pop(&{stack});")
        return lines

    def _instruction(self, instruction: list, index: int) -> list[str]:
        op = instruction[0]
        stack = "stack"
        if op == "PUSH_CONST":
            return [f"p_push(&stack, {_constant(instruction[1])});"]
        if op == "PUSH_SLOT":
            return [f"p_push(&stack, p_read_slot(slots[{instruction[1]}]));"]
        if op == "STORE_SLOT":
            return [f"slots[{instruction[1]}] = p_pop(&stack);"]
        if op == "POP":
            return ["(void)p_pop(&stack);"]
        if op == "BINOP":
            return [
                "{ PValue right = p_pop(&stack); PValue left = p_pop(&stack);",
                f"p_push(&stack, p_binary({_c_op(instruction[1])}, left, right)); }}",
            ]
        if op == "UNOP":
            return [f"p_push(&stack, p_unary({_c_op(instruction[1])}, p_pop(&stack)));"]
        if op == "CALL":
            target = self.by_name[instruction[1]]
            lines = ["{"] + self._pop_args(stack, instruction[2], "args")
            lines.append(f"p_push(&stack, {target.c_name}({instruction[2]}, args)); }}")
            return lines
        if op == "CALL_NATIVE":
            lines = ["{"] + self._pop_args(stack, instruction[2], "args")
            lines.append(f"p_push(&stack, p_native({_c_string(instruction[1])}, {instruction[2]}, args)); }}")
            return lines
        if op == "METHOD":
            lines = ["{"] + self._pop_args(stack, instruction[2], "args")
            lines.append(f"p_push(&stack, p_method({_c_string(instruction[1])}, {instruction[2]}, args)); }}")
            return lines
        if op == "INDEX_GET":
            return ["{ PValue index = p_pop(&stack); PValue base = p_pop(&stack); p_push(&stack, p_index_get(base, index)); }"]
        if op == "INDEX_SET":
            return ["{ PValue value = p_pop(&stack); PValue index = p_pop(&stack); PValue base = p_pop(&stack); p_index_set(base, index, value); }"]
        if op == "MAKE_LIST":
            lines = ["{"] + self._pop_args(stack, instruction[1], "items")
            lines.append(f"p_push(&stack, p_list({instruction[1]}, items)); }}")
            return lines
        if op == "MAKE_RANGE":
            return ["{ PValue end = p_pop(&stack); PValue start = p_pop(&stack); p_push(&stack, p_range(p_require_int(start, \"range start\"), p_require_int(end, \"range end\"))); }"]
        if op == "LEN":
            return ["p_push(&stack, p_len(p_pop(&stack)));"]
        if op == "ASSERT":
            return ["{ PValue message = p_pop(&stack); PValue condition = p_pop(&stack); (void)p_assert(condition, message); }"]
        if op == "THROW":
            return ["(void)p_throw(p_pop(&stack));"]
        if op == "JUMP":
            return [f"goto L{instruction[1]};"]
        if op == "JUMP_IF_FALSE":
            return [
                "{ PValue condition = p_pop(&stack);",
                "if (condition.type != P_BOOL) p_fail(\"PE4006\", \"branch condition must be सत्यता\");",
                f"if (!condition.as.boolean) goto L{instruction[1]}; }}",
            ]
        if op == "RET":
            if instruction[1]:
                return ["{ PValue result = p_pop(&stack); p_leave(); return result; }"]
            return ["p_leave(); return p_unit();"]
        if op == "NOP":
            return [";"]
        raise NativeCodegenError(f"unsupported opcode {op} at instruction {index}")

    def _function(self, function: _Function) -> str:
        image = function.image
        slots = max(1, image["slots"])
        lines = [
            f"static PValue {function.c_name}(int argc, PValue *args) {{",
            f"if (argc != {image['arity']}) p_fail(\"PE4999\", \"generated function arity mismatch\");",
            "p_enter();",
            "(void)args;",
            f"PValue slots[{slots}] = {{0}};",
            "PStack stack = {0};",
        ]
        for index in range(image["arity"]):
            lines.append(f"slots[{index}] = args[{index}];")
        targets = {
            instruction[1]
            for instruction in image["code"]
            if instruction[0] in {"JUMP", "JUMP_IF_FALSE"}
        }
        for index, instruction in enumerate(image["code"]):
            if index in targets:
                lines.append(f"L{index}:;")
            lines.append("p_tick();")
            lines.extend("    " + line for line in self._instruction(instruction, index))
        lines.extend([
            "p_fail(\"PE4999\", \"generated function reached its end without RET\");",
            "return p_unit();",
            "}",
        ])
        return "\n".join(lines)

    def generate(self, *, library: bool = False) -> str:
        parts = [
            "/* Generated from verified PEACOCK bytecode.  Do not edit. */",
            f"/* language {self.image['language_version']}; compiler {self.image['compiler_version']} */",
            "#include \"runtime.h\"",
            "#include <limits.h>",
            "",
        ]
        parts.extend(f"static PValue {f.c_name}(int argc, PValue *args);" for f in self.functions)
        parts.append("")
        parts.extend(self._function(function) for function in self.functions)
        if library:
            parts.extend([
                "int peacock_run(int64_t max_steps, POutputCallback output, void *userdata, const char **error_message) {",
                "p_runtime_init(max_steps);",
                "p_set_output_callback(output, userdata);",
                "p_error_target_active = 1;",
                "if (setjmp(p_error_target)) {",
                "p_error_target_active = 0;",
                "p_runtime_cleanup();",
                "p_set_output_callback(NULL, NULL);",
                "if (error_message) *error_message = p_last_error();",
                "return 3;",
                "}",
                f"(void){self.by_name['main'].c_name}(0, NULL);",
                "p_error_target_active = 0;",
                "p_runtime_cleanup();",
                "p_set_output_callback(NULL, NULL);",
                "if (error_message) *error_message = NULL;",
                "return 0;",
                "}",
                "",
            ])
        else:
            parts.extend([
                "int main(void) {",
                "p_runtime_init(2000000);",
                f"(void){self.by_name['main'].c_name}(0, NULL);",
                "p_runtime_cleanup();",
                "return 0;",
                "}",
                "",
            ])
        return "\n\n".join(parts)


def generate_c(image: dict, *, library: bool = False) -> str:
    """Return deterministic C source for an executable or embeddable library."""

    return NativeCGenerator(image).generate(library=library)
