"""Experimental bridge to the PEACOCK-written type-relation kernel.

`shadow_check` extracts supported type annotations from the already parsed AST,
constructs a PEACOCK test program, and runs that program in the VM. The Python
type model remains authoritative. This is deliberately a shadow-validation
switch, not a replacement semantic analyser: primitive relations, simple
`List<T>`, declared nominal structs and tensor relations are covered; names,
expression typing, diagnostics and scopes are not.
"""
from __future__ import annotations

import io
from pathlib import Path

from . import types as T
from .ast_nodes import ListTypeExpr, NamedTypeExpr, TensorTypeExpr


class SelfHostTypeMismatch(RuntimeError):
    """Raised when the PEACOCK relation kernel disagrees with the Python oracle."""


_PRIMITIVES = {
    "Int": T.IntType,
    "Float": T.FloatType,
    "Bool": T.BoolType,
    "String": T.StringType,
    "Unit": T.UnitType,
    "Never": T.NeverType,
}


def _adapt(expr, nominal_names=frozenset()):
    if isinstance(expr, NamedTypeExpr) and expr.name in _PRIMITIVES:
        return _PRIMITIVES[expr.name], f'primitive("{expr.name}")'
    if isinstance(expr, NamedTypeExpr) and expr.name in nominal_names:
        return T.StructType(expr.name), f'nominal_type("{expr.name}")'
    if isinstance(expr, ListTypeExpr) and isinstance(expr.element, NamedTypeExpr):
        element = expr.element.name
        primitive = _PRIMITIVES.get(element)
        if primitive is not None:
            return T.ListType(primitive), f'list_type("{element}")'
    if isinstance(expr, TensorTypeExpr):
        ty = T.TensorType(expr.dtype, tuple(expr.shape) if expr.shape is not None else None)
        if expr.shape is None:
            encoded = f'tensor_type("{expr.dtype}", false, [0])'
        else:
            dims = ", ".join(str(n) for n in expr.shape)
            encoded = f'tensor_type("{expr.dtype}", true, [{dims}])'
        return ty, encoded
    return None


def shadow_check(module) -> int:
    """Run type relation checks for eligible parsed declarations; return case count."""
    adapted = []
    nominal_names = frozenset(struct.name for struct in module.structs)
    for fn in module.functions:
        for param in fn.params:
            item = _adapt(param.annotation, nominal_names)
            if item is not None:
                adapted.append(item)
        if fn.return_type is not None:
            item = _adapt(fn.return_type, nominal_names)
            if item is not None:
                adapted.append(item)
    for struct in module.structs:
        for field in struct.fields:
            item = _adapt(field.annotation, nominal_names)
            if item is not None:
                adapted.append(item)

    if not adapted:
        return 0

    statements = []
    for src, src_expr in adapted:
        for target, target_expr in adapted:
            expected = T.is_assignable(src, target)
            negation = "" if expected else "not "
            statements.append(f"assert({negation}is_assignable({src_expr}, {target_expr}));")

    tensors = [(ty, expr) for ty, expr in adapted if isinstance(ty, T.TensorType)]
    for left, left_expr in tensors:
        for right, right_expr in tensors:
            expected = (
                left.shape is None
                or right.shape is None
                or T.broadcast_shapes(left.shape, right.shape) is not None
            )
            negation = "" if expected else "not "
            statements.append(f"assert({negation}broadcastable({left_expr}, {right_expr}));")

    repo_root = Path(__file__).resolve().parents[2]
    library = (repo_root / "selfhost" / "type_model.pac").read_text(encoding="utf-8")
    prefix = library[: library.index("fn main() -> Unit {")]
    source = prefix + "fn main() -> Unit {\n" + "\n".join(statements) + "\n}\n"

    # Local import avoids a module cycle: pipeline invokes us only after parsing.
    from .pipeline import compile_source
    from peacock.runtime.host import HostPolicy
    from peacock.runtime.vm import VM

    compiled = compile_source(source, "<selfhost-type-shadow>", semantic_mode="python")
    if not compiled.ok:
        raise SelfHostTypeMismatch(
            "generated type-shadow program failed to compile: "
            + compiled.diagnostics.render_all(source)
        )
    try:
        VM(compiled.image, HostPolicy(root=str(repo_root)), stdout=io.StringIO()).run()
    except Exception as exc:
        raise SelfHostTypeMismatch(
            f"PEACOCK type relation disagrees with Python oracle: {exc}"
        ) from exc
    return len(statements)
