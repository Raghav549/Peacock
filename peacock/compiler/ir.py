"""PEACOCK IR (PIR): a flat, typed, three-address intermediate representation.

PIR uses explicit virtual registers for expression temporaries and numbered slots
for named locals. Control flow is expressed with labels, conditional branches and
jumps. Values that must survive a control-flow join are stored in slots, never in
temporaries, which keeps the representation simple to verify.

The IR is intentionally *not* SSA in 0.2. A documented future optimisation is an
SSA construction pass (see ROADMAP.md). The verifier performs structural checks
and limited type checking; full dominance-based verification is future work and
is labelled as such in docs/compiler/ir.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import builtins as B
from . import types as T
from .ast_nodes import (
    AssertStmt,
    AssignStmt,
    Binary,
    Block,
    BoolLit,
    BreakStmt,
    Call,
    CapabilityStmt,
    ContinueStmt,
    Expr,
    ExprStmt,
    Field,
    FloatLit,
    ForStmt,
    FunctionDecl,
    IfStmt,
    Index,
    IntLit,
    LetStmt,
    ListLit,
    Name,
    RangeExpr,
    ReturnStmt,
    Stmt,
    StringLit,
    ThrowStmt,
    TryStmt,
    Unary,
    WhileStmt,
)
from .diagnostics import Span
from .semantic import FunctionSymbol, ModelSymbol, StructSymbol, TrainingSymbol, TypedProgram


class IRVerificationError(Exception):
    pass


@dataclass
class IRInstr:
    op: str
    dest: int | None = None
    args: tuple[Any, ...] = ()
    dest_type: T.Type | None = None
    span: Span | None = None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        bits = [self.op]
        if self.dest is not None:
            bits.append(f"%{self.dest}")
        bits.extend(repr(a) for a in self.args)
        return " ".join(bits)


@dataclass
class IRFunction:
    name: str
    decl: FunctionDecl
    return_type: T.Type
    slot_count: int
    capabilities: frozenset[str]
    instrs: list[IRInstr] = field(default_factory=list)


@dataclass
class ModelSpec:
    name: str
    input_dtype: str
    input_shape: tuple[int, ...]
    output_dtype: str
    output_shape: tuple[int, ...]
    layers: list[tuple[int, str]]  # (units, activation)


@dataclass
class IRModule:
    name: str | None
    functions: dict[str, IRFunction]
    structs: dict[str, list[str]]
    models: dict[str, ModelSpec]
    trainings: dict[str, dict[str, Any]]
    uses: tuple[str, ...]
    source: str = ""
    source_path: str = "<source>"


#: Operations whose output is a pure function of their inputs, used by DCE.
PURE_OPS = {
    "const",
    "move",
    "make_range",
    "nop",
}


class IRBuilder:
    def __init__(self, fn: FunctionSymbol):
        self.fn = fn
        self.next_reg = fn.decl.slot_count
        self.instrs: list[IRInstr] = []
        self._label_counter = 0
        self._break_targets: list[str] = []
        self._continue_targets: list[str] = []

    # -- allocation & emission --------------------------------------------
    def new_reg(self) -> int:
        r = self.next_reg
        self.next_reg += 1
        return r

    def label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def emit(
        self,
        op: str,
        dest: int | None = None,
        args: tuple[Any, ...] = (),
        span: Span | None = None,
        dest_type: T.Type | None = None,
    ) -> int | None:
        self.instrs.append(IRInstr(op, dest, args, dest_type, span))
        return dest

    # -- statements --------------------------------------------------------
    def build(self) -> IRFunction:
        self.stmts(self.fn.decl.body.statements)
        self.emit("return", args=(None,))
        return IRFunction(
            self.fn.name,
            self.fn.decl,
            self.fn.return_type,
            self.next_reg,
            self.fn.capabilities,
            self.instrs,
        )

    def stmts(self, statements) -> None:
        # Statements after a definite terminator (return/throw) are unreachable;
        # the semantic analyser still checks them, but no code is emitted.
        for stmt in statements:
            self.stmt(stmt)
            if stmt.always_returns:
                break

    def stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, LetStmt):
            reg = self.expr(stmt.init)
            self.emit("slot_set", args=(stmt.slot, reg), span=stmt.span)
            return
        if isinstance(stmt, ExprStmt):
            self.expr(stmt.expr)
            return
        if isinstance(stmt, AssignStmt):
            self.assign(stmt)
            return
        if isinstance(stmt, Block):
            self.stmts(stmt.statements)
            return
        if isinstance(stmt, IfStmt):
            self._if(stmt)
            return
        if isinstance(stmt, WhileStmt):
            self._while(stmt)
            return
        if isinstance(stmt, ForStmt):
            self._for(stmt)
            return
        if isinstance(stmt, ReturnStmt):
            if stmt.value is None:
                self.emit("return", args=(None,), span=stmt.span)
            else:
                reg = self.expr(stmt.value)
                self.emit("return", args=(reg,), span=stmt.span)
            return
        if isinstance(stmt, BreakStmt):
            if self._break_targets:
                self.emit("jump", args=(self._break_targets[-1],), span=stmt.span)
            return
        if isinstance(stmt, ContinueStmt):
            if self._continue_targets:
                self.emit("jump", args=(self._continue_targets[-1],), span=stmt.span)
            return
        if isinstance(stmt, CapabilityStmt):
            return  # declared in function metadata
        if isinstance(stmt, ThrowStmt):
            reg = self.expr(stmt.value)
            self.emit("throw", args=(reg,), span=stmt.span)
            return
        if isinstance(stmt, TryStmt):
            self._try(stmt)
            return
        if isinstance(stmt, AssertStmt):
            cond = self.expr(stmt.condition)
            msg = self.expr(stmt.message) if stmt.message is not None else None
            self.emit("assert", args=(cond, msg), span=stmt.span)
            return
        raise AssertionError(f"unhandled statement {type(stmt).__name__}")

    def assign(self, stmt: AssignStmt) -> None:
        target = stmt.target
        op = stmt.op
        if isinstance(target, Name):
            if op == "=":
                value = self.expr(stmt.value)
                self.emit("slot_set", args=(target.symbol.slot, value), span=stmt.span)
            else:
                left = self.new_reg()
                self.emit("slot_get", left, (target.symbol.slot,), span=stmt.span, dest_type=target.ty)
                right = self.expr(stmt.value)
                result = self._binary_regs(op[:-1], left, target.ty, right, stmt.value.ty, stmt.span)
                self.emit("slot_set", args=(target.symbol.slot, result), span=stmt.span)
            return
        if isinstance(target, Field):
            base = self.expr(target.base)
            if op == "=":
                value = self.expr(stmt.value)
                self.emit(
                    "field_set",
                    args=(base, target.name, value),
                    span=stmt.span,
                )
            else:
                old = self.new_reg()
                self.emit(
                    "field_get",
                    old,
                    (base, target.name, target.field_kind or "struct_field"),
                    span=target.span,
                    dest_type=target.ty,
                )
                right = self.expr(stmt.value)
                result = self._binary_regs(op[:-1], old, target.ty, right, stmt.value.ty, stmt.span)
                self.emit("field_set", args=(base, target.name, result), span=stmt.span)
            return
        if isinstance(target, Index):
            base = self.expr(target.base)
            index = self.expr(target.index)
            if op == "=":
                value = self.expr(stmt.value)
                self.emit("index_set", args=(base, index, value), span=stmt.span)
            else:
                old = self.new_reg()
                self.emit("index_get", old, (base, index), span=target.span, dest_type=target.ty)
                right = self.expr(stmt.value)
                result = self._binary_regs(op[:-1], old, target.ty, right, stmt.value.ty, stmt.span)
                self.emit("index_set", args=(base, index, result), span=stmt.span)
            return
        raise AssertionError("invalid assignment target")

    def _if(self, stmt: IfStmt) -> None:
        cond = self.expr(stmt.condition)
        then_lbl = self.label("then")
        else_lbl = self.label("else")
        join_lbl = self.label("endif")
        self.emit("branch", args=(cond, then_lbl, else_lbl), span=stmt.condition.span)
        self.emit("label", args=(then_lbl,))
        self.stmt(stmt.then_block)
        self.emit("jump", args=(join_lbl,), span=stmt.span)
        self.emit("label", args=(else_lbl,))
        if stmt.else_branch is not None:
            self.stmt(stmt.else_branch)
        self.emit("jump", args=(join_lbl,), span=stmt.span)
        self.emit("label", args=(join_lbl,))

    def _while(self, stmt: WhileStmt) -> None:
        head = self.label("while")
        body = self.label("do")
        exit_lbl = self.label("endwhile")
        self.emit("jump", args=(head,), span=stmt.span)
        self.emit("label", args=(head,))
        cond = self.expr(stmt.condition)
        self.emit("branch", args=(cond, body, exit_lbl), span=stmt.condition.span)
        self.emit("label", args=(body,))
        self._break_targets.append(exit_lbl)
        self._continue_targets.append(head)
        self.stmt(stmt.body)
        self._break_targets.pop()
        self._continue_targets.pop()
        self.emit("jump", args=(head,), span=stmt.span)
        self.emit("label", args=(exit_lbl,))

    def _for(self, stmt: ForStmt) -> None:
        iterable_ty = stmt.iterable.ty
        head = self.label("for")
        body = self.label("forbody")
        step = self.label("forstep")
        exit_lbl = self.label("endfor")
        if isinstance(stmt.iterable, RangeExpr):
            start = self.expr(stmt.iterable.start)
            end_slot = self.new_reg()
            end = self.expr(stmt.iterable.end)
            self.emit("slot_set", args=(end_slot, end), span=stmt.span)
            self.emit("slot_set", args=(stmt.slot, start), span=stmt.span)
            self.emit("jump", args=(head,), span=stmt.span)
            self.emit("label", args=(head,))
            current = self.new_reg()
            self.emit("slot_get", current, (stmt.slot,), dest_type=T.IntType)
            limit = self.new_reg()
            self.emit("slot_get", limit, (end_slot,), dest_type=T.IntType)
            cond = self.new_reg()
            self.emit("binop", cond, ("<", current, limit), dest_type=T.BoolType, span=stmt.span)
            self.emit("branch", args=(cond, body, exit_lbl), span=stmt.span)
            self.emit("label", args=(body,))
            self._break_targets.append(exit_lbl)
            self._continue_targets.append(step)
            self.stmt(stmt.body)
            self._break_targets.pop()
            self._continue_targets.pop()
            self.emit("label", args=(step,))
            cur2 = self.new_reg()
            self.emit("slot_get", cur2, (stmt.slot,), dest_type=T.IntType)
            one = self.new_reg()
            self.emit("const", one, (1,), dest_type=T.IntType)
            nxt = self.new_reg()
            self.emit("binop", nxt, ("+", cur2, one), dest_type=T.IntType)
            self.emit("slot_set", args=(stmt.slot, nxt), span=stmt.span)
            self.emit("jump", args=(head,), span=stmt.span)
            self.emit("label", args=(exit_lbl,))
            return
        # List iteration: keep the list and an index in slots.
        list_slot = self.new_reg()
        lst = self.expr(stmt.iterable)
        self.emit("slot_set", args=(list_slot, lst), span=stmt.span)
        index_slot = self.new_reg()
        zero = self.new_reg()
        self.emit("const", zero, (0,), dest_type=T.IntType)
        self.emit("slot_set", args=(index_slot, zero), span=stmt.span)
        self.emit("jump", args=(head,), span=stmt.span)
        self.emit("label", args=(head,))
        idx = self.new_reg()
        self.emit("slot_get", idx, (index_slot,), dest_type=T.IntType)
        length = self.new_reg()
        lst2 = self.new_reg()
        self.emit("slot_get", lst2, (list_slot,), dest_type=iterable_ty)
        self.emit("len", length, (lst2,), dest_type=T.IntType)
        cond = self.new_reg()
        self.emit("binop", cond, ("<", idx, length), dest_type=T.BoolType)
        self.emit("branch", args=(cond, body, exit_lbl), span=stmt.span)
        self.emit("label", args=(body,))
        idx2 = self.new_reg()
        self.emit("slot_get", idx2, (index_slot,), dest_type=T.IntType)
        lst3 = self.new_reg()
        self.emit("slot_get", lst3, (list_slot,), dest_type=iterable_ty)
        item = self.new_reg()
        self.emit("index_get", item, (lst3, idx2), dest_type=stmt.iterable.ty.element if isinstance(stmt.iterable.ty, T.ListType) else None)
        self.emit("slot_set", args=(stmt.slot, item), span=stmt.span)
        self._break_targets.append(exit_lbl)
        self._continue_targets.append(step)
        self.stmt(stmt.body)
        self._break_targets.pop()
        self._continue_targets.pop()
        self.emit("label", args=(step,))
        idx3 = self.new_reg()
        self.emit("slot_get", idx3, (index_slot,), dest_type=T.IntType)
        one = self.new_reg()
        self.emit("const", one, (1,), dest_type=T.IntType)
        nxt = self.new_reg()
        self.emit("binop", nxt, ("+", idx3, one), dest_type=T.IntType)
        self.emit("slot_set", args=(index_slot, nxt), span=stmt.span)
        self.emit("jump", args=(head,), span=stmt.span)
        self.emit("label", args=(exit_lbl,))

    def _try(self, stmt: TryStmt) -> None:
        catch_lbl = self.label("catch")
        join = self.label("endtry")
        self.emit("try_begin", args=(catch_lbl,), span=stmt.span)
        self.stmt(stmt.body)
        self.emit("try_end", span=stmt.span)
        self.emit("jump", args=(join,), span=stmt.span)
        self.emit("label", args=(catch_lbl,))
        err = self.new_reg()
        self.emit("catch", err, dest_type=T.StringType, span=stmt.span)
        self.emit("slot_set", args=(stmt.slot, err), span=stmt.span)
        self.stmt(stmt.catch_body)
        self.emit("label", args=(join,))

    # -- expressions -------------------------------------------------------
    def expr(self, expr: Expr) -> int:
        if isinstance(expr, IntLit):
            r = self.new_reg()
            self.emit("const", r, (expr.value,), dest_type=T.IntType, span=expr.span)
            return r
        if isinstance(expr, FloatLit):
            r = self.new_reg()
            self.emit("const", r, (expr.value,), dest_type=T.FloatType, span=expr.span)
            return r
        if isinstance(expr, StringLit):
            r = self.new_reg()
            self.emit("const", r, (expr.value,), dest_type=T.StringType, span=expr.span)
            return r
        if isinstance(expr, BoolLit):
            r = self.new_reg()
            self.emit("const", r, (expr.value,), dest_type=T.BoolType, span=expr.span)
            return r
        if isinstance(expr, Name):
            r = self.new_reg()
            if expr.resolution == "local":
                self.emit("slot_get", r, (expr.symbol.slot,), dest_type=expr.ty, span=expr.span)
            else:
                raise AssertionError(f"non-local name reached codegen: {expr.ident} ({expr.resolution})")
            return r
        if isinstance(expr, Unary):
            operand = self.expr(expr.operand)
            r = self.new_reg()
            self.emit("unop", r, (expr.op, operand), dest_type=expr.ty, span=expr.span)
            return r
        if isinstance(expr, Binary):
            if expr.op in ("and", "or"):
                return self._short_circuit(expr)
            left = self.expr(expr.left)
            right = self.expr(expr.right)
            return self._binary_regs(expr.op, left, expr.left.ty, right, expr.right.ty, expr.span, dest_ty=expr.ty)
        if isinstance(expr, RangeExpr):
            start = self.expr(expr.start)
            end = self.expr(expr.end)
            r = self.new_reg()
            self.emit("make_range", r, (start, end), dest_type=expr.ty, span=expr.span)
            return r
        if isinstance(expr, ListLit):
            regs = [self.expr(e) for e in expr.elements]
            r = self.new_reg()
            self.emit("make_list", r, tuple(regs), dest_type=expr.ty, span=expr.span)
            return r
        if isinstance(expr, Field):
            base = self.expr(expr.base)
            r = self.new_reg()
            self.emit(
                "field_get",
                r,
                (base, expr.name, expr.field_kind or "struct_field"),
                dest_type=expr.ty,
                span=expr.span,
            )
            return r
        if isinstance(expr, Index):
            base = self.expr(expr.base)
            index = self.expr(expr.index)
            r = self.new_reg()
            self.emit("index_get", r, (base, index), dest_type=expr.ty, span=expr.span)
            return r
        if isinstance(expr, Call):
            return self._call(expr)
        raise AssertionError(f"unhandled expression {type(expr).__name__}")

    def _short_circuit(self, expr: Binary) -> int:
        left = self.expr(expr.left)
        eval_right = self.label("sc_right")
        true_lbl = self.label("sc_true")
        false_lbl = self.label("sc_false")
        join = self.label("sc_join")
        result = self.new_reg()
        if expr.op == "and":
            self.emit("branch", args=(left, eval_right, false_lbl), span=expr.span)
        else:
            self.emit("branch", args=(left, true_lbl, eval_right), span=expr.span)
        self.emit("label", args=(eval_right,))
        right = self.expr(expr.right)
        self.emit("branch", args=(right, true_lbl, false_lbl), span=expr.span)
        self.emit("label", args=(true_lbl,))
        self.emit("const", result, (True,), dest_type=T.BoolType)
        self.emit("jump", args=(join,))
        self.emit("label", args=(false_lbl,))
        self.emit("const", result, (False,), dest_type=T.BoolType)
        self.emit("label", args=(join,))
        return result

    def _binary_regs(
        self,
        op: str,
        left: int,
        left_ty: T.Type,
        right: int,
        right_ty: T.Type,
        span: Span,
        dest_ty: T.Type | None = None,
    ) -> int:
        r = self.new_reg()
        self.emit("binop", r, (op, left, right), dest_type=dest_ty, span=span)
        return r

    def _call(self, expr: Call) -> int:
        kind = expr.call_kind
        if kind == "namespace" or kind == "native":
            sig = expr.native_sig
            assert sig is not None
            provided = [self.expr(arg) for arg in expr.args]
            ordered: list[int] = []
            for i, param in enumerate(sig.params):
                source = expr.arg_order[i] if i < len(expr.arg_order) else -1
                if source >= 0:
                    ordered.append(provided[source])
                else:
                    default = param.default
                    if default is B.NO_DEFAULT:
                        raise AssertionError("missing required native parameter")
                    r = self.new_reg()
                    self.emit(
                        "const",
                        r,
                        (default,),
                        dest_type=param.ty if param.ty != T.AnyType else None,
                        span=expr.span,
                    )
                    ordered.append(r)
            r = self.new_reg()
            self.emit(
                "call_native",
                r,
                (expr.native_name, tuple(ordered)),
                dest_type=expr.ty,
                span=expr.span,
            )
            return r
        if kind == "function":
            provided = [self.expr(arg) for arg in expr.args]
            ordered = [provided[i] for i in expr.arg_order if i >= 0]
            r = self.new_reg()
            self.emit("call", r, (expr.target.name, tuple(ordered)), dest_type=expr.ty, span=expr.span)
            return r
        if kind == "struct":
            provided = [self.expr(arg) for arg in expr.args]
            r = self.new_reg()
            self.emit(
                "struct_new",
                r,
                (expr.target.name, tuple(provided)),
                dest_type=expr.ty,
                span=expr.span,
            )
            return r
        if kind == "method":
            field = expr.callee
            assert isinstance(field, Field)
            receiver = self.expr(field.base)
            args = [self.expr(a) for a in expr.args]
            r = self.new_reg()
            self.emit(
                "method",
                r,
                (field.name, receiver, tuple(args)),
                dest_type=expr.ty,
                span=expr.span,
            )
            return r
        if kind == "model_method":
            args = [self.expr(a) for a in expr.args]
            ordered = [args[i] for i in expr.arg_order if i >= 0]
            # Fill omitted defaults.
            for i, param in enumerate(getattr(expr, "method_params", ())):
                if i >= len(expr.arg_order) or expr.arg_order[i] < 0:
                    default = param.default
                    if default is B.NO_DEFAULT:
                        raise AssertionError("missing model method argument")
                    rr = self.new_reg()
                    self.emit("const", rr, (default,), dest_type=param.ty, span=expr.span)
                    ordered.append(rr)
            r = self.new_reg()
            self.emit(
                "model_init",
                r,
                (expr.target.name, tuple(ordered)),
                dest_type=expr.ty,
                span=expr.span,
            )
            return r
        if kind == "training_method":
            args = [self.expr(a) for a in expr.args]
            ordered = [args[i] for i in expr.arg_order if i >= 0]
            r = self.new_reg()
            self.emit(
                "training_method",
                r,
                (expr.target.name, expr.method_name, tuple(ordered)),
                dest_type=expr.ty,
                span=expr.span,
            )
            return r
        raise AssertionError(f"unhandled call kind {kind}")


def build_ir(program: TypedProgram, source: str = "", source_path: str = "<source>") -> IRModule:
    functions: dict[str, IRFunction] = {}
    for name, fn in program.functions.items():
        functions[name] = IRBuilder(fn).build()
    structs = {name: list(sym.field_names) for name, sym in program.structs.items()}
    models: dict[str, ModelSpec] = {}
    for name, model in program.models.items():
        input_t = model.input_type
        output_t = model.output_type
        assert input_t.shape is not None and output_t.shape is not None
        models[name] = ModelSpec(
            name,
            input_t.dtype,
            input_t.shape,
            output_t.dtype,
            output_t.shape,
            [(layer.units, layer.activation) for layer in model.layers],
        )
    trainings = {name: dict(sym.config) for name, sym in program.trainings.items()}
    return IRModule(
        program.module.name,
        functions,
        structs,
        models,
        trainings,
        tuple(sorted(program.namespaces)),
        source,
        source_path,
    )


class IRVerifier:
    """Structural and limited type verification of a PIR module."""

    def __init__(self, module: IRModule):
        self.module = module
        self.errors: list[str] = []

    def fail(self, fn: IRFunction, index: int, message: str) -> None:
        self.errors.append(f"function '{fn.name}' instruction {index}: {message}")

    def verify(self) -> None:
        for name, fn in self.module.functions.items():
            self._verify_function(fn)
        if self.errors:
            raise IRVerificationError("IR verification failed:\n  " + "\n  ".join(self.errors))

    def _verify_function(self, fn: IRFunction) -> None:
        labels: set[str] = set()
        for index, instr in enumerate(fn.instrs):
            if instr.op == "label":
                label = instr.args[0]
                if label in labels:
                    self.fail(fn, index, f"duplicate label '{label}'")
                labels.add(label)
        reg_types: dict[int, T.Type] = {}
        try_depth = 0
        for index, instr in enumerate(fn.instrs):
            op = instr.op
            if instr.dest is not None:
                if not (0 <= instr.dest < fn.slot_count):
                    self.fail(fn, index, f"destination register {instr.dest} out of range")
                if instr.dest_type is not None and not isinstance(instr.dest_type, T.Type):
                    self.fail(fn, index, "destination type is not a Type")
            if op == "const":
                value = instr.args[0]
                if isinstance(value, bool):
                    actual = T.BoolType
                elif isinstance(value, int):
                    actual = T.IntType
                elif isinstance(value, float):
                    actual = T.FloatType
                elif isinstance(value, str):
                    actual = T.StringType
                else:
                    self.fail(fn, index, f"unsupported constant type {type(value).__name__}")
                    actual = T.ErrorType
                if instr.dest_type is not None and not T.is_assignable(actual, instr.dest_type):
                    self.fail(
                        fn,
                        index,
                        f"constant {value!r} is {actual.display()}, destination is {instr.dest_type.display()}",
                    )
            elif op in ("slot_get", "slot_set"):
                slot = instr.args[0]
                if not (0 <= slot < fn.slot_count):
                    self.fail(fn, index, f"slot {slot} out of range")
            elif op in ("move", "unop", "len", "index_get", "field_get", "catch", "slot_get"):
                for arg in instr.args:
                    if isinstance(arg, int):
                        self._check_reg(fn, index, arg, reg_types)
            elif op == "binop":
                _, a, b = instr.args
                self._check_reg(fn, index, a, reg_types)
                self._check_reg(fn, index, b, reg_types)
                self._check_binop_type(fn, index, instr, reg_types)
            elif op == "jump" or op == "try_begin":
                target = instr.args[0]
                if target not in labels:
                    self.fail(fn, index, f"jump target '{target}' does not exist")
                if op == "try_begin":
                    try_depth += 1
            elif op == "try_end":
                if try_depth == 0:
                    self.fail(fn, index, "try_end without try_begin")
                else:
                    try_depth -= 1
            elif op == "branch":
                cond, t, f = instr.args
                self._check_reg(fn, index, cond, reg_types)
                for target in (t, f):
                    if target not in labels:
                        self.fail(fn, index, f"branch target '{target}' does not exist")
            elif op == "call":
                name, arg_regs = instr.args
                if name not in self.module.functions:
                    self.fail(fn, index, f"call to unknown function '{name}'")
                else:
                    arity = len(self.module.functions[name].decl.params)
                    if len(arg_regs) != arity:
                        self.fail(fn, index, f"call to '{name}' passes {len(arg_regs)} args, expects {arity}")
                for arg in arg_regs:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "call_native":
                name, arg_regs = instr.args
                if name not in B.NATIVES:
                    self.fail(fn, index, f"unknown native function '{name}'")
                for arg in arg_regs:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "method":
                method, receiver, arg_regs = instr.args
                self._check_reg(fn, index, receiver, reg_types)
                for arg in arg_regs:
                    self._check_reg(fn, index, arg, reg_types)
                if not any(key[1] == method for key in B.METHODS):
                    self.fail(fn, index, f"unknown method '{method}'")
            elif op == "model_init":
                name, arg_regs = instr.args
                if name not in self.module.models:
                    self.fail(fn, index, f"unknown model '{name}'")
                for arg in arg_regs:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "training_method":
                name, method, arg_regs = instr.args
                if name not in self.module.trainings:
                    self.fail(fn, index, f"unknown training declaration '{name}'")
                if method not in ("run", "evaluate"):
                    self.fail(fn, index, f"unknown training method '{method}'")
                for arg in arg_regs:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "struct_new":
                name, arg_regs = instr.args
                if name not in self.module.structs:
                    self.fail(fn, index, f"unknown struct '{name}'")
                elif len(arg_regs) != len(self.module.structs[name]):
                    self.fail(fn, index, f"struct '{name}' expects {len(self.module.structs[name])} fields")
                for arg in arg_regs:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "field_set":
                base, field_name, value = instr.args
                self._check_reg(fn, index, base, reg_types)
                self._check_reg(fn, index, value, reg_types)
            elif op == "index_set":
                base, idx_reg, value = instr.args
                self._check_reg(fn, index, base, reg_types)
                self._check_reg(fn, index, idx_reg, reg_types)
                self._check_reg(fn, index, value, reg_types)
            elif op == "make_list":
                for arg in instr.args:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "make_range":
                for arg in instr.args:
                    self._check_reg(fn, index, arg, reg_types)
            elif op == "assert":
                cond, msg = instr.args
                self._check_reg(fn, index, cond, reg_types)
                if msg is not None:
                    self._check_reg(fn, index, msg, reg_types)
            elif op == "throw":
                self._check_reg(fn, index, instr.args[0], reg_types)
            elif op == "return":
                value = instr.args[0]
                if value is not None:
                    self._check_reg(fn, index, value, reg_types)
            elif op in ("nop", "label", "try_end"):
                pass
            elif op == "slot_set":
                self._check_reg(fn, index, instr.args[1], reg_types)
            elif op == "field_get":
                base = instr.args[0]
                self._check_reg(fn, index, base, reg_types)
            else:
                self.fail(fn, index, f"unknown IR op '{op}'")
            if instr.dest is not None and instr.dest_type is not None:
                reg_types[instr.dest] = instr.dest_type
        if try_depth != 0:
            self.errors.append(f"function '{fn.name}': {try_depth} unclosed try block(s)")
        if fn.instrs and fn.instrs[-1].op not in ("return", "throw", "jump"):
            self.errors.append(
                f"function '{fn.name}': ends with '{fn.instrs[-1].op}', "
                "which can fall through; expected 'return'"
            )

    def _check_reg(self, fn: IRFunction, index: int, reg: int, reg_types: dict[int, T.Type]) -> None:
        if not isinstance(reg, int):
            self.fail(fn, index, f"expected register, found {reg!r}")
            return
        if not (0 <= reg < fn.slot_count):
            self.fail(fn, index, f"register {reg} out of range (slot_count={fn.slot_count})")

    def _check_binop_type(self, fn: IRFunction, index: int, instr: IRInstr, reg_types) -> None:
        op, a, b = instr.args
        lt = reg_types.get(a)
        rt = reg_types.get(b)
        if lt is None or rt is None or instr.dest_type is None:
            return
        if op in ("and", "or"):
            expected, actual = T.BoolType, None
        elif op in ("==", "!=", "<", "<=", ">", ">="):
            expected, actual = T.BoolType, None
        elif op == "+":
            if lt == rt == T.IntType:
                expected = T.IntType
            elif lt == rt == T.FloatType:
                expected = T.FloatType
            elif lt == rt == T.StringType:
                expected = T.StringType
            else:
                return
        elif op in ("-", "*", "/", "%", "**"):
            if lt == rt and lt in (T.IntType, T.FloatType):
                expected = lt
            else:
                return
        else:
            return
        if not T.is_assignable(expected, instr.dest_type):
            self.fail(
                fn,
                index,
                f"binop '{op}' on {lt.display()} and {rt.display()} produces {expected.display()}, "
                f"but destination is {instr.dest_type.display()}",
            )


def verify_ir(module: IRModule) -> None:
    IRVerifier(module).verify()
