"""Name resolution, type checking and capability checking for PEACOCK 0.3.

The analyser annotates the AST in place (``expr.ty``, ``name.symbol``,
``call.target``, ...) and returns a :class:`TypedProgram` that the IR builder
consumes. It never executes user code.

Static rules worth calling out:

* no implicit ``Int`` ↔ ``Float`` conversions;
* capability requirements are checked against the *declared* capabilities of the
  enclosing function (the runtime re-checks them against host grants);
* a model must have exactly one input and one output tensor with statically
  known shapes in 0.3;
* training option values are compile-time literals.
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
    LayerDecl,
    LetStmt,
    ListLit,
    ListTypeExpr,
    Name,
    NamedTypeExpr,
    RangeExpr,
    ReturnStmt,
    Stmt,
    StringLit,
    StructDecl,
    TensorTypeExpr,
    ThrowStmt,
    TrainingDecl,
    TryStmt,
    Unary,
    WhileStmt,
)
from peacock.sanskrit import internalise_enum, surface, surface_enum, surface_type

from .diagnostics import DiagnosticBag, Span
from .tokens import KNOWN_CAPABILITIES, KNOWN_NAMESPACES

_PRIMITIVES = {
    "Int": T.IntType,
    "Float": T.FloatType,
    "Bool": T.BoolType,
    "String": T.StringType,
    "Unit": T.UnitType,
    "Never": T.NeverType,
}

_OPAQUE = {
    "Color": T.ColorType,
    "Canvas": T.CanvasType,
    "Model": T.ModelType,
    "Dataset": T.DatasetType,
    "Range": T.RangeType,
    "UI": T.UIType,
    "Scene3D": T.Scene3DType,
    "Agent": T.AgentType,
}

_ACTIVATIONS = {"relu", "sigmoid", "tanh", "softmax", "linear"}
_OBJECTIVES = {"cross_entropy", "mse"}
_OPTIMISERS = {"sgd", "adam"}


@dataclass
class LocalSymbol:
    name: str
    ty: T.Type
    mutable: bool
    slot: int
    span: Span
    used: bool = False


@dataclass
class FunctionSymbol:
    name: str
    decl: FunctionDecl
    param_types: list[T.Type]
    return_type: T.Type
    capabilities: frozenset[str] = frozenset()


@dataclass
class StructSymbol:
    name: str
    decl: StructDecl
    field_names: list[str] = field(default_factory=list)
    field_types: list[T.Type] = field(default_factory=list)

    def field_index(self, name: str) -> int:
        return self.field_names.index(name)


@dataclass
class ResolvedLayer:
    kind: str
    units: int
    activation: str


@dataclass
class ModelSymbol:
    name: str
    decl: Any
    input_type: T.TensorType
    output_type: T.TensorType
    layers: list[ResolvedLayer] = field(default_factory=list)


@dataclass
class TrainingSymbol:
    name: str
    decl: TrainingDecl
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TypedProgram:
    module: Any
    functions: dict[str, FunctionSymbol]
    structs: dict[str, StructSymbol]
    models: dict[str, ModelSymbol]
    trainings: dict[str, TrainingSymbol]
    namespaces: frozenset[str]
    diagnostics: DiagnosticBag

    @property
    def main(self) -> FunctionSymbol | None:
        return self.functions.get("main")


class SemanticAnalyzer:
    def __init__(self, module, diag: DiagnosticBag | None = None):
        self.module = module
        self.diag = diag if diag is not None else DiagnosticBag()
        self.functions: dict[str, FunctionSymbol] = {}
        self.structs: dict[str, StructSymbol] = {}
        self.models: dict[str, ModelSymbol] = {}
        self.trainings: dict[str, TrainingSymbol] = {}
        self.namespaces: set[str] = set()
        self.scopes: list[dict[str, LocalSymbol]] = []
        self.current_function: FunctionSymbol | None = None
        self.next_slot = 0
        self.max_slots = 0
        self.loop_depth = 0

    # -- utilities ---------------------------------------------------------
    def _error(self, code: str, message: str, span: Span, hint: str | None = None) -> T.PrimitiveType:
        self.diag.error(code, message, span, hint)
        return T.ErrorType

    def _is_error(self, ty: T.Type) -> bool:
        return ty is T.ErrorType

    def _suggest(self, name: str, candidates) -> str | None:
        best: tuple[int, str] | None = None
        for candidate in candidates:
            d = _edit_distance(name.lower(), candidate.lower())
            if d <= 2 and (best is None or d < best[0]):
                best = (d, candidate)
        if best is None:
            return None
        return best[1]

    def _push_scope(self) -> None:
        self.scopes.append({})

    def _pop_scope(self) -> None:
        scope = self.scopes.pop()
        for symbol in scope.values():
            if not symbol.used and symbol.name != "_":
                self.diag.warning(
                    "PE3100",
                    f"unused variable '{symbol.name}'",
                    symbol.span,
                    hint="prefix with '_' if intentional",
                )

    def _declare(self, name: str, ty: T.Type, mutable: bool, span: Span) -> LocalSymbol:
        scope = self.scopes[-1]
        if name != "_" and name in scope:
            prev = scope[name]
            self.diag.error(
                "PE3001",
                f"variable '{name}' is already declared in this scope",
                span,
                notes=[f"previous declaration at line {prev.span.line}"],
            )
        slot = self.next_slot
        self.next_slot += 1
        self.max_slots = max(self.max_slots, self.next_slot)
        symbol = LocalSymbol(name, ty, mutable, slot, span)
        if name != "_":
            scope[name] = symbol
        return symbol

    def _lookup_local(self, name: str) -> LocalSymbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # -- entry point -------------------------------------------------------
    def analyze(self) -> TypedProgram:
        self._check_uses()
        self._declare_structs()
        self._declare_functions()
        self._resolve_struct_fields()
        self._declare_models()
        self._declare_trainings()
        for fn in self.functions.values():
            self._check_function(fn)
        return TypedProgram(
            self.module,
            self.functions,
            self.structs,
            self.models,
            self.trainings,
            frozenset(self.namespaces),
            self.diag,
        )

    def _check_uses(self) -> None:
        seen: set[str] = set()
        for use in self.module.uses:
            if len(use.path) != 1:
                self.diag.error(
                    "PE3006",
                    "only whole standard-library namespaces can be imported in 0.3",
                    use.span,
                    hint="write 'उपयोग तन्त्रजाल;' rather than 'उपयोग तन्त्रजाल.अभ्यासय;'",
                )
                continue
            ns = use.path[0]
            if ns not in B.NAMESPACES:
                suggestion = self._suggest(ns, B.NAMESPACES)
                self.diag.error(
                    "PE3006",
                    f"unknown module '{ns}'",
                    use.span,
                    hint=f"did you mean 'उपयोग {surface(suggestion)};'?" if suggestion else f"known modules: {', '.join(surface(n) for n in sorted(B.NAMESPACES))}",
                )
                continue
            if ns in seen:
                self.diag.error("PE3001", f"module '{surface(ns)}' is imported more than once", use.span)
            seen.add(ns)
            self.namespaces.add(ns)

    def _declare_structs(self) -> None:
        for decl in self.module.structs:
            if self._name_conflict(decl.name, decl.name_span):
                continue
            self.structs[decl.name] = StructSymbol(decl.name, decl)

    def _resolve_struct_fields(self) -> None:
        for sym in self.structs.values():
            seen: set[str] = set()
            for f in sym.decl.fields:
                if f.name in seen:
                    self.diag.error(
                        "PE3001", f"duplicate field '{f.name}' in struct '{sym.name}'", f.span
                    )
                    continue
                seen.add(f.name)
                ty = self.resolve_type(f.annotation)
                if ty == T.UnitType:
                    self._error("PE3003", "struct fields may not have type एकक", f.annotation.span)
                f.ty = ty
                sym.field_names.append(f.name)
                sym.field_types.append(ty)

    def _declare_functions(self) -> None:
        for decl in self.module.functions:
            if self._name_conflict(decl.name, decl.name_span):
                continue
            param_types: list[T.Type] = []
            seen_params: set[str] = set()
            for p in decl.params:
                if p.name in seen_params:
                    self.diag.error("PE3001", f"duplicate parameter '{p.name}'", p.span)
                seen_params.add(p.name)
                ty = self.resolve_type(p.annotation)
                if ty == T.UnitType:
                    self.diag.error(
                        "PE3003", f"parameter '{p.name}' may not have type Unit", p.annotation.span
                    )
                p.ty = ty
                param_types.append(ty)
            if decl.return_type is not None:
                return_type = self.resolve_type(decl.return_type)
            else:
                return_type = T.UnitType
            self.functions[decl.name] = FunctionSymbol(
                decl.name, decl, param_types, return_type
            )
            if decl.name == "main":
                self._check_entry_point()

    def _check_entry_point(self) -> None:
        symbol = self.functions.get("main")
        if symbol is None:
            return
        decl = symbol.decl
        if len(decl.params) != 0:
            self.diag.error(
                "PE3013",
                f"entry point 'मुख्य' must take no parameters, found {len(decl.params)}",
                decl.name_span,
                hint="read command-line arguments with प्रक्रिया.तर्कावली(); the host passes them there",
            )
        if symbol.return_type != T.UnitType:
            self.diag.error(
                "PE3013",
                "entry point 'मुख्य' must return एकक",
                decl.return_type.span if decl.return_type is not None else decl.name_span,
                hint="terminate with 'प्रत्यानय;' and report failures with क्षिप/निश्चिनु",
            )

    def _name_conflict(self, name: str, span: Span) -> bool:
        if (
            name in self.functions
            or name in self.structs
            or name in self.models
            or name in self.trainings
        ):
            self.diag.error("PE3001", f"'{name}' is already declared", span)
            return True
        if name in B.NATIVES or name in B.NAMESPACES:
            self.diag.error(
                "PE3001",
                f"'{name}' conflicts with a built-in name",
                span,
                hint="choose a different name",
            )
            return True
        if name in _PRIMITIVES or name in _OPAQUE or name in ("Tensor", "List"):
            self.diag.error(
                "PE3001",
                f"'{name}' is a built-in type name and cannot be redeclared",
                span,
            )
            return True
        return False

    # -- types -------------------------------------------------------------
    def resolve_type(self, te) -> T.Type:
        if isinstance(te, TensorTypeExpr):
            if te.dtype not in T.TENSOR_DTYPES:
                self._error(
                    "PE3003",
                    f"unknown tensor dtype '{te.dtype}'",
                    te.dtype_span,
                    hint=f"supported dtypes: {', '.join(T.TENSOR_DTYPES)}",
                )
                return T.ErrorType
            shape = tuple(te.shape) if te.shape is not None else None
            return T.TensorType(te.dtype, shape)
        if isinstance(te, ListTypeExpr):
            elem = self.resolve_type(te.element)
            if elem == T.UnitType:
                self._error("PE3003", "सूची<एकक> is not a valid type", te.span)
            return T.ListType(elem)
        if isinstance(te, NamedTypeExpr):
            name = te.name
            if te.args:
                self._error(
                    "PE3012",
                    f"user-defined generic types are not implemented in 0.3 ('{name}<...>')",
                    te.span,
                )
                return T.ErrorType
            if name in _PRIMITIVES:
                return _PRIMITIVES[name]
            if name == "Any":
                self._error(
                    "PE3012",
                    "'Any' is reserved for native signatures and cannot be written in source",
                    te.span,
                )
                return T.ErrorType
            if name in _OPAQUE:
                return _OPAQUE[name]
            if name in self.structs:
                return T.StructType(name)
            if name in self.models or name in self.trainings:
                self._error(
                    "PE3012",
                    f"'{name}' is a declaration, not a type",
                    te.span,
                    hint="use the opaque 'प्रतिमानप्रकार' type for model values",
                )
                return T.ErrorType
            suggestion = self._suggest(
                name, list(_PRIMITIVES) + list(_OPAQUE) + list(self.structs)
            )
            self._error(
                "PE3003",
                f"unknown type '{name}'",
                te.span,
                hint=f"did you mean '{suggestion}'?" if suggestion else None,
            )
            return T.ErrorType
        self._error("PE3003", "unsupported type syntax", getattr(te, "span", Span(0, 0, 1, 1)))
        return T.ErrorType

    # -- models and training ----------------------------------------------
    def _declare_models(self) -> None:
        for decl in self.module.models:
            if self._name_conflict(decl.name, decl.name_span):
                continue
            symbol = self._analyse_model(decl)
            if symbol is not None:
                self.models[decl.name] = symbol

    def _analyse_model(self, decl) -> ModelSymbol | None:
        ok = True
        if len(decl.inputs) != 1:
            self.diag.error(
                "PE3009",
                f"model '{decl.name}' must declare exactly one input in 0.3 (found {len(decl.inputs)})",
                decl.name_span,
            )
            ok = False
        if len(decl.outputs) != 1:
            self.diag.error(
                "PE3009",
                f"model '{decl.name}' must declare exactly one output in 0.3 (found {len(decl.outputs)})",
                decl.name_span,
            )
            ok = False
        inputs: list[T.TensorType] = []
        outputs: list[T.TensorType] = []
        for field in decl.inputs:
            ty = self.resolve_type(field.annotation)
            if not isinstance(ty, T.TensorType):
                self.diag.error(
                    "PE3009",
                    f"model input '{field.name}' must be a Tensor, found {ty.display()}",
                    field.span,
                )
                ok = False
            else:
                if ty.dtype not in ("Float32", "Float64"):
                    self.diag.error(
                        "PE3009",
                        f"model input '{field.name}' must use a floating dtype",
                        field.span,
                    )
                    ok = False
                if ty.shape is None:
                    self.diag.error(
                        "PE3009",
                        f"model input '{field.name}' needs a statically known shape in 0.3",
                        field.span,
                        hint="write आयाम<दशमलव३२, [2]> rather than आयाम<दशमलव३२>",
                    )
                    ok = False
                inputs.append(ty)
        for field in decl.outputs:
            ty = self.resolve_type(field.annotation)
            if not isinstance(ty, T.TensorType):
                self.diag.error(
                    "PE3009",
                    f"model output '{field.name}' must be a Tensor, found {ty.display()}",
                    field.span,
                )
                ok = False
            else:
                if ty.dtype not in ("Float32", "Float64"):
                    self.diag.error(
                        "PE3009",
                        f"model output '{field.name}' must use a floating dtype",
                        field.span,
                    )
                    ok = False
                if ty.shape is None:
                    self.diag.error(
                        "PE3009",
                        f"model output '{field.name}' needs a statically known shape in 0.3",
                        field.span,
                    )
                    ok = False
                outputs.append(ty)
        layers: list[ResolvedLayer] = []
        for layer in decl.layers:
            resolved = self._analyse_layer(layer)
            if resolved is None:
                ok = False
            else:
                layers.append(resolved)
        if not decl.layers:
            self.diag.error(
                "PE3009", f"model '{decl.name}' has an empty stack", decl.name_span
            )
            ok = False
        if ok and inputs and outputs and layers:
            current = inputs[0].shape[-1] if inputs[0].shape else None
            for layer in layers:
                current = layer.units
            if current is not None and outputs[0].shape and outputs[0].shape[-1] != current:
                self.diag.error(
                    "PE3009",
                    f"model output last dimension is {outputs[0].shape[-1]}, but the stack produces {current} units",
                    decl.outputs[0].span,
                    hint="make the final सघन(एककानि: ...) match the output shape",
                )
                ok = False
        if not ok:
            return None
        assert inputs and outputs
        return ModelSymbol(decl.name, decl, inputs[0], outputs[0], layers)

    def _analyse_layer(self, layer: LayerDecl) -> ResolvedLayer | None:
        if layer.name != "Dense":
            self.diag.error(
                "PE3009",
                f"unknown layer '{surface(layer.name)}'",
                layer.span,
                hint="0.3 supports only सघन(एककानि: N, सक्रियण: धनाङ्क|वक्रसीमा|अतिस्पर्शज्या|कोमलाधिकतम|रैखिक)",
            )
            return None
        seen: set[str] = set()
        units: int | None = None
        activation = "linear"
        for arg in layer.args:
            if arg.name in seen:
                self.diag.error("PE3009", f"duplicate layer argument '{surface(arg.name)}'", arg.span)
                continue
            seen.add(arg.name)
            if arg.name == "units":
                if not isinstance(arg.value, IntLit):
                    self.diag.error(
                        "PE3009", "सघन 'एककानि' must be an integer literal in 0.3", arg.span
                    )
                    continue
                units = arg.value.value
                if units <= 0:
                    self.diag.error("PE3009", "सघन 'एककानि' must be positive", arg.span)
            elif arg.name == "activation":
                if arg.symbol is not None:
                    activation = arg.symbol
                elif isinstance(arg.value, StringLit):
                    activation = arg.value.value
                else:
                    self.diag.error(
                        "PE3009",
                        "सघन 'सक्रियण' must be a bare name or string literal",
                        arg.span,
                        hint="सक्रियण: धनाङ्क",
                    )
                activation = internalise_enum(activation)
                if activation not in _ACTIVATIONS:
                    self.diag.error(
                        "PE3009",
                        f"unknown activation '{surface_enum(activation)}'",
                        arg.span,
                        hint=f"supported: {', '.join(sorted(surface_enum(v) for v in _ACTIVATIONS))}",
                    )
            else:
                self.diag.error(
                    "PE3009",
                    f"unknown सघन argument '{surface(arg.name)}'",
                    arg.span,
                    hint="supported arguments: एककानि, सक्रियण",
                )
        if units is None:
            self.diag.error("PE3009", "सघन layer requires 'एककानि'", layer.span)
            return None
        return ResolvedLayer("Dense", units, activation)

    def _declare_trainings(self) -> None:
        for decl in self.module.trainings:
            if self._name_conflict(decl.name, decl.name_span):
                continue
            symbol = self._analyse_training(decl)
            if symbol is not None:
                self.trainings[decl.name] = symbol

    def _analyse_training(self, decl) -> TrainingSymbol | None:
        defaults: dict[str, Any] = {
            "objective": "cross_entropy",
            "optimiser": "adam",
            "epochs": 10,
            "learning_rate": 0.01,
            "batch_size": 16,
            "seed": 0,
        }
        config = dict(defaults)
        seen: set[str] = set()
        ok = True
        for field_node in decl.fields:
            if field_node.name in seen:
                self.diag.error(
                    "PE3010", f"duplicate training option '{surface(field_node.name)}'", field_node.span
                )
                ok = False
                continue
            seen.add(field_node.name)
            if field_node.name not in defaults:
                self.diag.error(
                    "PE3010",
                    f"unknown training option '{surface(field_node.name)}'",
                    field_node.span,
                    hint=f"supported options: {', '.join(sorted(surface(k) for k in defaults))}",
                )
                ok = False
                continue
            value = self._const_value(field_node.value)
            if value is None:
                ok = False
                continue
            config[field_node.name] = value
        config["objective"] = internalise_enum(config["objective"])
        config["optimiser"] = internalise_enum(config["optimiser"])
        if config["objective"] not in _OBJECTIVES:
            self.diag.error(
                "PE3010",
                f"unknown objective '{surface_enum(config['objective'])}'",
                decl.name_span,
                hint=f"supported: {', '.join(sorted(surface_enum(v) for v in _OBJECTIVES))}",
            )
            ok = False
        if config["optimiser"] not in _OPTIMISERS:
            self.diag.error(
                "PE3010",
                f"unknown optimiser '{surface_enum(config['optimiser'])}'",
                decl.name_span,
                hint=f"supported: {', '.join(sorted(surface_enum(v) for v in _OPTIMISERS))}",
            )
            ok = False
        for key in ("epochs", "batch_size"):
            if not isinstance(config[key], int) or isinstance(config[key], bool) or config[key] < 1:
                self.diag.error(
                    "PE3010", f"training option '{surface(key)}' must be an integer >= 1", decl.name_span
                )
                ok = False
        lr = config["learning_rate"]
        if not isinstance(lr, (int, float)) or isinstance(lr, bool) or lr <= 0:
            self.diag.error(
                "PE3010", "training option 'अधिगमदर' must be a positive number", decl.name_span
            )
            ok = False
        if not isinstance(config["seed"], int) or isinstance(config["seed"], bool):
            self.diag.error("PE3010", "training option 'बीज' must be an integer", decl.name_span)
            ok = False
        if not ok:
            return None
        return TrainingSymbol(decl.name, decl, config)

    def _const_value(self, expr: Expr) -> int | float | str | bool | None:
        if isinstance(expr, IntLit):
            expr.ty = T.IntType
            return expr.value
        if isinstance(expr, FloatLit):
            expr.ty = T.FloatType
            return expr.value
        if isinstance(expr, StringLit):
            expr.ty = T.StringType
            return expr.value
        if isinstance(expr, BoolLit):
            expr.ty = T.BoolType
            return expr.value
        if isinstance(expr, Unary) and expr.op == "-" and isinstance(
            expr.operand, (IntLit, FloatLit)
        ):
            operand = self._const_value(expr.operand)
            expr.ty = expr.operand.ty
            if isinstance(operand, (int, float)):
                return -operand
        self.diag.error(
            "PE3010",
            "training option values must be numeric, string or boolean literals in 0.3",
            expr.span,
        )
        expr.ty = T.ErrorType
        return None

    # -- functions ---------------------------------------------------------
    def _check_function(self, fn: FunctionSymbol) -> None:
        decl = fn.decl
        self.current_function = fn
        self.next_slot = 0
        self.max_slots = 0
        self._push_scope()
        # Capabilities are function-scoped and must be declared at the top level
        # of the body. Collect them first so calls earlier in the body see them.
        caps: set[str] = set()
        for stmt in decl.body.statements:
            if isinstance(stmt, CapabilityStmt):
                for name, span in zip(stmt.capabilities, stmt.spans):
                    if name not in KNOWN_CAPABILITIES:
                        self.diag.error(
                            "PE3005",
                            f"unknown capability '{name}'",
                            span,
                            hint=f"known capabilities in 0.3: {', '.join(surface(c) for c in KNOWN_CAPABILITIES)}",
                        )
                    elif name in caps:
                        self.diag.error(
                            "PE3005", f"capability '{surface(name)}' is declared twice", span
                        )
                    else:
                        caps.add(name)
        decl.capabilities = frozenset(caps)
        fn.capabilities = decl.capabilities
        for param, ty in zip(decl.params, fn.param_types):
            sym = self._declare(param.name, ty, False, param.span)
            param.slot = sym.slot
        self._check_block(decl.body, new_scope=False, allow_capability=True)
        if fn.return_type != T.UnitType and fn.return_type != T.NeverType:
            if not decl.body.always_returns:
                self.diag.error(
                    "PE3008",
                    f"function '{fn.name}' does not return a value on all paths",
                    decl.name_span,
                    hint=f"declare '-> एकक' if the function returns nothing, or add a प्रत्यानय statement",
                )
        self._pop_scope()
        decl.slot_count = self.max_slots
        if self.next_slot > 255:
            self.diag.error(
                "PE3012",
                f"function '{fn.name}' needs {self.next_slot} local slots; the 0.3 VM supports at most 256",
                decl.name_span,
            )
        self.current_function = None

    # -- blocks & statements ----------------------------------------------
    def _check_block(self, block: Block, new_scope: bool = True, allow_capability: bool = False) -> None:
        if new_scope:
            self._push_scope()
        unreachable_reported = False
        for stmt in block.statements:
            if block.always_returns and not unreachable_reported:
                self.diag.warning(
                    "PE3102", "unreachable statement", stmt.span,
                    hint="this code follows a statement that always returns or throws",
                )
                unreachable_reported = True
            # Unreachable statements are still checked so that every declaration
            # receives a slot and diagnostics are complete. Code generation skips them.
            self._check_stmt(stmt, allow_capability=allow_capability and not block.always_returns)
            if stmt.always_returns:
                block.always_returns = True
        if new_scope:
            self._pop_scope()

    def _check_stmt(self, stmt: Stmt, allow_capability: bool = False) -> None:
        if isinstance(stmt, Block):
            self._check_block(stmt, new_scope=True, allow_capability=False)
            stmt.always_returns = stmt.always_returns or any(
                s.always_returns for s in stmt.statements
            )
            return
        if isinstance(stmt, LetStmt):
            expected = self.resolve_type(stmt.annotation) if stmt.annotation is not None else None
            if expected is not None and expected == T.UnitType:
                self._error("PE3003", "variables may not have type एकक", stmt.annotation.span)
            ty = self._check_expr(stmt.init, expected)
            if expected is not None:
                if not T.is_assignable(ty, expected):
                    self._error(
                        "PE3003",
                        f"cannot initialise '{stmt.name}' of type {expected.display()} with {ty.display()}",
                        stmt.init.span,
                    )
                final_ty = expected
            else:
                if ty == T.UnitType:
                    self._error(
                        "PE3003",
                        f"cannot infer a type for '{stmt.name}' from a Unit expression",
                        stmt.init.span,
                    )
                final_ty = ty
            sym = self._declare(stmt.name, final_ty, stmt.mutable, stmt.span)
            stmt.slot = sym.slot
            stmt.ty = final_ty
            stmt.symbol = sym
            return
        if isinstance(stmt, AssignStmt):
            self._check_assign(stmt)
            return
        if isinstance(stmt, ExprStmt):
            ty = self._check_expr(stmt.expr)
            stmt.always_returns = ty == T.NeverType
            return
        if isinstance(stmt, IfStmt):
            cond = self._check_expr(stmt.condition)
            if cond != T.BoolType and not self._is_error(cond):
                self._error(
                    "PE3003", f"if condition must be Bool, found {cond.display()}", stmt.condition.span
                )
            self._check_block(stmt.then_block, new_scope=True)
            if stmt.else_branch is not None:
                if isinstance(stmt.else_branch, IfStmt):
                    self._check_stmt(stmt.else_branch)
                else:
                    self._check_block(stmt.else_branch, new_scope=True)
                stmt.always_returns = stmt.then_block.always_returns and stmt.else_branch.always_returns
            return
        if isinstance(stmt, WhileStmt):
            cond = self._check_expr(stmt.condition)
            if cond != T.BoolType and not self._is_error(cond):
                self._error(
                    "PE3003",
                    f"while condition must be Bool, found {cond.display()}",
                    stmt.condition.span,
                )
            self.loop_depth += 1
            self._check_block(stmt.body, new_scope=True)
            self.loop_depth -= 1
            return
        if isinstance(stmt, ForStmt):
            iterable_ty = self._check_expr(stmt.iterable)
            elem: T.Type | None = None
            if isinstance(iterable_ty, T.ListType):
                elem = iterable_ty.element
            elif iterable_ty == T.RangeType:
                elem = T.IntType
            elif not self._is_error(iterable_ty):
                self._error(
                    "PE3003",
                    f"for-loop iterable must be a List or Range, found {iterable_ty.display()}",
                    stmt.iterable.span,
                    hint="use 'प्रति i मध्ये 0..n' or iterate a सूची",
                )
            self.loop_depth += 1
            self._push_scope()
            if elem is not None:
                sym = self._declare(stmt.name, elem, False, stmt.span)
                stmt.slot = sym.slot
            self._check_block(stmt.body, new_scope=False)
            self._pop_scope()
            self.loop_depth -= 1
            return
        if isinstance(stmt, ReturnStmt):
            fn = self.current_function
            if fn is None:  # pragma: no cover - parser prevents this
                self._error("PE3008", "return outside a function", stmt.span)
                return
            expected = fn.return_type
            if stmt.value is None:
                if expected != T.UnitType:
                    self._error(
                        "PE3008",
                        f"function '{fn.name}' must return {expected.display()}",
                        stmt.span,
                    )
            else:
                got = self._check_expr(stmt.value)
                if expected == T.UnitType:
                    self._error(
                        "PE3008",
                        f"function '{fn.name}' returns Unit but a value is returned",
                        stmt.value.span,
                        hint="write 'प्रत्यानय;'",
                    )
                elif not T.is_assignable(got, expected):
                    self._error(
                        "PE3008",
                        f"function '{fn.name}' returns {expected.display()}, found {got.display()}",
                        stmt.value.span,
                    )
            stmt.always_returns = True
            return
        if isinstance(stmt, (BreakStmt, ContinueStmt)):
            if self.loop_depth == 0:
                self._error(
                    "PE3011",
                    f"'{stmt.__class__.__name__.replace('Stmt', '').lower()}' outside a loop",
                    stmt.span,
                )
            return
        if isinstance(stmt, CapabilityStmt):
            if not allow_capability:
                self._error(
                    "PE3005",
                    "capability declarations must appear directly in the function body",
                    stmt.span,
                    hint="move the declaration to the top level of the enclosing function",
                )
            return
        if isinstance(stmt, ThrowStmt):
            ty = self._check_expr(stmt.value)
            if ty != T.StringType and not self._is_error(ty):
                self._error(
                    "PE3003",
                    f"throw expects a String message, found {ty.display()}",
                    stmt.value.span,
                )
            stmt.always_returns = True
            return
        if isinstance(stmt, TryStmt):
            self.loop_depth += 0  # break/continue inside try are governed by enclosing loop
            self._check_block(stmt.body, new_scope=True)
            self._push_scope()
            sym = self._declare(stmt.catch_name, T.StringType, False, stmt.span)
            stmt.slot = sym.slot
            self._check_block(stmt.catch_body, new_scope=False)
            self._pop_scope()
            stmt.always_returns = stmt.body.always_returns and stmt.catch_body.always_returns
            return
        if isinstance(stmt, AssertStmt):
            cond = self._check_expr(stmt.condition)
            if cond != T.BoolType and not self._is_error(cond):
                self._error(
                    "PE3003",
                    f"assert condition must be Bool, found {cond.display()}",
                    stmt.condition.span,
                )
            if stmt.message is not None:
                msg = self._check_expr(stmt.message)
                if msg != T.StringType and not self._is_error(msg):
                    self._error(
                        "PE3003",
                        f"assert message must be a String, found {msg.display()}",
                        stmt.message.span,
                    )
            return
        self._error("PE3012", f"unsupported statement {type(stmt).__name__}", stmt.span)

    def _check_assign(self, stmt: AssignStmt) -> None:
        target = stmt.target
        op = stmt.op
        if isinstance(target, Name):
            sym = self._lookup_local(target.ident)
            if sym is None:
                target.ty = self._error(
                    "PE3002", f"unknown variable '{target.ident}'", target.span
                )
                self._check_expr(stmt.value)
                return
            target.symbol = sym
            target.resolution = "local"
            target.ty = sym.ty
            sym.used = True
            if not sym.mutable:
                self._error(
                    "PE3007",
                    f"cannot assign to immutable variable '{sym.name}'",
                    target.span,
                    hint=f"declare it with 'स्थापय परिवर्तनीय {surface(sym.name)} = ...'",
                )
            expected = sym.ty
        elif isinstance(target, Field):
            base_ty = self._check_expr(target.base)
            target.ty = self._field_type(base_ty, target, for_assignment=True)
            expected = target.ty
        elif isinstance(target, Index):
            base_ty = self._check_expr(target.base)
            idx_ty = self._check_expr(target.index)
            if idx_ty != T.IntType and not self._is_error(idx_ty):
                self._error(
                    "PE3003",
                    f"index must be Int, found {idx_ty.display()}",
                    target.index.span,
                )
            if isinstance(base_ty, T.ListType):
                target.ty = base_ty.element
                target.index_kind = "list"
            elif self._is_error(base_ty):
                target.ty = T.ErrorType
            else:
                target.ty = self._error(
                    "PE3007",
                    f"cannot assign through an index of {base_ty.display()}",
                    target.span,
                    hint="0.3 supports index assignment only for सूची values; tensors are immutable",
                )
            expected = target.ty
        else:
            self._error(
                "PE3007", "invalid assignment target", stmt.target.span
            )
            self._check_expr(stmt.value)
            return

        if op == "=":
            value_ty = self._check_expr(stmt.value, expected)
            if not T.is_assignable(value_ty, expected):
                self._error(
                    "PE3003",
                    f"cannot assign {value_ty.display()} to {expected.display()}",
                    stmt.value.span,
                )
        else:
            rhs = self._check_expr(stmt.value)
            binop = op[:-1]
            result, err = self._binary_type(binop, expected, rhs, stmt.span)
            if err:
                self._error("PE3003", err, stmt.span)
            elif not T.is_assignable(result, expected):
                self._error(
                    "PE3003",
                    f"compound assignment '{op}' would change the type to {result.display()}",
                    stmt.span,
                )

    # -- expressions -------------------------------------------------------
    def _check_expr(self, expr: Expr, expected: T.Type | None = None) -> T.Type:
        ty = self._check_expr_inner(expr, expected)
        expr.ty = ty
        return ty

    def _check_expr_inner(self, expr: Expr, expected: T.Type | None) -> T.Type:
        if isinstance(expr, IntLit):
            return T.IntType
        if isinstance(expr, FloatLit):
            return T.FloatType
        if isinstance(expr, StringLit):
            return T.StringType
        if isinstance(expr, BoolLit):
            return T.BoolType
        if isinstance(expr, Name):
            return self._check_name(expr)
        if isinstance(expr, Unary):
            operand = self._check_expr(expr.operand)
            if self._is_error(operand):
                return T.ErrorType
            if expr.op == "-":
                if operand == T.IntType or operand == T.FloatType:
                    return operand
                if isinstance(operand, T.TensorType):
                    return operand
                return self._error(
                    "PE3003", f"unary '-' is not defined for {operand.display()}", expr.span
                )
            if expr.op == "not":
                if operand != T.BoolType:
                    return self._error(
                        "PE3003", f"'not' expects Bool, found {operand.display()}", expr.span
                    )
                return T.BoolType
            return self._error("PE3012", f"unknown unary operator '{expr.op}'", expr.span)
        if isinstance(expr, Binary):
            left = self._check_expr(expr.left)
            right = self._check_expr(expr.right)
            result, err = self._binary_type(expr.op, left, right, expr.span)
            if err:
                return self._error("PE3003", err, expr.span)
            return result
        if isinstance(expr, RangeExpr):
            start = self._check_expr(expr.start)
            end = self._check_expr(expr.end)
            for side, ty, node in (("start", start, expr.start), ("end", end, expr.end)):
                if ty != T.IntType and not self._is_error(ty):
                    self._error(
                        "PE3003",
                        f"range {side} must be Int, found {ty.display()}",
                        node.span,
                    )
            return T.RangeType
        if isinstance(expr, ListLit):
            return self._check_list_literal(expr, expected)
        if isinstance(expr, Call):
            return self._check_call(expr)
        if isinstance(expr, Field):
            base_ty = self._check_expr(expr.base)
            return self._field_type(base_ty, expr)
        if isinstance(expr, Index):
            base_ty = self._check_expr(expr.base)
            idx_ty = self._check_expr(expr.index)
            if idx_ty != T.IntType and not self._is_error(idx_ty):
                self._error(
                    "PE3003", f"index must be Int, found {idx_ty.display()}", expr.index.span
                )
            if isinstance(base_ty, T.ListType):
                expr.index_kind = "list"
                return base_ty.element
            if base_ty == T.StringType:
                expr.index_kind = "string"
                return T.StringType
            if self._is_error(base_ty):
                return T.ErrorType
            return self._error(
                "PE3003",
                f"values of type {base_ty.display()} cannot be indexed in 0.3",
                expr.span,
                hint="use tensor methods such as .पुनराकृति(), or a सूची",
            )
        return self._error("PE3012", f"unsupported expression {type(expr).__name__}", expr.span)

    def _binary_type(
        self, op: str, left: T.Type, right: T.Type, span: Span
    ) -> tuple[T.Type, str | None]:
        if self._is_error(left) or self._is_error(right):
            return T.ErrorType, None
        if op in ("and", "or"):
            if left != T.BoolType or right != T.BoolType:
                return T.ErrorType, f"'{op}' expects Bool operands, found {left.display()} and {right.display()}"
            return T.BoolType, None
        if op in ("==", "!="):
            if left == right and left in (T.IntType, T.FloatType, T.BoolType, T.StringType):
                return T.BoolType, None
            if isinstance(left, T.TensorType) or isinstance(right, T.TensorType):
                return T.ErrorType, (
                    "tensor equality is not supported in 0.3; compare reductions such as .sum()"
                )
            return T.ErrorType, (
                f"cannot compare {left.display()} with {right.display()} using '{op}'"
            )
        if op in ("<", "<=", ">", ">="):
            if left == right and left in (T.IntType, T.FloatType, T.StringType):
                return T.BoolType, None
            return T.ErrorType, (
                f"ordering comparison '{op}' requires two Ints, two Floats or two Strings; "
                f"found {left.display()} and {right.display()}"
            )
        if isinstance(left, T.TensorType) or isinstance(right, T.TensorType):
            if op not in ("+", "-", "*", "/", "**"):
                return T.ErrorType, f"operator '{op}' is not defined for tensors"
            if isinstance(left, T.TensorType) and isinstance(right, T.TensorType):
                if left.dtype != right.dtype:
                    return T.ErrorType, (
                        f"tensor dtypes differ ({left.dtype} and {right.dtype}); "
                        "convert explicitly before combining"
                    )
                if left.shape is None or right.shape is None:
                    return T.TensorType(left.dtype, None), None
                shape = T.broadcast_shapes(left.shape, right.shape)
                if shape is None:
                    return T.ErrorType, (
                        f"cannot broadcast shapes {list(left.shape)} and {list(right.shape)} "
                        f"in operator '{op}'"
                    )
                return T.TensorType(left.dtype, shape), None
            tensor = left if isinstance(left, T.TensorType) else right
            scalar = right if tensor is left else left
            if scalar not in (T.IntType, T.FloatType):
                return T.ErrorType, (
                    f"operator '{op}' between {left.display()} and {right.display()} is not supported"
                )
            if op == "**" and scalar is not T.IntType:
                return T.ErrorType, "tensor exponent must be an Int scalar"
            return T.TensorType(tensor.dtype, tensor.shape), None
        if op == "+":
            if left == T.IntType and right == T.IntType:
                return T.IntType, None
            if left == T.FloatType and right == T.FloatType:
                return T.FloatType, None
            if left == T.StringType and right == T.StringType:
                return T.StringType, None
            return T.ErrorType, (
                f"operator '+' is not defined for {left.display()} and {right.display()}"
                + ("; use str(...) to build strings" if T.StringType in (left, right) else "")
            )
        if op in ("-", "*", "/"):
            if left == T.IntType and right == T.IntType:
                return T.IntType, None
            if left == T.FloatType and right == T.FloatType:
                return T.FloatType, None
            return T.ErrorType, (
                f"operator '{op}' is not defined for {left.display()} and {right.display()}"
                + ("; PEACOCK has no implicit Int/Float conversion" if {left, right} == {T.IntType, T.FloatType} else "")
            )
        if op == "%":
            if left == T.IntType and right == T.IntType:
                return T.IntType, None
            return T.ErrorType, (
                f"operator '%' is defined for Int only in 0.3, found {left.display()} and {right.display()}"
            )
        if op == "**":
            if left == T.IntType and right == T.IntType:
                return T.IntType, None
            if left == T.FloatType and right == T.FloatType:
                return T.FloatType, None
            return T.ErrorType, (
                f"operator '**' requires two Ints or two Floats, found {left.display()} and {right.display()}"
            )
        return T.ErrorType, f"unknown binary operator '{op}'"

    def _check_list_literal(self, expr: ListLit, expected: T.Type | None) -> T.Type:
        expected_elem = expected.element if isinstance(expected, T.ListType) else None
        if not expr.elements:
            if expected_elem is None:
                return self._error(
                    "PE3003",
                    "cannot infer the type of an empty list",
                    expr.span,
                    hint="annotate the binding, e.g. स्थापय xs: सूची<पूर्णाङ्क> = [];",
                )
            # Preserve the contextual element type on the AST so later compiler
            # passes and shadow analyzers can inspect the fully resolved list.
            expr.element_ty = expected_elem
            return T.ListType(expected_elem)
        element_types: list[T.Type] = []
        for i, element in enumerate(expr.elements):
            ty = self._check_expr(element, expected_elem)
            element_types.append(ty)
        if any(self._is_error(t) for t in element_types):
            return T.ErrorType
        first = element_types[0]
        for i, ty in enumerate(element_types[1:], start=1):
            if ty != first:
                self.diag.error(
                    "PE3003",
                    f"list elements must share one type; element 1 is {first.display()} but element {i + 1} is {ty.display()}",
                    expr.elements[i].span,
                    hint="PEACOCK has no implicit numeric conversion; make all elements the same type",
                )
                return T.ErrorType
        expr.element_ty = first
        return T.ListType(first)

    # -- names -------------------------------------------------------------
    def _resolve_entity(self, name: Name):
        local = self._lookup_local(name.ident)
        if local is not None:
            return "local", local
        if name.ident in self.functions:
            return "function", self.functions[name.ident]
        if name.ident in self.structs:
            return "struct", self.structs[name.ident]
        if name.ident in self.models:
            return "model", self.models[name.ident]
        if name.ident in self.trainings:
            return "training", self.trainings[name.ident]
        if name.ident in B.NAMESPACES:
            return "namespace", name.ident
        if name.ident in B.GLOBAL_NATIVES:
            return "native", B.GLOBAL_NATIVES[name.ident]
        return "unknown", None

    def _check_name(self, expr: Name) -> T.Type:
        kind, symbol = self._resolve_entity(expr)
        expr.resolution = kind
        expr.symbol = symbol
        if kind == "local":
            symbol.used = True
            return symbol.ty
        if kind == "function":
            return self._error(
                "PE3012",
                f"function '{expr.ident}' is not a first-class value in 0.3",
                expr.span,
                hint="call it directly instead of storing it",
            )
        if kind == "struct":
            return self._error(
                "PE3012",
                f"struct '{expr.ident}' must be constructed with arguments",
                expr.span,
                hint=f"{expr.ident}(field1, field2, ...)",
            )
        if kind == "model":
            return T.ModelDeclType(expr.ident)
        if kind == "training":
            return T.TrainingDeclType(expr.ident)
        if kind == "namespace":
            if expr.ident not in self.namespaces:
                return self._error(
                    "PE3006",
                    f"module '{expr.ident}' is used but not imported",
                    expr.span,
                    hint=f"add 'उपयोग {surface(expr.ident)};'",
                )
            expr.ty = T.NamespaceType
            return T.NamespaceType
        if kind == "native":
            return self._error(
                "PE3012",
                f"native function '{expr.ident}' must be called",
                expr.span,
            )
        suggestion = self._suggest(
            expr.ident,
            list(self.functions) + list(self.structs) + list(self.models) + list(self.trainings),
        )
        return self._error(
            "PE3002",
            f"unknown name '{expr.ident}'",
            expr.span,
            hint=f"did you mean '{suggestion}'?" if suggestion else None,
        )

    # -- fields & methods --------------------------------------------------
    def _field_type(self, base_ty: T.Type, field: Field, for_assignment: bool = False) -> T.Type:
        if self._is_error(base_ty):
            field.field_kind = "error"
            return T.ErrorType
        if isinstance(base_ty, T.StructType):
            struct = self.structs.get(base_ty.name)
            if struct is None:  # pragma: no cover
                return self._error("PE3003", f"unknown struct '{base_ty.name}'", field.span)
            if field.name not in struct.field_names:
                return self._error(
                    "PE3015",
                    f"struct '{struct.name}' has no field '{field.name}'",
                    field.name_span,
                    hint=f"fields: {', '.join(surface(n) for n in struct.field_names)}",
                )
            idx = struct.field_index(field.name)
            field.field_kind = "struct_field"
            field.symbol = (struct, idx)
            return struct.field_types[idx]
        category = _category(base_ty)
        if category is not None:
            prop = B.PROPERTIES.get((category, field.name))
            if prop is not None:
                field.field_kind = "property"
                if isinstance(prop, T.TensorType) and isinstance(base_ty, T.TensorType):
                    return T.TensorType(base_ty.dtype, None)
                return prop
            if for_assignment:
                return self._error(
                    "PE3007", f"property '{surface(field.name)}' of {base_ty.display()} is read-only", field.name_span
                )
            return self._error(
                "PE3015",
                f"{base_ty.display()} has no property '{surface(field.name)}'",
                field.name_span,
            )
        if isinstance(base_ty, T.ModelDeclType):
            return self._error(
                "PE3012",
                f"model declaration members are only callable, e.g. {base_ty.name}.प्रारम्भ(बीज: 0)",
                field.span,
            )
        if isinstance(base_ty, T.TrainingDeclType):
            return self._error(
                "PE3012",
                f"training declaration members are only callable, e.g. {base_ty.name}.चलाय(प्रतिमानमूल्य, दत्त)",
                field.span,
            )
        if base_ty == T.NamespaceType:
            return self._error(
                "PE3012",
                "namespace members must be called directly",
                field.span,
            )
        return self._error(
            "PE3015",
            f"{base_ty.display()} has no fields in 0.3",
            field.span,
        )

    def _check_method_call(self, base_ty: T.Type, field: Field, call: Call) -> T.Type:
        if any(name is not None for name in call.arg_names):
            self._error(
                "PE3004",
                "named arguments are not supported for methods in 0.3",
                call.span,
                hint="pass method arguments positionally",
            )
        category = _category(base_ty)
        if category is None:
            return self._error(
                "PE3015",
                f"{base_ty.display()} has no methods",
                field.name_span,
            )
        spec = B.METHODS.get((category, field.name))
        if spec is None:
            available = sorted(name for (cat, name) in B.METHODS if cat == category)
            return self._error(
                "PE3015",
                f"{base_ty.display()} has no method '{surface(field.name)}'",
                field.name_span,
                hint=f"available: {', '.join(surface(n) for n in available)}",
            )
        param_types, ret, capability = spec
        # Substitute element/tensor placeholders.
        elem = base_ty.element if isinstance(base_ty, T.ListType) else None
        concrete_params: list[T.Type] = []
        for p in param_types:
            if p == B.ELEM:
                concrete_params.append(elem if elem is not None else T.ErrorType)
            elif p == B.TENSOR_PLACEHOLDER:
                if isinstance(base_ty, T.TensorType):
                    concrete_params.append(T.TensorType(base_ty.dtype, None))
                else:
                    concrete_params.append(T.TensorType("Float32", None))
            else:
                concrete_params.append(p)
        if len(call.args) != len(concrete_params):
            self._error(
                "PE3004",
                f"method '{field.name}' expects {len(concrete_params)} argument(s), found {len(call.args)}",
                call.span,
            )
            for arg in call.args:
                self._check_expr(arg)
            return T.ErrorType
        arg_types = [self._check_expr(arg, p) for arg, p in zip(call.args, concrete_params)]
        for i, (got, want) in enumerate(zip(arg_types, concrete_params), start=1):
            if not T.is_assignable(got, want):
                self._error(
                    "PE3003",
                    f"argument {i} of method '{surface(field.name)}' expects {want.display()}, found {got.display()}",
                    call.args[i - 1].span,
                )
        call.call_kind = "method"
        call.target = (category, field.name)
        if field.name == "join" and elem is not None and elem != T.StringType:
            return self._error(
                "PE3003", "संयोजय() requires सूची<अक्षरमाला>", call.span
            )
        if field.name == "sort" and elem is not None and elem not in (T.IntType, T.FloatType):
            return self._error(
                "PE3003", "क्रमय() requires a सूची of पूर्णाङ्क or दशमलव", call.span
            )
        if capability is not None:
            self._require_capability(capability, call.span, f"method '{surface(field.name)}'")
        if ret == B.ELEM:
            return elem if elem is not None else T.ErrorType
        if ret == B.TENSOR_PLACEHOLDER:
            if isinstance(base_ty, T.TensorType):
                if field.name == "reshape":
                    return T.TensorType(base_ty.dtype, None)
                if field.name == "transpose":
                    shape = tuple(reversed(base_ty.shape)) if base_ty.shape is not None else None
                    return T.TensorType(base_ty.dtype, shape)
                if field.name == "matmul":
                    arg_ty = call.args[0].ty if call.args else None
                    if isinstance(base_ty, T.TensorType) and isinstance(arg_ty, T.TensorType):
                        if base_ty.dtype != arg_ty.dtype:
                            self._error(
                                "PE3003",
                                f"matmul requires equal dtypes, found {surface_type(base_ty.dtype)} and {surface_type(arg_ty.dtype)}",
                                call.span,
                            )
                        if base_ty.shape is not None and arg_ty.shape is not None:
                            if len(base_ty.shape) != 2 or len(arg_ty.shape) != 2:
                                self._error(
                                    "PE3003",
                                    "matmul in 0.3 is defined for 2-D tensors only",
                                    call.span,
                                )
                            elif base_ty.shape[1] != arg_ty.shape[0]:
                                self._error(
                                    "PE3003",
                                    f"matmul inner dimensions do not match: {base_ty.shape[1]} vs {arg_ty.shape[0]}",
                                    call.span,
                                )
                            else:
                                return T.TensorType(base_ty.dtype, (base_ty.shape[0], arg_ty.shape[1]))
                    return T.TensorType(base_ty.dtype, None)
                return T.TensorType(base_ty.dtype, base_ty.shape)
            return T.TensorType("Float32", None)
        return ret

    # -- calls -------------------------------------------------------------
    def _bind_args(
        self,
        param_names: list[str],
        required_count: int,
        arg_names: list[str | None],
        args: list[Expr],
        span: Span,
        callee: str,
        emit: bool = True,
    ) -> list[int] | None:
        """Map parameters to source argument indices; -1 means omitted (default)."""
        slots = [-1] * len(param_names)
        for i, name in enumerate(arg_names):
            if name is None:
                target = next((j for j, s in enumerate(slots) if s == -1), None)
                if target is None:
                    if emit:
                        self._error(
                            "PE3004",
                            f"too many arguments to {callee}: expected at most {len(param_names)}, found {len(args)}",
                            args[i].span if i < len(args) else span,
                        )
                    return None
                slots[target] = i
            else:
                if name not in param_names:
                    if emit:
                        self._error(
                            "PE3004",
                            f"{callee} has no parameter named '{surface(name)}'",
                            args[i].span if i < len(args) else span,
                            hint=f"parameters: {', '.join(surface(n) for n in param_names)}",
                        )
                    return None
                target = param_names.index(name)
                if slots[target] != -1:
                    if emit:
                        self._error(
                            "PE3004",
                            f"parameter '{surface(name)}' of {callee} is supplied twice",
                            args[i].span if i < len(args) else span,
                        )
                    return None
                slots[target] = i
        missing = [param_names[j] for j in range(required_count) if slots[j] == -1]
        if missing:
            if emit:
                self._error(
                    "PE3004",
                    f"missing argument(s) to {callee}: {', '.join(missing)}",
                    span,
                )
            return None
        return slots

    def _check_call(self, call: Call) -> T.Type:
        callee = call.callee
        if isinstance(callee, Name):
            kind, symbol = self._resolve_entity(callee)
            callee.resolution = kind
            callee.symbol = symbol
            if kind == "local":
                for arg in call.args:
                    self._check_expr(arg)
                return self._error(
                    "PE3012",
                    f"'{callee.ident}' is a variable, not a function",
                    callee.span,
                )
            if kind == "function":
                return self._check_user_call(call, symbol)
            if kind == "struct":
                return self._check_struct_constructor(call, symbol)
            if kind == "native":
                return self._check_native_call(call, callee.ident, symbol)
            if kind == "namespace":
                for arg in call.args:
                    self._check_expr(arg)
                return self._error(
                    "PE3012",
                    f"namespace '{callee.ident}' is not callable",
                    callee.span,
                    hint=f"call one of its functions, e.g. {callee.ident}.{B.NAMESPACES[callee.ident][0]}",
                )
            if kind in ("model", "training"):
                for arg in call.args:
                    self._check_expr(arg)
                return self._error(
                    "PE3012",
                    f"'{callee.ident}' is a declaration; call a member such as .init(...)",
                    callee.span,
                )
            for arg in call.args:
                self._check_expr(arg)
            return self._error("PE3002", f"unknown function '{callee.ident}'", callee.span)
        if isinstance(callee, Field):
            return self._check_member_call(call, callee)
        for arg in call.args:
            self._check_expr(arg)
        return self._error("PE3012", "expression is not callable", call.span)

    def _check_user_call(self, call: Call, fn: FunctionSymbol) -> T.Type:
        if any(name is not None for name in call.arg_names):
            # Named arguments are supported for user functions too.
            pass
        param_names = [p.name for p in fn.decl.params]
        slots = self._bind_args(
            param_names, len(param_names), call.arg_names, call.args, call.span, f"'{fn.name}'"
        )
        if slots is None:
            for arg in call.args:
                self._check_expr(arg)
            call.arg_order = []
            return T.ErrorType
        arg_types: list[T.Type] = []
        for i, arg in enumerate(call.args):
            param_index = slots.index(i) if i in slots else -1
            expected = (
                fn.param_types[param_index] if param_index >= 0 else None
            )
            arg_types.append(self._check_expr(arg, expected))
        for param_index, source_index in enumerate(slots):
            if source_index < 0:
                continue
            got = arg_types[source_index]
            want = fn.param_types[param_index]
            if not T.is_assignable(got, want):
                self._error(
                    "PE3003",
                    f"argument '{param_names[param_index]}' of '{fn.name}' expects {want.display()}, found {got.display()}",
                    call.args[source_index].span,
                )
        call.call_kind = "function"
        call.target = fn
        call.arg_order = slots
        call.arg_types = arg_types
        return fn.return_type

    def _check_struct_constructor(self, call: Call, struct: StructSymbol) -> T.Type:
        callee = call.callee
        if any(name is not None for name in call.arg_names):
            self._error(
                "PE3004",
                "named arguments are not supported for struct constructors in 0.3",
                call.span,
                hint=f"pass fields in declaration order: {', '.join(surface(n) for n in struct.field_names)}",
            )
            for arg in call.args:
                self._check_expr(arg)
            return T.ErrorType
        if len(call.args) != len(struct.field_names):
            self._error(
                "PE3004",
                f"struct '{struct.name}' expects {len(struct.field_names)} field value(s), found {len(call.args)}",
                call.span,
                hint=f"fields: {', '.join(surface(n) for n in struct.field_names)}",
            )
        arg_types = [
            self._check_expr(arg, struct.field_types[i] if i < len(struct.field_types) else None)
            for i, arg in enumerate(call.args)
        ]
        for i, (got, want) in enumerate(zip(arg_types, struct.field_types)):
            if not T.is_assignable(got, want):
                self._error(
                    "PE3003",
                    f"field '{struct.field_names[i]}' expects {want.display()}, found {got.display()}",
                    call.args[i].span,
                )
        call.call_kind = "struct"
        call.target = struct
        call.arg_order = list(range(len(call.args)))
        call.arg_types = arg_types
        return T.StructType(struct.name)

    def _check_native_call(
        self, call: Call, name: str, overloads: tuple[B.NativeSignature, ...]
    ) -> T.Type:
        if name == "tensor":
            return self._check_tensor_call(call)
        if name == "len":
            if len(call.args) != 1:
                self._error("PE3004", f"'len' expects 1 argument, found {len(call.args)}", call.span)
                for arg in call.args:
                    self._check_expr(arg)
                return T.ErrorType
            ty = self._check_expr(call.args[0])
            allowed = (
                isinstance(ty, T.ListType)
                or ty in (T.StringType, T.RangeType, T.DatasetType)
                or isinstance(ty, T.TensorType)
            )
            if not allowed and not self._is_error(ty):
                self._error(
                    "PE3003",
                    f"len() is not defined for {ty.display()}",
                    call.args[0].span,
                    hint="tensor.मान and .आकृति are also available",
                )
            call.call_kind = "native"
            call.native_name = name
            call.arg_order = [0]
            call.target = B.NATIVES[name][0]
            call.native_sig = B.NATIVES[name][0]
            return T.IntType

        param_names = [p.name for p in overloads[0].params]
        # Feasible overloads by arity and parameter names.
        feasible: list[tuple[B.NativeSignature, list[int]]] = []
        for sig in overloads:
            if len(call.args) > len(sig.params):
                continue
            if any(
                n is not None and n not in [p.name for p in sig.params]
                for n in call.arg_names
            ):
                continue
            if len(call.args) < sig.required_count:
                continue
            slots = self._bind_args(
                [p.name for p in sig.params],
                sig.required_count,
                call.arg_names,
                call.args,
                call.span,
                f"'{surface(name)}'",
                emit=False,
            )
            if slots is not None:
                feasible.append((sig, slots))
        if not feasible:
            if len(overloads) == 1:
                # Emit the precise binding error for the only overload.
                self._bind_args(
                    param_names,
                    overloads[0].required_count,
                    call.arg_names,
                    call.args,
                    call.span,
                    f"'{surface(name)}'",
                )
            else:
                self._error(
                    "PE3004",
                    f"no overload of '{name}' accepts {len(call.args)} argument(s)",
                    call.span,
                    hint="overloads: "
                    + "; ".join(
                        f"({', '.join(p.name for p in sig.params)})" for sig in overloads
                    ),
                )
            for arg in call.args:
                self._check_expr(arg)
            call.arg_order = []
            return T.ErrorType

        sig: B.NativeSignature
        slots: list[int]
        if len(feasible) == 1:
            sig, slots = feasible[0]
            arg_types: list[T.Type] = []
            for i, arg in enumerate(call.args):
                param_index = slots.index(i) if i in slots else -1
                expected = sig.params[param_index].ty if param_index >= 0 else None
                if expected == T.AnyType:
                    expected = None
                arg_types.append(self._check_expr(arg, expected))
        else:
            arg_types = [self._check_expr(arg) for arg in call.args]
            chosen = None
            for candidate, candidate_slots in feasible:
                ok = True
                for pi, si in enumerate(candidate_slots):
                    if si < 0:
                        continue
                    want = candidate.params[pi].ty
                    if want == T.AnyType:
                        continue
                    if not T.is_assignable(arg_types[si], want):
                        ok = False
                        break
                if ok:
                    chosen = (candidate, candidate_slots)
                    break
            if chosen is None:
                types = ", ".join(t.display() for t in arg_types)
                self._error(
                    "PE3003",
                    f"no overload of '{surface(name)}' accepts argument types ({types})",
                    call.span,
                    hint="overloads: "
                    + "; ".join(
                        f"({', '.join(p.ty.display() for p in s.params)}) -> {s.returns.display()}"
                        for s in overloads
                    ),
                )
                call.arg_order = []
                return T.ErrorType
            sig, slots = chosen

        for pi, si in enumerate(slots):
            if si < 0:
                continue
            want = sig.params[pi].ty
            got = arg_types[si]
            if want == T.AnyType:
                continue
            if not T.is_assignable(got, want):
                self._error(
                    "PE3003",
                    f"argument '{surface(sig.params[pi].name)}' of '{surface(name)}' expects {want.display()}, found {got.display()}",
                    call.args[si].span,
                )
        if sig.capability is not None:
            self._require_capability(sig.capability, call.span, f"'{surface(name)}'")
        call.call_kind = "native"
        call.native_name = name
        call.target = sig
        call.native_sig = sig
        call.arg_order = slots
        call.arg_types = arg_types
        return sig.returns

    def _check_tensor_call(self, call: Call) -> T.Type:
        if len(call.args) != 1 or call.arg_names[0] is not None:
            self._error(
                "PE3004",
                "tensor() expects exactly one positional argument",
                call.span,
            )
            for arg in call.args:
                self._check_expr(arg)
            return T.ErrorType
        arg = call.args[0]
        ty = self._check_expr(arg)
        call.call_kind = "native"
        call.native_name = "tensor"
        call.arg_order = [0]
        call.target = B.NATIVES["tensor"][0]
        call.native_sig = B.NATIVES["tensor"][0]
        if isinstance(ty, T.TensorType):
            return ty
        inferred = self._infer_tensor_literal(arg) if isinstance(arg, ListLit) else None
        if inferred is not None:
            dtype, shape = inferred
            call.tensor_static = T.TensorType(dtype, shape)
            return call.tensor_static
        if isinstance(ty, T.ListType):
            inner = ty.element
            while isinstance(inner, T.ListType):
                inner = inner.element
            if inner in (T.IntType, T.FloatType):
                dtype = "Int32" if inner == T.IntType else "Float32"
                return T.TensorType(dtype, None)
            return self._error(
                "PE3003",
                f"tensor() requires nested numeric lists, found List<{ty.element.display()}>",
                arg.span,
            )
        if self._is_error(ty):
            return T.ErrorType
        return self._error(
            "PE3003",
            f"tensor() requires nested numeric lists or a Tensor, found {ty.display()}",
            arg.span,
        )

    def _infer_tensor_literal(self, expr: Expr) -> tuple[str, tuple[int, ...]] | None:
        if isinstance(expr, IntLit):
            return ("Int32", ())
        if isinstance(expr, FloatLit):
            return ("Float32", ())
        if isinstance(expr, Unary) and expr.op == "-" and isinstance(
            expr.operand, (IntLit, FloatLit)
        ):
            return self._infer_tensor_literal(expr.operand)
        if isinstance(expr, ListLit):
            if not expr.elements:
                return None
            inner: list[tuple[str, tuple[int, ...]]] = []
            for element in expr.elements:
                inferred = self._infer_tensor_literal(element)
                if inferred is None:
                    return None
                inner.append(inferred)
            first_dtype, first_shape = inner[0]
            for dtype, shape in inner[1:]:
                if dtype != first_dtype:
                    self._error(
                        "PE3003",
                        "tensor literals must not mix Int and Float elements",
                        expr.span,
                        hint="write every element as a दशमलव, e.g. 1.0",
                    )
                    return None
                if shape != first_shape:
                    self._error(
                        "PE3003",
                        "tensor literals must be rectangular",
                        expr.span,
                    )
                    return None
            return (first_dtype, (len(expr.elements),) + first_shape)
        return None

    def _check_member_call(self, call: Call, field: Field) -> T.Type:
        base = field.base
        if isinstance(base, Name):
            kind, symbol = self._resolve_entity(base)
            base.resolution = kind
            base.symbol = symbol
            if kind == "namespace":
                namespace = base.ident
                if namespace not in self.namespaces:
                    for arg in call.args:
                        self._check_expr(arg)
                    return self._error(
                        "PE3006",
                        f"module '{namespace}' is used but not imported",
                        base.span,
                        hint=f"add 'उपयोग {surface(namespace)};'",
                    )
                full_name = f"{namespace}.{field.name}"
                if full_name not in B.NATIVES:
                    available = B.NAMESPACES.get(namespace, ())
                    return self._error(
                        "PE3006",
                        f"module '{namespace}' has no function '{field.name}'",
                        field.name_span,
                        hint=f"available: {', '.join(surface(n) for n in available)}",
                    )
                field.field_kind = "namespace_member"
                return self._check_native_call(call, full_name, B.NATIVES[full_name])
            if kind == "model":
                base.ty = T.ModelDeclType(base.ident)
                return self._check_decl_method(call, symbol, B.MODEL_DECL_METHODS, "model")
            if kind == "training":
                base.ty = T.TrainingDeclType(base.ident)
                return self._check_decl_method(call, symbol, B.TRAINING_DECL_METHODS, "training")
            if kind == "local":
                sym = symbol
                sym.used = True
                base.ty = sym.ty
                return self._check_method_call(sym.ty, field, call)
            if kind == "unknown":
                for arg in call.args:
                    self._check_expr(arg)
                return self._error("PE3002", f"unknown name '{base.ident}'", base.span)
            # Fall through for functions/structs as base expressions, which will
            # produce a targeted "not a first-class value" error.
        base_ty = self._check_expr(base)
        if self._is_error(base_ty):
            for arg in call.args:
                self._check_expr(arg)
            return T.ErrorType
        return self._check_method_call(base_ty, field, call)

    def _check_decl_method(
        self,
        call: Call,
        symbol,
        table: dict,
        what: str,
    ) -> T.Type:
        name = call.callee.name if isinstance(call.callee, Field) else "?"
        if name not in table:
            for arg in call.args:
                self._check_expr(arg)
            return self._error(
                "PE3015",
                f"{what} declaration has no method '{name}'",
                call.span,
                hint=f"available: {', '.join(surface(n) for n in sorted(table))}",
            )
        params, returns, capability = table[name]
        slots = self._bind_args(
            [p.name for p in params],
            sum(1 for p in params if not p.optional),
            call.arg_names,
            call.args,
            call.span,
            f"'{surface(name)}'",
        )
        if slots is None:
            for arg in call.args:
                self._check_expr(arg)
            return T.ErrorType
        arg_types: list[T.Type] = []
        for i, arg in enumerate(call.args):
            param_index = slots.index(i) if i in slots else -1
            expected = params[param_index].ty if param_index >= 0 else None
            arg_types.append(self._check_expr(arg, expected))
        for pi, si in enumerate(slots):
            if si < 0:
                continue
            got = arg_types[si]
            want = params[pi].ty
            if not T.is_assignable(got, want):
                self._error(
                    "PE3003",
                    f"argument '{surface(params[pi].name)}' of '{surface(name)}' expects {want.display()}, found {got.display()}",
                    call.args[si].span,
                )
        if capability is not None:
            self._require_capability(capability, call.span, f"'{surface(name)}'")
        call.call_kind = f"{what}_method"
        call.target = symbol
        call.method_name = name
        call.arg_order = slots
        call.method_params = params
        call.arg_types = arg_types
        return returns

    def _require_capability(self, capability: str, span: Span, what: str) -> None:
        fn = self.current_function
        if fn is None:
            self._error(
                "PE3005",
                f"{what} requires the '{surface(capability)}' capability but is not inside a function",
                span,
            )
            return
        if capability not in fn.capabilities:
            self._error(
                "PE3005",
                f"{what} requires capability '{surface(capability)}', which '{surface(fn.name)}' does not declare",
                span,
                hint=f"add 'अधिकार {surface(capability)};' directly inside function '{surface(fn.name)}' (the host must also grant it)",
            )


def _category(ty: T.Type) -> str | None:
    if isinstance(ty, T.TensorType):
        return "Tensor"
    if isinstance(ty, T.ListType):
        return "List"
    return {
        T.StringType: "String",
        T.RangeType: "Range",
        T.DatasetType: "Dataset",
        T.CanvasType: "Canvas",
        T.ModelType: "Model",
        T.ColorType: "Color",
    }.get(ty)


def _edit_distance(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 3:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def analyze(module, diag: DiagnosticBag | None = None) -> TypedProgram:
    return SemanticAnalyzer(module, diag).analyze()
