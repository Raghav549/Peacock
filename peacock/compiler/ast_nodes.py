"""Abstract syntax tree for PEACOCK 0.1.

Nodes are plain (non-slotted) dataclasses so the semantic analyser can attach
resolution information (``node.ty``, ``node.symbol``, ...) without copying trees.
Every node carries a :class:`~peacock.compiler.diagnostics.Span`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .diagnostics import Span


# ---------------------------------------------------------------------------
# Type syntax (unresolved)
# ---------------------------------------------------------------------------
@dataclass
class TypeExpr:
    span: Span


@dataclass
class NamedTypeExpr(TypeExpr):
    name: str
    args: list[TypeExpr] = field(default_factory=list)


@dataclass
class ListTypeExpr(TypeExpr):
    element: TypeExpr


@dataclass
class TensorTypeExpr(TypeExpr):
    dtype: str
    dtype_span: Span
    shape: list[int] | None
    shape_span: Span | None


@dataclass
class FunctionTypeExpr(TypeExpr):
    """Reserved for future first-class functions; parsed only inside errors."""

    params: list[TypeExpr]
    result: TypeExpr


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
@dataclass
class Expr:
    span: Span
    # Filled by the semantic analyser (not part of the constructor).
    ty: Any = field(default=None, init=False, repr=False)


@dataclass
class IntLit(Expr):
    value: int


@dataclass
class FloatLit(Expr):
    value: float


@dataclass
class StringLit(Expr):
    value: str


@dataclass
class BoolLit(Expr):
    value: bool


@dataclass
class Name(Expr):
    ident: str
    # Resolution metadata: kind in {"local", "function", "struct", "model",
    # "training", "native_namespace"}.
    resolution: str | None = None
    symbol: Any = None


@dataclass
class Unary(Expr):
    op: str
    operand: Expr


@dataclass
class Binary(Expr):
    op: str
    left: Expr
    right: Expr
    # Constant-folded value, if any.
    folded: Any = None


@dataclass
class RangeExpr(Expr):
    start: Expr
    end: Expr


@dataclass
class ListLit(Expr):
    elements: list[Expr]
    # If all elements share a type this is filled by inference.
    element_ty: Any = None


@dataclass
class Call(Expr):
    callee: Expr
    args: list[Expr]
    arg_names: list[str | None] = field(default_factory=list)
    # Resolution metadata set by the analyser:
    call_kind: str | None = None  # function | native | namespace | struct | method | model_method | training_method
    target: Any = None
    native_name: str | None = None
    native_sig: Any = None
    arg_order: list[int] = field(default_factory=list)


@dataclass
class Field(Expr):
    base: Expr
    name: str
    name_span: Span
    field_kind: str | None = None  # struct_field | namespace | property
    symbol: Any = None


@dataclass
class Index(Expr):
    base: Expr
    index: Expr


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------
@dataclass
class Stmt:
    span: Span
    # Definite-return flag filled by the analyser (not part of the constructor).
    always_returns: bool = field(default=False, init=False, repr=False)


@dataclass
class Block(Stmt):
    statements: list[Stmt]


@dataclass
class LetStmt(Stmt):
    name: str
    mutable: bool
    annotation: TypeExpr | None
    init: Expr
    slot: int = -1
    # Filled by semantic analysis for tooling and differential validation.
    ty: Any = None
    symbol: Any = None


@dataclass
class AssignStmt(Stmt):
    target: Expr
    op: str  # "=", "+=", ...
    value: Expr


@dataclass
class ExprStmt(Stmt):
    expr: Expr


@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_block: Block
    else_branch: Block | "IfStmt" | None


@dataclass
class WhileStmt(Stmt):
    condition: Expr
    body: Block


@dataclass
class ForStmt(Stmt):
    name: str
    iterable: Expr
    body: Block
    slot: int = -1


@dataclass
class ReturnStmt(Stmt):
    value: Expr | None


@dataclass
class BreakStmt(Stmt):
    pass


@dataclass
class ContinueStmt(Stmt):
    pass


@dataclass
class CapabilityStmt(Stmt):
    capabilities: list[str]
    spans: list[Span] = field(default_factory=list)


@dataclass
class ThrowStmt(Stmt):
    value: Expr


@dataclass
class TryStmt(Stmt):
    body: Block
    catch_name: str
    catch_body: Block
    slot: int = -1


@dataclass
class AssertStmt(Stmt):
    condition: Expr
    message: Expr | None


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------
@dataclass
class Param:
    name: str
    annotation: TypeExpr
    span: Span
    slot: int = -1
    ty: Any = None


@dataclass
class FunctionDecl:
    name: str
    params: list[Param]
    return_type: TypeExpr | None
    body: Block
    span: Span
    name_span: Span
    # Filled by semantic analysis:
    signature: Any = None
    capabilities: frozenset[str] = frozenset()
    slot_count: int = 0


@dataclass
class StructField:
    name: str
    annotation: TypeExpr
    span: Span
    ty: Any = None


@dataclass
class StructDecl:
    name: str
    fields: list[StructField]
    span: Span
    name_span: Span


@dataclass
class LayerDecl:
    name: str
    args: list["LayerArg"]
    span: Span


@dataclass
class LayerArg:
    name: str
    value: Expr
    span: Span
    # Set for bare symbolic arguments such as ``activation: relu``.
    symbol: str | None = None


@dataclass
class ModelDecl:
    name: str
    inputs: list[StructField]
    outputs: list[StructField]
    layers: list[LayerDecl]
    span: Span
    name_span: Span


@dataclass
class TrainingField:
    name: str
    value: Expr
    span: Span


@dataclass
class TrainingDecl:
    name: str
    fields: list[TrainingField]
    span: Span
    name_span: Span
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class UseDecl:
    path: list[str]
    span: Span
    alias: str | None = None


@dataclass
class Module:
    name: str | None
    uses: list[UseDecl]
    functions: list[FunctionDecl]
    structs: list[StructDecl]
    models: list[ModelDecl]
    trainings: list[TrainingDecl]
    span: Span
