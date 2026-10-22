"""The native-function catalog shared by the type checker and the runtime.

This module contains *signatures and metadata only*. Implementations live in
``peacock/runtime/native.py`` so the compiler front end never needs to import
the intelligence or graphics engines.

Capabilities (see SPECIFICATION.md §8): a ``NativeSignature`` may require a
capability. The semantic analyser checks the *declared* capabilities of the
enclosing function; the VM checks them again against the *host-granted* set.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import types as T


NO_DEFAULT = object()


@dataclass(frozen=True, slots=True)
class NativeParam:
    name: str
    ty: T.Type
    default: object = NO_DEFAULT

    @property
    def optional(self) -> bool:
        return self.default is not NO_DEFAULT


@dataclass(frozen=True, slots=True)
class NativeSignature:
    params: tuple[NativeParam, ...]
    returns: T.Type
    capability: str | None = None

    @property
    def required_count(self) -> int:
        return sum(1 for p in self.params if not p.optional)


ANY = T.AnyType
I = T.IntType
F = T.FloatType
B = T.BoolType
S = T.StringType
U = T.UnitType
COLOR = T.ColorType
CANVAS = T.CanvasType
MODEL = T.ModelType
DATASET = T.DatasetType
RANGE = T.RangeType
TENSOR = T.TensorType("Float32", None)
TENSOR_ANY = T.TensorType("Float32", None)


def _p(name: str, ty: T.Type, default: object = NO_DEFAULT) -> NativeParam:
    return NativeParam(name, ty, default)


#: Canonical native functions by dotted name. Each name maps to a list of
#: overloads; the checker picks the first signature whose arity and parameter
#: types match.
NATIVES: dict[str, tuple[NativeSignature, ...]] = {
    # -- globals ---------------------------------------------------------
    "print": (NativeSignature((_p("value", ANY),), U),),
    "str": (NativeSignature((_p("value", ANY),), S),),
    "len": (NativeSignature((_p("value", ANY),), I),),
    "range": (NativeSignature((_p("start", I), _p("end", I)), RANGE),),
    "tensor": (NativeSignature((_p("data", ANY),), TENSOR),),
    "int": (
        NativeSignature((_p("value", F),), I),
        NativeSignature((_p("value", I),), I),
    ),
    "float": (
        NativeSignature((_p("value", I),), F),
        NativeSignature((_p("value", F),), F),
    ),
    "abs": (
        NativeSignature((_p("value", I),), I),
        NativeSignature((_p("value", F),), F),
    ),
    "type_name": (NativeSignature((_p("value", ANY),), S),),
    "panic": (NativeSignature((_p("message", S),), T.NeverType),),
    # -- math ------------------------------------------------------------
    "math.sqrt": (NativeSignature((_p("x", F),), F),),
    "math.exp": (NativeSignature((_p("x", F),), F),),
    "math.log": (NativeSignature((_p("x", F),), F),),
    "math.log2": (NativeSignature((_p("x", F),), F),),
    "math.sin": (NativeSignature((_p("x", F),), F),),
    "math.cos": (NativeSignature((_p("x", F),), F),),
    "math.tan": (NativeSignature((_p("x", F),), F),),
    "math.atan2": (NativeSignature((_p("y", F), _p("x", F)), F),),
    "math.pow": (NativeSignature((_p("base", F), _p("exponent", F)), F),),
    "math.floor": (NativeSignature((_p("x", F),), I),),
    "math.ceil": (NativeSignature((_p("x", F),), I),),
    "math.round": (NativeSignature((_p("x", F),), I),),
    "math.min": (NativeSignature((_p("a", F), _p("b", F)), F),),
    "math.max": (NativeSignature((_p("a", F), _p("b", F)), F),),
    "math.clamp": (NativeSignature((_p("x", F), _p("low", F), _p("high", F)), F),),
    "math.pi": (NativeSignature((), F),),
    "math.e": (NativeSignature((), F),),
    # -- colour ----------------------------------------------------------
    "colour.srgb": (
        NativeSignature(
            (_p("r", F), _p("g", F), _p("b", F), _p("alpha", F, 1.0)), COLOR
        ),
    ),
    "colour.oklch": (
        NativeSignature(
            (_p("l", F), _p("c", F), _p("h", F), _p("alpha", F, 1.0)), COLOR
        ),
    ),
    "colour.oklab": (
        NativeSignature(
            (_p("l", F), _p("a", F), _p("b", F), _p("alpha", F, 1.0)), COLOR
        ),
    ),
    "colour.from_hex": (NativeSignature((_p("hex", S),), COLOR),),
    "colour.mix": (NativeSignature((_p("a", COLOR), _p("b", COLOR), _p("t", F)), COLOR),),
    "colour.lighten": (NativeSignature((_p("color", COLOR), _p("amount", F)), COLOR),),
    "colour.darken": (NativeSignature((_p("color", COLOR), _p("amount", F)), COLOR),),
    "colour.rotate_hue": (NativeSignature((_p("color", COLOR), _p("degrees", F)), COLOR),),
    "colour.complement": (NativeSignature((_p("color", COLOR),), COLOR),),
    "colour.to_css": (NativeSignature((_p("color", COLOR),), S),),
    "colour.luminance": (NativeSignature((_p("color", COLOR),), F),),
    "colour.contrast": (NativeSignature((_p("a", COLOR), _p("b", COLOR)), F),),
    "colour.palette": (NativeSignature((_p("count", I), _p("seed", I)), T.ListType(COLOR)),),
    # -- graphics --------------------------------------------------------
    "graphics.canvas": (NativeSignature((_p("width", I), _p("height", I)), CANVAS),),
    "graphics.clear": (NativeSignature((_p("canvas", CANVAS), _p("color", COLOR)), U),),
    "graphics.fill": (NativeSignature((_p("canvas", CANVAS), _p("color", COLOR)), U),),
    "graphics.rect": (
        NativeSignature(
            (
                _p("canvas", CANVAS),
                _p("x", F),
                _p("y", F),
                _p("width", F),
                _p("height", F),
                _p("color", COLOR),
            ),
            U,
        ),
    ),
    "graphics.circle": (
        NativeSignature(
            (_p("canvas", CANVAS), _p("cx", F), _p("cy", F), _p("radius", F), _p("color", COLOR)),
            U,
        ),
    ),
    "graphics.line": (
        NativeSignature(
            (
                _p("canvas", CANVAS),
                _p("x0", F),
                _p("y0", F),
                _p("x1", F),
                _p("y1", F),
                _p("width", F),
                _p("color", COLOR),
            ),
            U,
        ),
    ),
    "graphics.gradient": (
        NativeSignature(
            (_p("canvas", CANVAS), _p("colors", T.ListType(COLOR)), _p("angle", F)), U
        ),
    ),
    "graphics.glow": (
        NativeSignature(
            (_p("canvas", CANVAS), _p("cx", F), _p("cy", F), _p("radius", F), _p("color", COLOR)),
            U,
        ),
    ),
    "graphics.aurora": (
        NativeSignature((_p("canvas", CANVAS), _p("time", F), _p("seed", I)), U),
    ),
    "graphics.save": (
        NativeSignature((_p("canvas", CANVAS), _p("path", S)), U, capability="fs"),
    ),
    "graphics.present": (
        NativeSignature((_p("canvas", CANVAS),), U, capability="ui"),
    ),
    # -- process & filesystem -------------------------------------------
    "process.args": (NativeSignature((), T.ListType(S)),),
    "fs.read_text": (
        NativeSignature((_p("path", S),), S, capability="fs"),
    ),
    "fs.write_text": (
        NativeSignature((_p("path", S), _p("content", S)), U, capability="fs"),
    ),
    "fs.create_dir": (
        NativeSignature((_p("path", S),), U, capability="fs"),
    ),
    # -- neural networks -------------------------------------------------
    "nn.parameter": (
        NativeSignature((_p("data", ANY),), T.TensorType("Float32", None), capability="compute"),
    ),
    "nn.mse": (
        NativeSignature(
            (_p("predictions", T.TensorType("Float32", None)), _p("targets", T.TensorType("Float32", None))),
            T.TensorType("Float32", None),
            capability="compute",
        ),
    ),
    "nn.cross_entropy": (
        NativeSignature(
            (_p("logits", T.TensorType("Float32", None)), _p("labels", T.TensorType("Float32", None))),
            T.TensorType("Float32", None),
            capability="compute",
        ),
    ),
    "nn.max_abs_diff": (
        NativeSignature(
            (_p("a", T.TensorType("Float32", None)), _p("b", T.TensorType("Float32", None))),
            F,
        ),
    ),
    "nn.xor": (NativeSignature((), DATASET),),
    "nn.spiral": (
        NativeSignature((_p("per_class", I), _p("noise", F), _p("seed", I)), DATASET),
    ),
    "nn.dataset": (
        NativeSignature((_p("features", T.TensorType("Float32", None)), _p("labels", T.TensorType("Float32", None))), DATASET),
    ),
    "nn.train": (
        NativeSignature(
            (
                _p("model", MODEL),
                _p("data", DATASET),
                _p("loss", S, "cross_entropy"),
                _p("optimiser", S, "adam"),
                _p("epochs", I, 10),
                _p("learning_rate", F, 0.01),
                _p("batch_size", I, 16),
                _p("seed", I, 0),
            ),
            T.ListType(F),
            capability="compute",
        ),
    ),
    "nn.accuracy": (NativeSignature((_p("model", MODEL), _p("data", DATASET)), F, capability="compute"),),
    "nn.loss": (
        NativeSignature((_p("model", MODEL), _p("data", DATASET), _p("loss", S, "cross_entropy")), F, capability="compute"),
    ),
    "nn.predict": (
        NativeSignature((_p("model", MODEL), _p("x", T.TensorType("Float32", None))), T.TensorType("Float32", None), capability="compute"),
    ),
    "nn.save": (
        NativeSignature((_p("model", MODEL), _p("path", S)), U, capability="fs"),
    ),
    "nn.load": (
        NativeSignature((_p("path", S),), MODEL, capability="fs"),
    ),
    # -- text ------------------------------------------------------------
    "text.char_at": (NativeSignature((_p("value", S), _p("index", I)), S),),
    "text.is_alpha": (NativeSignature((_p("value", S),), B),),
    "text.is_digit": (NativeSignature((_p("value", S),), B),),
    "text.is_alnum": (NativeSignature((_p("value", S),), B),),
    "text.is_mark": (NativeSignature((_p("value", S),), B),),
    "text.is_space": (NativeSignature((_p("value", S),), B),),
    "text.ord": (NativeSignature((_p("value", S),), I),),
    "text.chr": (NativeSignature((_p("code", I),), S),),
    "text.split_lines": (NativeSignature((_p("value", S),), T.ListType(S)),),
    # -- motion ----------------------------------------------------------
    "motion.spring_steps": (
        NativeSignature(
            (
                _p("start", F),
                _p("target", F),
                _p("stiffness", F),
                _p("damping", F),
                _p("steps", I),
                _p("dt", F, 1.0 / 60.0),
            ),
            T.ListType(F),
        ),
    ),
    "motion.ease": (NativeSignature((_p("name", S), _p("t", F)), F),),
}

#: Human-readable descriptions used by tooling and tests.
NATIVE_DOCS: dict[str, str] = {
    "print": "Write a value to standard output followed by a newline.",
    "str": "Convert any PEACOCK value to its display string.",
    "len": "Length of a List, String, Tensor, Range or Dataset.",
    "range": "Half-open integer range [start, end) for for-loops.",
    "tensor": "Construct a tensor from nested numeric lists or another tensor.",
    "nn.train": "Train a model on a dataset; returns per-epoch loss values.",
    "graphics.aurora": "Render a deterministic procedural aurora field into a canvas.",
    "graphics.save": "Encode a canvas as a PNG file. Requires the fs capability.",
    "graphics.present": "Hand a canvas to the host's presentation backend. Requires the ui capability and an attached backend.",
    "text.char_at": "Return the single-character String at an index.",
    "text.is_alpha": "True if a one-character String is a Unicode letter.",
    "text.ord": "Unicode code point of a one-character String.",
    "text.chr": "One-character String for a Unicode code point.",
    "abs": "Absolute value of an Int or Float.",
    "float": "Convert an Int or Float to Float (no implicit conversion is performed elsewhere).",
    "int": "Truncate a Float toward zero, or pass an Int through unchanged.",
    "panic": "Abort execution with an uncatchable runtime fault.",
    "type_name": "Display name of a value's runtime type.",
    # colour
    "colour.srgb": "Construct a colour from gamma-encoded sRGB components in [0, 1].",
    "colour.oklab": "Construct a colour from Oklab coordinates.",
    "colour.oklch": "Construct a colour from cylindrical Oklch coordinates (hue in degrees).",
    "colour.from_hex": "Parse #rrggbb or #rrggbbaa into a colour.",
    "colour.mix": "Interpolate two colours in Oklab at t in [0, 1].",
    "colour.lighten": "Increase Oklab lightness by amount.",
    "colour.darken": "Decrease Oklab lightness by amount.",
    "colour.rotate_hue": "Rotate the Oklch hue by degrees.",
    "colour.complement": "Colour with the hue rotated by 180 degrees.",
    "colour.luminance": "WCAG 2 relative luminance.",
    "colour.contrast": "WCAG contrast ratio between two colours (1 to 21).",
    "colour.palette": "Deterministic palette of count perceptually spaced colours.",
    "colour.to_css": "CSS string for a colour (sRGB or hex fallback).",
    # filesystem
    "fs.read_text": "Read a UTF-8 text file inside the sandbox. Requires the fs capability.",
    "fs.write_text": "Write a UTF-8 text file inside the sandbox. Requires the fs capability.",
    "fs.create_dir": "Create a directory (and missing parents) inside the filesystem sandbox. Requires the fs capability.",
    # graphics
    "graphics.canvas": "Create an RGBA canvas of the given integer dimensions.",
    "graphics.clear": "Replace every pixel with a colour.",
    "graphics.fill": "Alias of graphics.clear.",
    "graphics.rect": "Draw an anti-aliased axis-aligned rectangle.",
    "graphics.circle": "Draw an anti-aliased filled circle.",
    "graphics.line": "Draw an anti-aliased line segment with a width.",
    "graphics.gradient": "Fill a canvas with a multi-stop perceptual gradient at an angle.",
    "graphics.glow": "Add a soft radial light glow to a canvas.",
    # math
    "math.pi": "The constant pi.",
    "math.e": "Euler's number.",
    "math.sqrt": "Square root; negative inputs are runtime errors.",
    "math.pow": "Raise base to exponent as Floats.",
    "math.exp": "e raised to x.",
    "math.log": "Natural logarithm; non-positive inputs are runtime errors.",
    "math.log2": "Base-2 logarithm.",
    "math.sin": "Sine of an angle in radians.",
    "math.cos": "Cosine of an angle in radians.",
    "math.tan": "Tangent of an angle in radians.",
    "math.atan2": "Angle in radians for y/x, using both signs.",
    "math.floor": "Largest Int less than or equal to x.",
    "math.ceil": "Smallest Int greater than or equal to x.",
    "math.round": "Nearest Int, rounding halfway cases away from zero.",
    "math.min": "Smaller of two Floats.",
    "math.max": "Larger of two Floats.",
    "math.clamp": "Clamp x into [low, high].",
    # motion
    "motion.ease": "Evaluate a named easing curve at t in [0, 1].",
    "motion.spring_steps": "Simulate a damped spring and return step samples.",
    # neural networks
    "nn.parameter": "Create a Float32 tensor that tracks gradients. Requires compute.",
    "nn.mse": "Mean-squared error between two equally shaped tensors.",
    "nn.cross_entropy": "Mean cross-entropy between logits and one-hot labels.",
    "nn.max_abs_diff": "Maximum absolute elementwise difference between two tensors.",
    "nn.xor": "The canonical four-example XOR dataset.",
    "nn.spiral": "Generate a deterministic two-arm spiral dataset.",
    "nn.dataset": "Wrap feature and label tensors as a dataset.",
    "nn.train": "Train a model and return per-epoch losses (the report is available to the host).",
    "nn.accuracy": "Accuracy of a trained model on a dataset.",
    "nn.loss": "Loss of a trained model on a dataset for a named objective.",
    "nn.predict": "Logits for one input tensor.",
    "nn.save": "Serialise a model to a .ज्ञान file. Requires fs and compute.",
    "nn.load": "Load a model from a .ज्ञान file. Requires fs and compute.",
    # process and text
    "process.args": "Command-line arguments passed by the host to the program.",
    "text.is_digit": "True if a one-character String is a Unicode decimal digit.",
    "text.is_alnum": "True if a one-character String is a Unicode letter or decimal digit.",
    "text.is_mark": "True if a one-character String is a Unicode combining mark (including Devanagari mātrās).",
    "text.is_space": "True if a one-character String is Unicode whitespace.",
    "text.split_lines": "Split a String on line boundaries, discarding the separators.",
}

#: Namespaces that can be imported with ``use``. Derived from NATIVES.
_ns_sets: dict[str, set[str]] = {}
for _name in NATIVES:
    if "." in _name:
        _ns, _member = _name.split(".", 1)
        _ns_sets.setdefault(_ns, set()).add(_member)
NAMESPACES: dict[str, tuple[str, ...]] = {
    ns: tuple(sorted(members)) for ns, members in _ns_sets.items()
}

GLOBAL_NATIVES: dict[str, tuple[NativeSignature, ...]] = {
    name: sigs for name, sigs in NATIVES.items() if "." not in name
}

#: Properties of built-in types: (type category, property) -> result type.
PROPERTIES: dict[tuple[str, str], T.Type] = {
    ("Tensor", "rank"): I,
    ("Tensor", "shape"): T.ListType(I),
    ("Tensor", "dtype"): S,
    ("Tensor", "size"): I,
    ("Tensor", "grad"): T.TensorType("Float32", None),
    ("Tensor", "requires_grad"): B,
    ("Canvas", "width"): I,
    ("Canvas", "height"): I,
    ("Model", "parameter_count"): I,
    ("Dataset", "size"): I,
    ("Dataset", "features"): T.TensorType("Float32", None),
    ("Dataset", "labels"): T.TensorType("Float32", None),
}

#: Methods of built-in types. ``ELEM`` denotes the receiver's element type and
#: is resolved by the checker; ``TENSOR`` denotes a shape-dynamic tensor.
ELEM = "<elem>"
TENSOR_PLACEHOLDER = "<tensor>"

METHODS: dict[tuple[str, str], tuple[tuple[T.Type | str, ...], T.Type | str | None, str | None]] = {
    # List
    ("List", "len"): ((), I, None),
    ("List", "push"): ((ELEM,), U, None),
    ("List", "pop"): ((), ELEM, None),
    ("List", "get"): ((I,), ELEM, None),
    ("List", "contains"): ((ELEM,), B, None),
    ("List", "index_of"): ((ELEM,), I, None),
    ("List", "join"): ((S,), S, None),
    ("List", "sort"): ((), U, None),
    ("List", "reverse"): ((), U, None),
    # String
    ("String", "len"): ((), I, None),
    ("String", "upper"): ((), S, None),
    ("String", "lower"): ((), S, None),
    ("String", "trim"): ((), S, None),
    ("String", "contains"): ((S,), B, None),
    ("String", "starts_with"): ((S,), B, None),
    ("String", "ends_with"): ((S,), B, None),
    ("String", "split"): ((S,), T.ListType(S), None),
    ("String", "replace"): ((S, S), S, None),
    ("String", "substring"): ((I, I), S, None),
    # Tensor
    ("Tensor", "sum"): ((), F, None),
    ("Tensor", "mean"): ((), F, None),
    ("Tensor", "max"): ((), F, None),
    ("Tensor", "min"): ((), F, None),
    ("Tensor", "exp"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "log"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "sqrt"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "abs"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "relu"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "tanh"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "sigmoid"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "softmax"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "reshape"): ((T.ListType(I),), TENSOR_PLACEHOLDER, None),
    ("Tensor", "transpose"): ((), TENSOR_PLACEHOLDER, None),
    ("Tensor", "matmul"): ((TENSOR_PLACEHOLDER,), TENSOR_PLACEHOLDER, None),
    ("Tensor", "backward"): ((), U, "compute"),
    ("Tensor", "zero_grad"): ((), U, "compute"),
    ("Tensor", "item"): ((), F, None),
    # Range / Dataset / Canvas / Model / Color
    ("Range", "len"): ((), I, None),
    ("Dataset", "features"): ((), T.TensorType("Float32", None), None),
    ("Dataset", "labels"): ((), T.TensorType("Float32", None), None),
    ("Dataset", "size"): ((), I, None),
    ("Canvas", "save"): ((S,), U, "fs"),
    ("Model", "predict"): ((T.TensorType("Float32", None),), T.TensorType("Float32", None), "compute"),
    ("Model", "summary"): ((), S, None),
    ("Color", "css"): ((), S, None),
    ("Color", "luminance"): ((), F, None),
}

#: Model declaration methods: method name -> (param types, return type, capability)
MODEL_DECL_METHODS: dict[str, tuple[tuple[NativeParam, ...], T.Type, str | None]] = {
    "init": ((_p("seed", I, 0),), T.ModelType, "compute"),
}

TRAINING_DECL_METHODS: dict[str, tuple[tuple[NativeParam, ...], T.Type, str | None]] = {
    "run": ((_p("model", MODEL), _p("dataset", DATASET)), T.ListType(F), "compute"),
    "evaluate": ((_p("model", MODEL), _p("dataset", DATASET)), F, "compute"),
}


def resolve_overload(
    overloads: tuple[NativeSignature, ...], arg_types: list[T.Type]
) -> NativeSignature | None:
    """Pick the first overload compatible with ``arg_types`` (exact/assignable matching)."""
    for sig in overloads:
        if len(arg_types) < sig.required_count or len(arg_types) > len(sig.params):
            continue
        ok = True
        for arg, param in zip(arg_types, sig.params):
            if param.ty == ANY:
                continue
            if not T.is_assignable(arg, param.ty):
                ok = False
                break
        if ok:
            return sig
    return None


def namespace_members(ns: str) -> tuple[str, ...]:
    return NAMESPACES.get(ns, ())
