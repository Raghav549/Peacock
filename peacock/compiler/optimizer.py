"""PIR optimisation passes for PEACOCK 0.2.

Passes are deliberately conservative and evidence-backed:

1. branch folding on constant conditions;
2. block-local constant folding;
3. unreachable code elimination via reachability;
4. jump-to-next-label peephole;
5. dead temporary elimination for provably pure operations.

The pass pipeline never removes an operation that can raise a runtime error
(division, exponentiation, indexing, calls), so error behaviour is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ir import IRFunction, IRInstr, IRModule, PURE_OPS
from .types import FloatType, IntType

INT_MIN = -(2**63)
INT_MAX = 2**63 - 1


def _int_ok(v: int) -> int | None:
    return v if INT_MIN <= v <= INT_MAX else None


def _fold_binop(op: str, a, b):
    try:
        if op in ("+", "-", "*", "/", "%", "**") and isinstance(a, int) and isinstance(b, int):
            if op == "+":
                return _int_ok(a + b)
            if op == "-":
                return _int_ok(a - b)
            if op == "*":
                return _int_ok(a * b)
            if op == "/":
                if b == 0:
                    return None
                q = abs(a) // abs(b)
                return _int_ok(q if (a >= 0) == (b >= 0) else -q)
            if op == "%":
                if b == 0:
                    return None
                q = abs(a) // abs(b)
                q = q if (a >= 0) == (b >= 0) else -q
                return _int_ok(a - q * b)
            if op == "**":
                if b < 0 or b > 63:
                    return None
                return _int_ok(a**b)
        if op in ("+", "-", "*", "/") and isinstance(a, float) and isinstance(b, float):
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                return None if b == 0.0 else a / b
        if op == "+" and isinstance(a, str) and isinstance(b, str):
            return a + b
        if op == "==":
            return a == b if type(a) is type(b) else None
        if op == "!=":
            return a != b if type(a) is type(b) else None
        if op in ("<", "<=", ">", ">=") and type(a) is type(b) and isinstance(a, (int, float, str)):
            return {
                "<": a < b,
                "<=": a <= b,
                ">": a > b,
                ">=": a >= b,
            }[op]
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    return None


def _literal_type(value):
    if isinstance(value, bool):
        return "Bool"
    if isinstance(value, int):
        return "Int"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, str):
        return "String"
    return None


class Optimizer:
    def __init__(self):
        self.stats = {
            "constants_folded": 0,
            "branches_folded": 0,
            "unreachable_removed": 0,
            "dead_temps_removed": 0,
            "jumps_removed": 0,
            "labels_removed": 0,
        }

    def optimize_module(self, module: IRModule) -> IRModule:
        for fn in module.functions.values():
            fn.instrs = self.optimize_function(fn.instrs)
        return module

    def optimize_function(self, instrs: list[IRInstr]) -> list[IRInstr]:
        instrs = self._fold_constants(instrs)
        instrs = self._remove_unreachable(instrs)
        instrs = self._peephole(instrs)
        instrs = self._dead_temps(instrs)
        instrs = self._peephole(instrs)
        return instrs

    # -- constant folding --------------------------------------------------
    def _reset_boundary(self, constants: dict[int, object]) -> None:
        constants.clear()

    def _fold_constants(self, instrs: list[IRInstr]) -> list[IRInstr]:
        constants: dict[int, object] = {}
        out: list[IRInstr] = []
        for instr in instrs:
            op = instr.op
            if op in ("label", "jump", "try_begin", "try_end", "catch"):
                self._reset_boundary(constants)
            if op == "const" and instr.dest is not None:
                constants[instr.dest] = instr.args[0]
            elif op == "binop":
                binop, a, b = instr.args
                if a in constants and b in constants:
                    folded = _fold_binop(binop, constants[a], constants[b])
                    if folded is not None and instr.dest is not None:
                        instr = IRInstr(
                            "const",
                            instr.dest,
                            (folded,),
                            instr.dest_type,
                            instr.span,
                        )
                        constants[instr.dest] = folded
                        self.stats["constants_folded"] += 1
                else:
                    if instr.dest is not None:
                        constants.pop(instr.dest, None)
            elif op == "unop":
                unop, a = instr.args
                if a in constants:
                    val = constants[a]
                    folded = None
                    if unop == "-" and isinstance(val, int) and not isinstance(val, bool):
                        folded = _int_ok(-val)
                    elif unop == "-" and isinstance(val, float):
                        folded = -val
                    elif unop == "not" and isinstance(val, bool):
                        folded = not val
                    if folded is not None and instr.dest is not None:
                        instr = IRInstr("const", instr.dest, (folded,), instr.dest_type, instr.span)
                        constants[instr.dest] = folded
                        self.stats["constants_folded"] += 1
                else:
                    if instr.dest is not None:
                        constants.pop(instr.dest, None)
            elif op == "branch":
                cond, t, f = instr.args
                if cond in constants and isinstance(constants[cond], bool):
                    target = t if constants[cond] else f
                    instr = IRInstr("jump", None, (target,), None, instr.span)
                    self.stats["branches_folded"] += 1
                    self._reset_boundary(constants)
            elif instr.dest is not None:
                constants.pop(instr.dest, None)
            out.append(instr)
        return out

    # -- reachability ------------------------------------------------------
    def _remove_unreachable(self, instrs: list[IRInstr]) -> list[IRInstr]:
        if not instrs:
            return instrs
        labels = {
            instr.args[0]: index
            for index, instr in enumerate(instrs)
            if instr.op == "label"
        }
        reachable: set[int] = set()
        work = [0]
        while work:
            index = work.pop()
            if index < 0 or index >= len(instrs) or index in reachable:
                continue
            reachable.add(index)
            instr = instrs[index]
            if instr.op == "jump":
                work.append(labels.get(instr.args[0], -1))
            elif instr.op == "branch":
                work.append(labels.get(instr.args[1], -1))
                work.append(labels.get(instr.args[2], -1))
            elif instr.op in ("return", "throw"):
                continue
            elif instr.op == "try_begin":
                work.append(labels.get(instr.args[0], -1))
                work.append(index + 1)
            else:
                work.append(index + 1)
        # Exception-scope markers are structural. A `throw` terminates a normal
        # path, so the matching `try_end` can be unreachable while the handler is
        # reachable. Keep both halves of any try scope that is reachable at all,
        # otherwise the verifier would see an unbalanced scope after DCE.
        stack: list[int] = []
        pairs: list[tuple[int, int]] = []
        for index, instr in enumerate(instrs):
            if instr.op == "try_begin":
                stack.append(index)
            elif instr.op == "try_end" and stack:
                pairs.append((stack.pop(), index))
        structural: set[int] = set()
        for begin, end in pairs:
            if begin in reachable or end in reachable:
                structural.add(begin)
                structural.add(end)
        reachable |= structural

        if len(reachable) == len(instrs):
            return instrs
        self.stats["unreachable_removed"] += len(instrs) - len(reachable)
        return [instr for i, instr in enumerate(instrs) if i in reachable]

    # -- peephole ----------------------------------------------------------
    def _peephole(self, instrs: list[IRInstr]) -> list[IRInstr]:
        out: list[IRInstr] = []
        for i, instr in enumerate(instrs):
            if instr.op == "jump" and i + 1 < len(instrs) and instrs[i + 1].op == "label":
                if instrs[i + 1].args[0] == instr.args[0]:
                    self.stats["jumps_removed"] += 1
                    continue
            out.append(instr)
        # Remove labels that are not referenced by any control-flow or handler.
        used: set[str] = set()
        for instr in out:
            if instr.op in ("jump", "try_begin"):
                used.add(instr.args[0])
            elif instr.op == "branch":
                used.add(instr.args[1])
                used.add(instr.args[2])
        filtered: list[IRInstr] = []
        for instr in out:
            if instr.op == "label" and instr.args[0] not in used:
                # A trailing unreferenced label has no effect; removing it is safe.
                self.stats["labels_removed"] += 1
                continue
            filtered.append(instr)
        return filtered

    # -- dead temporaries --------------------------------------------------
    def _dead_temps(self, instrs: list[IRInstr]) -> list[IRInstr]:
        used: set[int] = set()
        for instr in instrs:
            op = instr.op
            if op in ("slot_get",):
                continue
            if op in ("slot_set",):
                used.add(instr.args[1])
            elif op in ("binop",):
                used.add(instr.args[1])
                used.add(instr.args[2])
            elif op in ("unop", "len", "throw"):
                used.add(instr.args[1] if op == "unop" else instr.args[0])
            elif op in ("index_get", "field_get"):
                if isinstance(instr.args[0], int):
                    used.add(instr.args[0])
                if op == "index_get":
                    used.add(instr.args[1])
                if op == "field_set":
                    pass
            elif op in ("index_set",):
                used.add(instr.args[0])
                used.add(instr.args[1])
                used.add(instr.args[2])
            elif op == "field_set":
                used.add(instr.args[0])
                used.add(instr.args[2])
            elif op in ("call", "call_native", "struct_new", "model_init"):
                for arg in instr.args[1]:
                    used.add(arg)
            elif op == "method":
                used.add(instr.args[1])
                for arg in instr.args[2]:
                    used.add(arg)
            elif op == "training_method":
                for arg in instr.args[2]:
                    used.add(arg)
            elif op == "make_list":
                used.update(instr.args)
            elif op in ("make_range",):
                used.add(instr.args[0])
                used.add(instr.args[1])
            elif op == "assert":
                used.add(instr.args[0])
                if instr.args[1] is not None:
                    used.add(instr.args[1])
            elif op == "branch":
                used.add(instr.args[0])
            elif op == "return":
                if instr.args[0] is not None:
                    used.add(instr.args[0])
        changed = True
        while changed:
            changed = False
            kept: list[IRInstr] = []
            for instr in instrs:
                if instr.op in PURE_OPS and instr.dest is not None and instr.dest not in used:
                    self.stats["dead_temps_removed"] += 1
                    changed = True
                    continue
                kept.append(instr)
            instrs = kept
        return instrs


def optimize(module: IRModule) -> tuple[IRModule, dict[str, int]]:
    opt = Optimizer()
    opt.optimize_module(module)
    return module, dict(opt.stats)
