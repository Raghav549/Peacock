"""Canonical AST digest for differential testing against the self-hosted parser.

The self-hosted parser (`selfhost/parser.सूत्र`) prints this exact S-expression
format. This module produces the same text from the bootstrap AST, which is the
oracle. It is test infrastructure, not part of the language implementation.
"""

from __future__ import annotations

from peacock.compiler import ast_nodes as A
from peacock.compiler.pipeline import compile_source
from peacock.sanskrit import (
    INTERNAL_TO_SOURCE,
    LEGACY_KEYWORDS,
    devanagari_digits,
)


_AST_LABELS = {
    "ann": "प्रकाराङ्कन",
    "arg": "तर्क",
    "assign": "नियोजन",
    "b": "द्वि",
    "block": "खण्ड",
    "call": "आह्वान",
    "cap": "अधिकार",
    "error": "दोष",
    "expr": "अभिव्यक्ति",
    "field": "क्षेत्र",
    "layer": "स्तर",
    "list": "सूची",
    "opt": "विकल्प",
    "param": "प्राचल",
    "params": "प्राचलावली",
    "ret": "प्रत्यागत",
    "sym": "प्रतीक",
    "t": "प्रकार",
    "tylist": "सूचीप्रकार",
    "u": "एक",
}


def _source_word(word: str) -> str:
    return INTERNAL_TO_SOURCE.get(word, LEGACY_KEYWORDS.get(word, word))


def node(name: str, *parts: str) -> str:
    # Declaration labels and value identifiers have separate namespaces: the
    # former is `model` -> प्रतिमान, the latter `model` -> प्रतिमानमूल्य.
    name = _AST_LABELS.get(name, LEGACY_KEYWORDS.get(name, _source_word(name)))
    parts = tuple(_source_word(part) for part in parts)
    if parts:
        return "(" + name + " " + " ".join(parts) + ")"
    return "(" + name + ")"


def type_digest(ty: A.TypeExpr) -> str:
    if isinstance(ty, A.NamedTypeExpr):
        return node("t", ty.name, *[type_digest(a) for a in ty.args])
    if isinstance(ty, A.ListTypeExpr):
        return node("tylist", type_digest(ty.element))
    if isinstance(ty, A.TensorTypeExpr):
        parts = ["tensor", ty.dtype]
        if ty.shape is not None:
            parts.append(node("shape", *[devanagari_digits(d) for d in ty.shape]))
        return node(*parts)
    raise ValueError(f"unsupported type in corpus: {type(ty).__name__}")


def expr_digest(e: A.Expr) -> str:
    if isinstance(e, A.IntLit):
        return node("int")
    if isinstance(e, A.FloatLit):
        return node("float")
    if isinstance(e, A.StringLit):
        return node("str")
    if isinstance(e, A.BoolLit):
        return node("true" if e.value else "false")
    if isinstance(e, A.Name):
        return node("name", e.ident)
    if isinstance(e, A.Unary):
        return node("u", e.op, expr_digest(e.operand))
    if isinstance(e, A.Binary):
        return node("b", e.op, expr_digest(e.left), expr_digest(e.right))
    if isinstance(e, A.RangeExpr):
        return node("range", expr_digest(e.start), expr_digest(e.end))
    if isinstance(e, A.ListLit):
        return node("list", *[expr_digest(x) for x in e.elements])
    if isinstance(e, A.Call):
        args = []
        for name, arg in zip(e.arg_names, e.args):
            args.append(node("arg", name if name is not None else "_", expr_digest(arg)))
        return node("call", expr_digest(e.callee), *args)
    if isinstance(e, A.Field):
        return node("field", expr_digest(e.base), e.name)
    if isinstance(e, A.Index):
        return node("index", expr_digest(e.base), expr_digest(e.index))
    raise ValueError(f"unsupported expression in corpus: {type(e).__name__}")


def stmt_digest(s: A.Stmt) -> str:
    if isinstance(s, A.Block):
        return node("block", *[stmt_digest(x) for x in s.statements])
    if isinstance(s, A.LetStmt):
        parts = []
        if s.mutable:
            parts.append("mut")
        parts.append(s.name)
        if s.annotation is not None:
            parts.append(node("ann", type_digest(s.annotation)))
        parts.append(expr_digest(s.init))
        return node("let", *parts)
    if isinstance(s, A.AssignStmt):
        return node("assign", s.op, expr_digest(s.target), expr_digest(s.value))
    if isinstance(s, A.ExprStmt):
        return node("expr", expr_digest(s.expr))
    if isinstance(s, A.IfStmt):
        parts = ["if", expr_digest(s.condition), stmt_digest(s.then_block)]
        if s.else_branch is not None:
            parts.append(stmt_digest(s.else_branch))
        return node(*parts)
    if isinstance(s, A.WhileStmt):
        return node("while", expr_digest(s.condition), stmt_digest(s.body))
    if isinstance(s, A.ForStmt):
        return node("for", s.name, expr_digest(s.iterable), stmt_digest(s.body))
    if isinstance(s, A.ReturnStmt):
        return node("return", *([expr_digest(s.value)] if s.value is not None else []))
    if isinstance(s, A.BreakStmt):
        return node("break")
    if isinstance(s, A.ContinueStmt):
        return node("continue")
    if isinstance(s, A.CapabilityStmt):
        return node("cap", *s.capabilities)
    if isinstance(s, A.ThrowStmt):
        return node("throw", expr_digest(s.value))
    if isinstance(s, A.TryStmt):
        return node("try", stmt_digest(s.body), s.catch_name, stmt_digest(s.catch_body))
    if isinstance(s, A.AssertStmt):
        parts = ["assert", expr_digest(s.condition)]
        if s.message is not None:
            parts.append(expr_digest(s.message))
        return node(*parts)
    raise ValueError(f"unsupported statement in corpus: {type(s).__name__}")


def layer_digest(layer: A.LayerDecl) -> str:
    args = []
    for arg in layer.args:
        if arg.symbol is not None:
            value = node("sym", arg.symbol)
        else:
            value = expr_digest(arg.value)
        args.append(node("arg", arg.name, value))
    return node("layer", layer.name, *args)


def model_digest(model: A.ModelDecl) -> str:
    parts = [model.name]
    for field in model.inputs:
        parts.append(node("input", field.name, type_digest(field.annotation)))
    for field in model.outputs:
        parts.append(node("output", field.name, type_digest(field.annotation)))
    parts.append(node("stack", *[layer_digest(layer) for layer in model.layers]))
    return node("model", *parts)


def training_digest(training: A.TrainingDecl) -> str:
    options = [
        node("opt", field.name, expr_digest(field.value)) for field in training.fields
    ]
    return node("training", training.name, *options)


def module_digest(source: str, path: str = "<selfhost-corpus>") -> str:
    result = compile_source(source, path)
    if not result.ok:
        raise ValueError(result.diagnostics.render_all(source))
    module = result.module
    assert module is not None
    lines = [node("module", module.name or "")]
    for use in module.uses:
        path_text = ".".join(use.path)
        lines.append(node("use", path_text, *(["as", use.alias] if use.alias else [])))
    for struct in module.structs:
        fields = [
            node("field", f.name, type_digest(f.annotation)) for f in struct.fields
        ]
        lines.append(node("struct", struct.name, *fields))
    for fn in module.functions:
        params = node(
            "params",
            *[node("param", p.name, type_digest(p.annotation)) for p in fn.params],
        )
        ret = type_digest(fn.return_type) if fn.return_type is not None else node("t", "Unit")
        lines.append(node("fn", fn.name, params, node("ret", ret), stmt_digest(fn.body)))
    for model in module.models:
        lines.append(model_digest(model))
    for training in module.trainings:
        lines.append(training_digest(training))
    return "\n".join(lines)
