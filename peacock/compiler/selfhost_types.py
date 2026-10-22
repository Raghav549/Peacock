"""Differential bridge to the PEACOCK-written semantic kernel.

The bridge is intentionally an oracle adapter, not a second implementation in
Python: it extracts already-parsed/typed facts, serialises type descriptors and
semantic events as PEACOCK source, then asks the real compiler and VM to execute
`selfhost/type_model.सूत्र`. The Python analyser remains authoritative. Probes cover
assignability/broadcasting, expression result types, local scopes and names,
declarations/assignments, conditions/returns, and user-function signatures.

Unsupported semantic forms (notably struct-field lookup, native overloads,
methods, model/training declarations and diagnostic rendering) are not silently
claimed as migrated; they are skipped until a later migration increment.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from peacock.sanskrit import INTERNAL_TO_SOURCE, LEGACY_KEYWORDS

from . import types as T
from .ast_nodes import (
    AssertStmt,
    AssignStmt,
    Binary,
    Block,
    BreakStmt,
    Call,
    CapabilityStmt,
    ContinueStmt,
    Expr,
    ExprStmt,
    Field,
    ForStmt,
    FunctionDecl,
    IfStmt,
    Index,
    LetStmt,
    ListLit,
    Name,
    RangeExpr,
    ReturnStmt,
    ThrowStmt,
    TryStmt,
    Unary,
    WhileStmt,
)


class SelfHostTypeMismatch(RuntimeError):
    """Raised when the PEACOCK semantic kernel disagrees with its Python oracle."""


_MAX_TYPES = 128
_MAX_PROBES = 20_000
_GENERATED_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _native_generated(source: str) -> str:
    """Render internally generated probe IR with the canonical Sanskrit notation.

    This is an emitter, not a legacy-source acceptance path.  Probe facts may
    contain internal type and identifier names; every one is rendered back to
    its native spelling before the real Sanskrit compiler sees the program.
    """

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        return INTERNAL_TO_SOURCE.get(word, LEGACY_KEYWORDS.get(word, word))

    return _GENERATED_WORD.sub(replace, source)


def _quote(text: str) -> str:
    """Quote a Python string as a PEACOCK string literal."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\0", "\\0")
    )
    return f'"{escaped}"'


def _type_expr(ty: T.Type | None) -> str:
    """Render a bootstrap type as a PEACOCK `TypeDesc` expression."""
    if ty is None or ty is T.ErrorType:
        return "error_type()"
    if isinstance(ty, T.PrimitiveType):
        return f"primitive({_quote(ty.name)})"
    if isinstance(ty, T.TensorType):
        known = ty.shape is not None
        dims = "[" + ", ".join(str(dim) for dim in (ty.shape or ())) + "]"
        return f"tensor_type({_quote(ty.dtype)}, {'true' if known else 'false'}, {dims})"
    if isinstance(ty, T.ListType):
        return f"list_type({_type_expr(ty.element)})"
    if isinstance(ty, T.StructType):
        return f"nominal_type({_quote(ty.name)})"
    if isinstance(ty, T.ModelDeclType):
        return f"opaque_type({_quote('model:' + ty.name)})"
    if isinstance(ty, T.TrainingDeclType):
        return f"opaque_type({_quote('training:' + ty.name)})"
    if isinstance(ty, T.OpaqueType):
        return f"opaque_type({_quote(ty.name)})"
    # Defensive recovery for a future type that has not yet been migrated.
    return "error_type()"


def _collect_expr_types(expr: Expr, found: list[T.Type]) -> None:
    if expr.ty is not None and expr.ty not in found:
        found.append(expr.ty)
    if isinstance(expr, Unary):
        _collect_expr_types(expr.operand, found)
    elif isinstance(expr, Binary):
        _collect_expr_types(expr.left, found)
        _collect_expr_types(expr.right, found)
    elif isinstance(expr, RangeExpr):
        _collect_expr_types(expr.start, found)
        _collect_expr_types(expr.end, found)
    elif isinstance(expr, ListLit):
        for child in expr.elements:
            _collect_expr_types(child, found)
    elif isinstance(expr, Call):
        _collect_expr_types(expr.callee, found)
        for child in expr.args:
            _collect_expr_types(child, found)
    elif isinstance(expr, Field):
        _collect_expr_types(expr.base, found)
    elif isinstance(expr, Index):
        _collect_expr_types(expr.base, found)
        _collect_expr_types(expr.index, found)


def _collect_block_types(block: Block, found: list[T.Type]) -> None:
    for stmt in block.statements:
        if isinstance(stmt, LetStmt):
            if stmt.ty is not None and stmt.ty not in found:
                found.append(stmt.ty)
            _collect_expr_types(stmt.init, found)
        elif isinstance(stmt, AssignStmt):
            _collect_expr_types(stmt.target, found)
            _collect_expr_types(stmt.value, found)
        elif isinstance(stmt, ExprStmt):
            _collect_expr_types(stmt.expr, found)
        elif isinstance(stmt, IfStmt):
            _collect_expr_types(stmt.condition, found)
            _collect_block_types(stmt.then_block, found)
            if isinstance(stmt.else_branch, Block):
                _collect_block_types(stmt.else_branch, found)
            elif isinstance(stmt.else_branch, IfStmt):
                _collect_block_types(Block(stmt.else_branch.span, [stmt.else_branch]), found)
        elif isinstance(stmt, WhileStmt):
            _collect_expr_types(stmt.condition, found)
            _collect_block_types(stmt.body, found)
        elif isinstance(stmt, ForStmt):
            _collect_expr_types(stmt.iterable, found)
            _collect_block_types(stmt.body, found)
        elif isinstance(stmt, ReturnStmt) and stmt.value is not None:
            _collect_expr_types(stmt.value, found)
        elif isinstance(stmt, ThrowStmt):
            _collect_expr_types(stmt.value, found)
        elif isinstance(stmt, TryStmt):
            _collect_block_types(stmt.body, found)
            _collect_block_types(stmt.catch_body, found)
        elif isinstance(stmt, AssertStmt):
            _collect_expr_types(stmt.condition, found)
            if stmt.message is not None:
                _collect_expr_types(stmt.message, found)
        elif isinstance(stmt, Block):
            _collect_block_types(stmt, found)


def _diagnostic_at(diagnostics, span, code: str, message_prefix: str | None = None) -> bool:
    for diagnostic in diagnostics:
        if diagnostic.code != code or diagnostic.span.start != span.start:
            continue
        if message_prefix is None or diagnostic.message.startswith(message_prefix):
            return True
    return False


def _declared_ok(diagnostics, name: str, span, *, parameter: bool = False) -> bool:
    if name == "_":
        return True
    if parameter:
        prefix = f"duplicate parameter '{name}'"
    else:
        prefix = f"variable '{name}' is already declared in this scope"
    return not _diagnostic_at(diagnostics, span, "PE3001", prefix)


def _error_or_bool(value: bool) -> str:
    return "true" if value else "false"


class _FunctionProbeEmitter:
    """Emit ordered scope/expression probes for one already-analysed function."""

    def __init__(self, function, diagnostics, signatures_name: str, function_index: int, next_scope_id: int):
        self.function = function
        self.diagnostics = diagnostics
        self.signatures_name = signatures_name
        self.function_index = function_index
        self.lines: list[str] = []
        self.cases = 0
        self.next_scope_id = next_scope_id
        self.bindings = f"__shadow_bindings_{function_index}"
        self.scopes = f"__shadow_scopes_{function_index}"

    def _assert(self, condition: str) -> None:
        self.lines.append(f"    assert({condition});")
        self.cases += 1

    def _declare(self, name: str, ty: T.Type, mutable: bool, span, *, parameter: bool = False) -> None:
        expected = _declared_ok(self.diagnostics, name, span, parameter=parameter)
        self._assert(
            f"declare({self.bindings}, {self.scopes}, {_quote(name)}, "
            f"{_type_expr(ty)}, {'true' if mutable else 'false'}) == {_error_or_bool(expected)}"
        )

    def _new_scope(self) -> None:
        scope_id = self.next_scope_id
        self.next_scope_id += 1
        self.lines.append(f"    {self.scopes}.push({scope_id});")

    def _end_scope(self) -> None:
        self.lines.append(f"    {self.scopes}.pop();")

    def emit(self) -> tuple[list[str], int, int]:
        self.lines.extend(
            [
                f"    let mut {self.bindings}: List<Binding> = [];",
                f"    let mut {self.scopes}: List<Int> = [0];",
            ]
        )
        for param in self.function.decl.params:
            self._declare(param.name, param.ty or T.ErrorType, False, param.span, parameter=True)
        self._emit_block(self.function.decl.body, new_scope=False)
        return self.lines, self.cases, self.next_scope_id

    def _emit_name(self, expr: Name) -> None:
        if expr.resolution == "local" and expr.symbol is not None:
            index = f"lookup_index({self.bindings}, {self.scopes}, {_quote(expr.ident)})"
            self._assert(f"{index} >= 0")
            self._assert(
                f"type_equal(resolved_type({self.bindings}, {self.scopes}, {_quote(expr.ident)}), "
                f"{_type_expr(expr.symbol.ty)})"
            )
        elif expr.resolution == "unknown":
            self._assert(
                f"lookup_index({self.bindings}, {self.scopes}, {_quote(expr.ident)}) == -1"
            )

    def _emit_call_probe(self, expr: Call) -> None:
        if expr.call_kind != "function" or not isinstance(expr.target, object):
            return
        target = expr.target
        if not hasattr(target, "param_types") or not hasattr(target, "decl"):
            return
        ordered: list[T.Type] = []
        for source_index in expr.arg_order:
            if source_index < 0 or source_index >= len(expr.args):
                return
            ordered.append(expr.args[source_index].ty or T.ErrorType)
        argument_list = "[" + ", ".join(_type_expr(ty) for ty in ordered) + "]"
        call_result = f"check_call(__shadow_functions, {_quote(target.name)}, {argument_list})"
        arg_mismatch = False
        for diagnostic in self.diagnostics:
            if diagnostic.code != "PE3003" or not diagnostic.message.startswith("argument '"):
                continue
            if f"of '{target.name}'" not in diagnostic.message:
                continue
            if any(diagnostic.span.start == arg.span.start for arg in expr.args):
                arg_mismatch = True
                break
        if arg_mismatch:
            self._assert(f"is_error({call_result})")
        else:
            self._assert(f"type_equal({call_result}, {_type_expr(expr.ty)})")

    def _emit_expr(self, expr: Expr | None) -> None:
        if expr is None:
            return
        if isinstance(expr, Name):
            self._emit_name(expr)
            return
        if isinstance(expr, Unary):
            self._emit_expr(expr.operand)
            self._assert(
                f"type_equal(infer_unary({_quote(expr.op)}, {_type_expr(expr.operand.ty)}), "
                f"{_type_expr(expr.ty)})"
            )
            return
        if isinstance(expr, Binary):
            self._emit_expr(expr.left)
            self._emit_expr(expr.right)
            self._assert(
                f"type_equal(infer_binary({_quote(expr.op)}, {_type_expr(expr.left.ty)}, "
                f"{_type_expr(expr.right.ty)}), {_type_expr(expr.ty)})"
            )
            return
        if isinstance(expr, RangeExpr):
            self._emit_expr(expr.start)
            self._emit_expr(expr.end)
            self._assert(f"type_equal(range_type(), {_type_expr(expr.ty)})")
            # The bootstrap recovers from an invalid bound but reports a
            # PE3003. Compare this independent rule only if both operands have
            # non-error types (otherwise the child owns the primary error).
            if expr.start.ty is not T.ErrorType and expr.end.ty is not T.ErrorType:
                expected = expr.start.ty == T.IntType and expr.end.ty == T.IntType
                self._assert(
                    f"valid_range_bounds({_type_expr(expr.start.ty)}, {_type_expr(expr.end.ty)}) == "
                    f"{_error_or_bool(expected)}"
                )
            return
        if isinstance(expr, ListLit):
            for child in expr.elements:
                self._emit_expr(child)
            has_expected = not expr.elements and isinstance(expr.ty, T.ListType)
            expected_element = expr.ty.element if has_expected else T.ErrorType
            element_types = "[" + ", ".join(_type_expr(child.ty) for child in expr.elements) + "]"
            self._assert(
                f"type_equal(infer_list({element_types}, {'true' if has_expected else 'false'}, "
                f"{_type_expr(expected_element)}), {_type_expr(expr.ty)})"
            )
            return
        if isinstance(expr, Index):
            self._emit_expr(expr.base)
            self._emit_expr(expr.index)
            self._assert(
                f"type_equal(infer_index({_type_expr(expr.base.ty)}, {_type_expr(expr.index.ty)}), "
                f"{_type_expr(expr.ty)})"
            )
            return
        if isinstance(expr, Field):
            # Field resolution is a separate next increment. Still exercise any
            # local/name and call probes in the receiver expression.
            self._emit_expr(expr.base)
            return
        if isinstance(expr, Call):
            self._emit_expr(expr.callee)
            for child in expr.args:
                self._emit_expr(child)
            self._emit_call_probe(expr)

    def _emit_block(self, block: Block, *, new_scope: bool) -> None:
        if new_scope:
            self._new_scope()
        for stmt in block.statements:
            self._emit_stmt(stmt)
        if new_scope:
            self._end_scope()

    def _emit_stmt(self, stmt) -> None:
        if isinstance(stmt, LetStmt):
            self._emit_expr(stmt.init)
            if stmt.ty is not None:
                initializer_mismatch = any(
                    diagnostic.code == "PE3003"
                    and diagnostic.span.start in (stmt.init.span.start, stmt.annotation.span.start if stmt.annotation else -1)
                    and (
                        diagnostic.message.startswith("cannot initialise")
                        or diagnostic.message.startswith("cannot infer a type")
                        or diagnostic.message.startswith("variables may not have type Unit")
                    )
                    for diagnostic in self.diagnostics
                )
                expected = not initializer_mismatch
                self._assert(
                    f"variable_initializer_compatible({_type_expr(stmt.init.ty)}, {_type_expr(stmt.ty)}) == "
                    f"{_error_or_bool(expected)}"
                )
                self._declare(stmt.name, stmt.ty, stmt.mutable, stmt.span)
            return
        if isinstance(stmt, AssignStmt):
            if isinstance(stmt.target, Name):
                self._emit_name(stmt.target)
            elif isinstance(stmt.target, Field):
                self._emit_expr(stmt.target.base)
            elif isinstance(stmt.target, Index):
                self._emit_expr(stmt.target.base)
                self._emit_expr(stmt.target.index)
            self._emit_expr(stmt.value)
            if isinstance(stmt.target, Name) and stmt.target.resolution == "local" and stmt.target.symbol is not None:
                current_ty = stmt.target.ty
                if current_ty is not T.ErrorType:
                    symbol = stmt.target.symbol
                    if not symbol.mutable:
                        expected_status = "immutable"
                    elif stmt.op == "=":
                        expected_status = "ok" if T.is_assignable(stmt.value.ty, current_ty) else "type"
                    else:
                        expected_status = (
                            "type"
                            if _diagnostic_at(self.diagnostics, stmt.span, "PE3003", "compound assignment")
                            or _diagnostic_at(self.diagnostics, stmt.span, "PE3003", "operator '")
                            else "ok"
                        )
                    operation = "=" if stmt.op == "=" else stmt.op[:-1]
                    self._assert(
                        f"assignment_status({self.bindings}, {self.scopes}, {_quote(stmt.target.ident)}, "
                        f"{_type_expr(stmt.value.ty)}, {_quote(operation)}) == {_quote(expected_status)}"
                    )
            elif stmt.target.ty is not None and stmt.target.ty is not T.ErrorType:
                if stmt.op == "=":
                    expected = T.is_assignable(stmt.value.ty, stmt.target.ty)
                    self._assert(
                        f"is_assignable({_type_expr(stmt.value.ty)}, {_type_expr(stmt.target.ty)}) == "
                        f"{_error_or_bool(expected)}"
                    )
            return
        if isinstance(stmt, ExprStmt):
            self._emit_expr(stmt.expr)
            return
        if isinstance(stmt, IfStmt):
            self._emit_expr(stmt.condition)
            expected = stmt.condition.ty in (T.BoolType, T.ErrorType)
            self._assert(
                f"condition_compatible({_type_expr(stmt.condition.ty)}) == {_error_or_bool(expected)}"
            )
            self._emit_block(stmt.then_block, new_scope=True)
            if isinstance(stmt.else_branch, Block):
                self._emit_block(stmt.else_branch, new_scope=True)
            elif isinstance(stmt.else_branch, IfStmt):
                self._emit_stmt(stmt.else_branch)
            return
        if isinstance(stmt, WhileStmt):
            self._emit_expr(stmt.condition)
            expected = stmt.condition.ty in (T.BoolType, T.ErrorType)
            self._assert(
                f"condition_compatible({_type_expr(stmt.condition.ty)}) == {_error_or_bool(expected)}"
            )
            self._emit_block(stmt.body, new_scope=True)
            return
        if isinstance(stmt, ForStmt):
            self._emit_expr(stmt.iterable)
            iterable_ty = stmt.iterable.ty
            expected_supported = (
                iterable_ty is T.ErrorType
                or isinstance(iterable_ty, T.ListType)
                or iterable_ty == T.RangeType
            )
            self._assert(
                f"iterable_supported({_type_expr(iterable_ty)}) == {_error_or_bool(expected_supported)}"
            )
            element_type = None
            if isinstance(iterable_ty, T.ListType):
                element_type = iterable_ty.element
            elif iterable_ty == T.RangeType:
                element_type = T.IntType
            self._new_scope()
            if element_type is not None:
                self._declare(stmt.name, element_type, False, stmt.span)
            self._emit_block(stmt.body, new_scope=False)
            self._end_scope()
            return
        if isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                self._emit_expr(stmt.value)
            function = self.function
            expected_valid = not any(
                diagnostic.code == "PE3008"
                and diagnostic.span.start in (
                    stmt.span.start,
                    stmt.value.span.start if stmt.value is not None else -1,
                )
                for diagnostic in self.diagnostics
            )
            self._assert(
                f"return_compatible({_type_expr(stmt.value.ty if stmt.value is not None else T.UnitType)}, "
                f"{_type_expr(function.return_type)}, {'true' if stmt.value is not None else 'false'}) == "
                f"{_error_or_bool(expected_valid)}"
            )
            return
        if isinstance(stmt, ThrowStmt):
            self._emit_expr(stmt.value)
            expected = stmt.value.ty is T.ErrorType or stmt.value.ty == T.StringType
            self._assert(
                f"is_assignable({_type_expr(stmt.value.ty)}, primitive(\"String\")) == "
                f"{_error_or_bool(expected)}"
            )
            return
        if isinstance(stmt, TryStmt):
            self._emit_block(stmt.body, new_scope=True)
            self._new_scope()
            self._declare(stmt.catch_name, T.StringType, False, stmt.span)
            self._emit_block(stmt.catch_body, new_scope=False)
            self._end_scope()
            return
        if isinstance(stmt, AssertStmt):
            self._emit_expr(stmt.condition)
            expected = stmt.condition.ty in (T.BoolType, T.ErrorType)
            self._assert(
                f"condition_compatible({_type_expr(stmt.condition.ty)}) == {_error_or_bool(expected)}"
            )
            if stmt.message is not None:
                self._emit_expr(stmt.message)
                expected_message = stmt.message.ty is T.ErrorType or stmt.message.ty == T.StringType
                self._assert(
                    f"is_assignable({_type_expr(stmt.message.ty)}, primitive(\"String\")) == "
                    f"{_error_or_bool(expected_message)}"
                )
            return
        if isinstance(stmt, Block):
            self._emit_block(stmt, new_scope=True)
            return
        if isinstance(stmt, (BreakStmt, ContinueStmt, CapabilityStmt)):
            return


def _make_type_relation_probes(types: list[T.Type]) -> tuple[list[str], int]:
    unique: list[T.Type] = []
    for ty in types:
        if ty not in unique:
            unique.append(ty)
    if len(unique) > _MAX_TYPES:
        raise SelfHostTypeMismatch(
            f"shadow semantic probe contains {len(unique)} distinct types; limit is {_MAX_TYPES}"
        )
    lines: list[str] = []
    cases = 0
    for source in unique:
        for target in unique:
            expected = T.is_assignable(source, target)
            lines.append(
                f"    assert(is_assignable({_type_expr(source)}, {_type_expr(target)}) == "
                f"{_error_or_bool(expected)});"
            )
            cases += 1
    tensors = [ty for ty in unique if isinstance(ty, T.TensorType)]
    for left in tensors:
        for right in tensors:
            expected = (
                left.shape is None
                or right.shape is None
                or T.broadcast_shapes(left.shape, right.shape) is not None
            )
            lines.append(
                f"    assert(broadcastable({_type_expr(left)}, {_type_expr(right)}) == "
                f"{_error_or_bool(expected)});"
            )
            cases += 1
    return lines, cases


def shadow_check(module, typed) -> dict[str, int]:
    """Run PEACOCK-side semantic probes extracted from the typed AST.

    Returns separate relation and semantic probe counts for the compiler stats
    and benchmark/debug interfaces. A disagreement is an internal compiler
    error in shadow mode; it never changes ordinary compilation diagnostics.
    """
    from .pipeline import compile_source
    from peacock.runtime.host import HostPolicy
    from peacock.runtime.vm import VM

    types: list[T.Type] = []
    for signature in typed.functions.values():
        for ty in signature.param_types + [signature.return_type]:
            if ty not in types:
                types.append(ty)
    for struct in typed.structs.values():
        for ty in struct.field_types:
            if ty not in types:
                types.append(ty)
    for function in module.functions:
        if typed.functions.get(function.name) is not None and typed.functions[function.name].decl is function:
            _collect_block_types(function.body, types)
            for param in function.params:
                if param.ty is not None and param.ty not in types:
                    types.append(param.ty)

    type_lines, type_cases = _make_type_relation_probes(types)
    main_lines: list[str] = [
        '    स्थापय __shadow_builtin_cases = run_builtin_checks();',
        '    स्थापय परिवर्तनीय __shadow_functions: सूची<FunctionSignature> = [];',
    ]
    for signature in typed.functions.values():
        param_names = "[" + ", ".join(_quote(param.name) for param in signature.decl.params) + "]"
        param_types = "[" + ", ".join(_type_expr(ty) for ty in signature.param_types) + "]"
        main_lines.append(
            "    __shadow_functions.push(FunctionSignature("
            f"{_quote(signature.name)}, {param_names}, {param_types}, {_type_expr(signature.return_type)}));"
        )

    semantic_cases = 0
    next_scope_id = 1
    for index, function in enumerate(module.functions):
        signature = typed.functions.get(function.name)
        if signature is None or signature.decl is not function:
            continue
        emitter = _FunctionProbeEmitter(
            signature,
            typed.diagnostics,
            "__shadow_functions",
            index,
            next_scope_id,
        )
        emitted, cases, next_scope_id = emitter.emit()
        main_lines.extend(emitted)
        semantic_cases += cases

    if type_cases + semantic_cases > _MAX_PROBES:
        raise SelfHostTypeMismatch(
            f"shadow semantic probe contains {type_cases + semantic_cases} checks; limit is {_MAX_PROBES}"
        )
    if type_lines:
        main_lines[1:1] = type_lines
    generated = 'कार्य मुख्य() -> एकक {\n' + "\n".join(main_lines) + "\n}\n"
    generated = _native_generated(generated)

    repo_root = Path(__file__).resolve().parents[2]
    library_path = repo_root / "selfhost" / "type_model.सूत्र"
    library = library_path.read_text(encoding="utf-8")
    marker = 'कार्य मुख्य() -> एकक {'
    main_start = library.find(marker)
    if main_start < 0:
        raise SelfHostTypeMismatch(f"{library_path} does not define its test main")
    source = library[:main_start] + generated

    compiled = compile_source(source, "<selfhost-semantic-shadow>", semantic_mode="python")
    if not compiled.ok:
        raise SelfHostTypeMismatch(
            "generated semantic-shadow program failed to compile: "
            + compiled.diagnostics.render_all(source)
        )
    try:
        VM(
            compiled.image,
            HostPolicy(root=str(repo_root), max_steps=10_000_000),
            stdout=io.StringIO(),
        ).run()
    except Exception as exc:
        raise SelfHostTypeMismatch(
            f"PEACOCK semantic kernel disagrees with Python oracle: {exc}"
        ) from exc
    return {
        "type_cases": type_cases,
        "semantic_cases": semantic_cases,
        "builtin_cases": 55,
    }
