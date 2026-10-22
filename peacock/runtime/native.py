"""Native functions: the bridge between PEACOCK bytecode and its own engines.

These are PEACOCK's standard-library implementations. They call the original
tensor, autodiff, colour, canvas and motion engines in this repository — never a
third-party ML or UI framework.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Any

from peacock.compiler import builtins as B
from peacock.compiler.diagnostics import PanicError, PeacockError, ResourceLimitError, RuntimeError_
from peacock.frontend.canvas import Canvas, CanvasError
from peacock.frontend.colour import (
    Color, ColorError, delta_e_2000, map_gamut, mix_weighted, palette,
)
from peacock.frontend.easing import ease
from peacock.frontend.scene3d import Scene3D, Scene3DError
from peacock.frontend.ui import UIBuilder, UIError
from peacock.frontend.png import encode_png
from peacock.frontend.spring import SpringConfig, settle
from peacock.intelligence.agent import Agent, AgentError
from peacock.intelligence.datasets import Dataset, make_dataset, spiral_dataset, xor_dataset
from peacock.intelligence.layers import Model
from peacock.intelligence.serialization import model_from_bytes, model_to_bytes
from peacock.intelligence.tensor import Tensor, TensorError, absolute
from peacock.intelligence import tensor as T
from peacock.intelligence.training import evaluate_accuracy, evaluate_loss, train_model
from peacock.runtime.errors import VMFault
from peacock.runtime.values import UNIT, RangeValue, format_value, is_int, type_name
from peacock.sanskrit import internalise_enum, surface, surface_enum
from peacock.vyakarana import (
    EXPECTED_SUTRAS, EXECUTABLE_RULE_IDS, CorpusError, PratyaharaError,
    SandhiError, expand as expand_pratyahara, get_sutra, join as sandhi_join,
    literature as grammar_literature, search as search_sutras,
)

# ---------------------------------------------------------------------------
# Capability metadata
# ---------------------------------------------------------------------------
NATIVE_CAPABILITIES: dict[str, str | None] = {}
for _name, _sigs in B.NATIVES.items():
    _caps = {sig.capability for sig in _sigs if sig.capability}
    if len(_caps) > 1:  # pragma: no cover - catalog invariant
        raise RuntimeError(f"native '{_name}' has inconsistent capability metadata")
    NATIVE_CAPABILITIES[_name] = next(iter(_caps), None)

METHOD_CAPABILITIES: dict[str, str] = {}
for (_category, _method), (_params, _ret, _cap) in B.METHODS.items():
    if _cap:
        METHOD_CAPABILITIES[_method] = _cap


def native_capability(name: str) -> str | None:
    return NATIVE_CAPABILITIES.get(name) or None


def method_capability(name: str) -> str | None:
    return METHOD_CAPABILITIES.get(name) or None


# ---------------------------------------------------------------------------
# Argument checking
# ---------------------------------------------------------------------------
def _fail(message: str, code: str = "PE4002") -> None:
    if code == "PE4003":
        raise ResourceLimitError(message)
    raise VMFault(message, code)


def _need_tensor(value, where: str) -> Tensor:
    if not isinstance(value, Tensor):
        _fail(f"{where} expects a आयाम, got {type_name(value)}")
    return value


def _need_color(value, where: str) -> Color:
    if not isinstance(value, Color):
        _fail(f"{where} expects a वर्ण, got {type_name(value)}")
    return value


def _need_canvas(value, where: str) -> Canvas:
    if not isinstance(value, Canvas):
        _fail(f"{where} expects a चित्रपट, got {type_name(value)}")
    return value


def _need_model(value, where: str) -> Model:
    if not isinstance(value, Model):
        _fail(f"{where} expects a प्रतिमानप्रकार, got {type_name(value)}")
    return value


def _need_dataset(value, where: str) -> Dataset:
    if not isinstance(value, Dataset):
        _fail(f"{where} expects a दत्तसमूह, got {type_name(value)}")
    return value


def _need_ui(value, where: str) -> UIBuilder:
    if not isinstance(value, UIBuilder):
        _fail(f"{where} expects a दृश्यरचना, got {type_name(value)}")
    return value


def _need_scene(value, where: str) -> Scene3D:
    if not isinstance(value, Scene3D):
        _fail(f"{where} expects a त्रिअयामदृश्य, got {type_name(value)}")
    return value


def _need_agent(value, where: str) -> Agent:
    if not isinstance(value, Agent):
        _fail(f"{where} expects an अभिकर्तृप्रकार, got {type_name(value)}")
    return value


def _need_int(value, where: str) -> int:
    if not is_int(value):
        _fail(f"{where} expects a पूर्णाङ्क, got {type_name(value)}")
    return value


def _need_float(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{where} expects a दशमलव, got {type_name(value)}")
    return float(value)


def _need_str(value, where: str) -> str:
    if not isinstance(value, str):
        _fail(f"{where} expects an अक्षरमाला, got {type_name(value)}")
    return value


def _need_list(value, where: str) -> list:
    if not isinstance(value, list):
        _fail(f"{where} expects a सूची, got {type_name(value)}")
    return value


@dataclass
class NativeContext:
    vm: Any
    host: Any

    @property
    def image(self) -> dict:
        return self.vm.image

    def write(self, text: str) -> None:
        self.vm.write_output(text)


def _wrap_engine_errors(fn, *args):
    try:
        return fn(*args)
    except PeacockError:
        raise
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc
    except ColorError as exc:
        raise VMFault(str(exc), "PE7001") from exc
    except CanvasError as exc:
        raise VMFault(str(exc), "PE7001") from exc
    except (ValueError, TypeError, ArithmeticError, OverflowError) as exc:
        raise VMFault(str(exc) or exc.__class__.__name__, "PE4002") from exc


# ---------------------------------------------------------------------------
# Global functions
# ---------------------------------------------------------------------------
def _print(ctx: NativeContext, args):
    ctx.write(format_value(args[0]) + "\n")
    return UNIT


def _str(ctx, args):
    return format_value(args[0])


def _len(ctx, args):
    value = args[0]
    if isinstance(value, (list, str)):
        return len(value)
    if isinstance(value, Tensor):
        return value.size
    if isinstance(value, RangeValue):
        return len(value)
    if isinstance(value, Dataset):
        return len(value)
    _fail(f"दैर्घ्य() is not defined for {type_name(value)}")
    return 0


def _range(ctx, args):
    start = _need_int(args[0], "range start")
    end = _need_int(args[1], "range end")
    return RangeValue(start, end)


def _tensor(ctx, args):
    value = args[0]
    if isinstance(value, Tensor):
        return value
    try:
        tensor = Tensor.from_nested(value)
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc
    if tensor.size > ctx.host.max_tensor_elements:
        _fail(
            f"tensor has {tensor.size} elements, exceeding the host limit of "
            f"{ctx.host.max_tensor_elements}",
            "PE4003",
        )
    return tensor


def _int(ctx, args):
    value = args[0]
    if is_int(value):
        return value
    if isinstance(value, float):
        truncated = int(value)
        if not (-(2**63) <= truncated < 2**63):
            _fail("पूर्णाङ्क conversion overflow", "PE4004")
        return truncated
    _fail("पूर्णीकरण() expects पूर्णाङ्क or दशमलव")


def _float(ctx, args):
    value = args[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("दशमलवीकरण() expects पूर्णाङ्क or दशमलव")
    return float(value)


def _abs(ctx, args):
    value = args[0]
    if is_int(value):
        if value == -(2**63):
            _fail("integer overflow in abs()", "PE4004")
        return abs(value)
    if isinstance(value, float):
        return abs(value)
    _fail("निरपेक्ष() expects पूर्णाङ्क or दशमलव")


def _type_name(ctx, args):
    from peacock.runtime.values import type_name

    return type_name(args[0])


def _panic(ctx, args):
    message = _need_str(args[0], "panic message")
    raise PanicError(message)


def _math_unary(fn, domain=None, name="function"):
    def impl(ctx, args):
        x = _need_float(args[0], f"math.{name}")
        if domain is not None and not domain(x):
            _fail(f"math.{name} argument out of domain: {x}")
        try:
            return fn(x)
        except (ValueError, OverflowError) as exc:
            raise VMFault(f"math.{name}: {exc}") from exc

    return impl


def _round_half_away(x: float) -> int:
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


def _math_impls() -> dict[str, Any]:
    return {
        "math.sqrt": _math_unary(math.sqrt, lambda x: x >= 0, "sqrt"),
        "math.exp": _math_unary(math.exp, None, "exp"),
        "math.log": _math_unary(math.log, lambda x: x > 0, "log"),
        "math.log2": _math_unary(math.log2, lambda x: x > 0, "log2"),
        "math.sin": _math_unary(math.sin, None, "sin"),
        "math.cos": _math_unary(math.cos, None, "cos"),
        "math.tan": _math_unary(math.tan, None, "tan"),
        "math.floor": lambda ctx, args: int(math.floor(_need_float(args[0], "math.floor"))),
        "math.ceil": lambda ctx, args: int(math.ceil(_need_float(args[0], "math.ceil"))),
        "math.round": lambda ctx, args: _round_half_away(_need_float(args[0], "math.round")),
        "math.atan2": lambda ctx, args: math.atan2(
            _need_float(args[0], "atan2 y"), _need_float(args[1], "atan2 x")
        ),
        "math.pow": lambda ctx, args: _wrap_engine_errors(
            lambda: math.pow(
                _need_float(args[0], "base"), _need_float(args[1], "exponent")
            )
        ),
        "math.min": lambda ctx, args: min(
            _need_float(args[0], "min a"), _need_float(args[1], "min b")
        ),
        "math.max": lambda ctx, args: max(
            _need_float(args[0], "max a"), _need_float(args[1], "max b")
        ),
        "math.clamp": lambda ctx, args: max(
            _need_float(args[1], "clamp low"),
            min(_need_float(args[2], "clamp high"), _need_float(args[0], "clamp x")),
        ),
        "math.pi": lambda ctx, args: math.pi,
        "math.e": lambda ctx, args: math.e,
    }


# -- colour -----------------------------------------------------------------
def _colour_srgb(ctx, args):
    r = _need_float(args[0], "colour.srgb r")
    g = _need_float(args[1], "colour.srgb g")
    b = _need_float(args[2], "colour.srgb b")
    alpha = _need_float(args[3], "colour.srgb alpha")
    return _wrap_engine_errors(Color.from_srgb, r, g, b, alpha)


def _colour_oklch(ctx, args):
    L = _need_float(args[0], "colour.oklch L")
    C = _need_float(args[1], "colour.oklch C")
    h = _need_float(args[2], "colour.oklch h")
    alpha = _need_float(args[3], "colour.oklch alpha")
    if C < 0:
        _fail("Oklch chroma must be non-negative")
    return _wrap_engine_errors(Color.from_oklch, L, C, h, alpha)


def _colour_oklab(ctx, args):
    return _wrap_engine_errors(
        Color.from_oklab,
        _need_float(args[0], "colour.oklab L"),
        _need_float(args[1], "colour.oklab a"),
        _need_float(args[2], "colour.oklab b"),
        _need_float(args[3], "colour.oklab alpha"),
    )


def _colour_from_hex(ctx, args):
    return _wrap_engine_errors(Color.from_hex, _need_str(args[0], "colour.from_hex"))


def _colour_mix(ctx, args):
    a = _need_color(args[0], "colour.mix a")
    b = _need_color(args[1], "colour.mix b")
    t = _need_float(args[2], "colour.mix t")
    if not (0.0 <= t <= 1.0):
        _fail("colour.mix t must be in [0, 1]")
    return a.mix(b, t, "oklab")


def _colour_lighten(ctx, args):
    return _need_color(args[0], "lighten").lighten(_need_float(args[1], "lighten amount"))


def _colour_darken(ctx, args):
    return _need_color(args[0], "darken").darken(_need_float(args[1], "darken amount"))


def _colour_rotate(ctx, args):
    return _need_color(args[0], "rotate_hue").rotate_hue(_need_float(args[1], "degrees"))


def _colour_complement(ctx, args):
    return _need_color(args[0], "complement").complement()


def _colour_css(ctx, args):
    return _need_color(args[0], "to_css").to_css()


def _colour_luminance(ctx, args):
    return _need_color(args[0], "luminance").luminance()


def _colour_contrast(ctx, args):
    a = _need_color(args[0], "contrast a")
    b = _need_color(args[1], "contrast b")
    return a.contrast_ratio(b)


def _colour_palette(ctx, args):
    count = _need_int(args[0], "palette count")
    seed = _need_int(args[1], "palette seed")
    return _wrap_engine_errors(palette, count, seed)


def _colour_mix_many(ctx, args):
    colors = [_need_color(value, "colour.mix_many colours") for value in _need_list(args[0], "colour.mix_many colours")]
    weights = [_need_float(value, "colour.mix_many weights") for value in _need_list(args[1], "colour.mix_many weights")]
    space = internalise_enum(_need_str(args[2], "colour.mix_many space"))
    return _wrap_engine_errors(mix_weighted, colors, weights, space)


def _colour_delta_e(ctx, args):
    return delta_e_2000(_need_color(args[0], "colour.delta_e a"), _need_color(args[1], "colour.delta_e b"))


def _colour_gamut_map(ctx, args):
    return map_gamut(_need_color(args[0], "colour.gamut_map"))


# -- graphics ---------------------------------------------------------------
def _graphics_canvas(ctx, args):
    width = _need_int(args[0], "canvas width")
    height = _need_int(args[1], "canvas height")
    return _wrap_engine_errors(Canvas, width, height)


def _graphics_clear(ctx, args):
    canvas = _need_canvas(args[0], "clear canvas")
    color = _need_color(args[1], "clear colour")
    canvas.clear(color)
    return UNIT


def _graphics_fill(ctx, args):
    canvas = _need_canvas(args[0], "fill canvas")
    color = _need_color(args[1], "fill colour")
    canvas.fill(color)
    return UNIT


def _graphics_rect(ctx, args):
    canvas = _need_canvas(args[0], "rect canvas")
    x = _need_float(args[1], "rect x")
    y = _need_float(args[2], "rect y")
    w = _need_float(args[3], "rect width")
    h = _need_float(args[4], "rect height")
    color = _need_color(args[5], "rect colour")
    canvas.rect(x, y, w, h, color)
    return UNIT


def _graphics_circle(ctx, args):
    canvas = _need_canvas(args[0], "circle canvas")
    cx = _need_float(args[1], "circle cx")
    cy = _need_float(args[2], "circle cy")
    r = _need_float(args[3], "circle radius")
    color = _need_color(args[4], "circle colour")
    canvas.circle(cx, cy, r, color)
    return UNIT


def _graphics_line(ctx, args):
    canvas = _need_canvas(args[0], "line canvas")
    x0, y0, x1, y1, width = (_need_float(args[i], f"line arg {i}") for i in range(1, 6))
    color = _need_color(args[6], "line colour")
    canvas.line(x0, y0, x1, y1, width, color)
    return UNIT


def _graphics_gradient(ctx, args):
    canvas = _need_canvas(args[0], "gradient canvas")
    colors = _need_list(args[1], "gradient colours")
    for c in colors:
        _need_color(c, "gradient colours")
    angle = _need_float(args[2], "gradient angle")
    canvas.gradient(colors, angle)
    return UNIT


def _graphics_glow(ctx, args):
    canvas = _need_canvas(args[0], "glow canvas")
    cx = _need_float(args[1], "glow cx")
    cy = _need_float(args[2], "glow cy")
    radius = _need_float(args[3], "glow radius")
    color = _need_color(args[4], "glow colour")
    canvas.glow(cx, cy, radius, color)
    return UNIT


def _graphics_aurora(ctx, args):
    canvas = _need_canvas(args[0], "aurora canvas")
    time = _need_float(args[1], "aurora time")
    seed = _need_int(args[2], "aurora seed")
    canvas.aurora(time, seed)
    return UNIT


def _graphics_save(ctx, args):
    canvas = _need_canvas(args[0], "save canvas")
    path = _need_str(args[1], "save path")
    data = encode_png(canvas)
    ctx.host.write_bytes(path, data)
    return UNIT


def _graphics_present(ctx, args):
    canvas = _need_canvas(args[0], "present canvas")
    ctx.host.present(canvas)
    return UNIT


# -- process & filesystem ---------------------------------------------------
def _process_args(ctx, args):
    return list(ctx.vm.argv)


def _fs_read_text(ctx, args):
    path = _need_str(args[0], "fs.read_text path")
    data = ctx.host.read_bytes(path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VMFault(f"file '{path}' is not valid UTF-8: {exc}", "PE5003") from exc


def _fs_write_text(ctx, args):
    path = _need_str(args[0], "fs.write_text path")
    content = _need_str(args[1], "fs.write_text content")
    ctx.host.write_bytes(path, content.encode("utf-8"))
    return UNIT


def _fs_create_dir(ctx, args):
    path = _need_str(args[0], "fs.create_dir path")
    ctx.host.create_directory(path)
    return UNIT


# -- neural networks --------------------------------------------------------
def _nn_parameter(ctx, args):
    value = args[0]
    if isinstance(value, Tensor):
        tensor = value.to("Float32")
        tensor.requires_grad = True
        return tensor
    try:
        tensor = Tensor.from_nested(value, dtype="Float32", requires_grad=True)
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc
    if tensor.size > ctx.host.max_tensor_elements:
        _fail("parameter tensor exceeds the host element limit", "PE4003")
    return tensor


def _nn_mse(ctx, args):
    predictions = _need_tensor(args[0], "nn.mse predictions")
    targets = _need_tensor(args[1], "nn.mse targets")
    try:
        from peacock.intelligence.training import mse_loss

        return mse_loss(predictions, targets)
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc


def _nn_cross_entropy(ctx, args):
    logits = _need_tensor(args[0], "nn.cross_entropy logits")
    labels = _need_tensor(args[1], "nn.cross_entropy labels")
    try:
        from peacock.intelligence.training import cross_entropy_loss

        return cross_entropy_loss(logits, labels)
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc


def _nn_max_abs_diff(ctx, args):
    a = _need_tensor(args[0], "nn.max_abs_diff a")
    b = _need_tensor(args[1], "nn.max_abs_diff b")
    try:
        return T.max_abs_diff(a, b)
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc


def _nn_xor(ctx, args):
    return xor_dataset()


def _nn_spiral(ctx, args):
    per_class = _need_int(args[0], "spiral per_class")
    noise = _need_float(args[1], "spiral noise")
    seed = _need_int(args[2], "spiral seed")
    if per_class < 1 or 2 * per_class > ctx.host.max_dataset_samples:
        _fail("spiral dataset exceeds the host sample limit", "PE4003")
    return _wrap_engine_errors(spiral_dataset, per_class, noise, seed)


def _nn_dataset(ctx, args):
    features = _need_tensor(args[0], "nn.dataset features")
    labels = _need_tensor(args[1], "nn.dataset labels")
    if features.shape[0] > ctx.host.max_dataset_samples:
        _fail("dataset exceeds the host sample limit", "PE4003")
    return _wrap_engine_errors(make_dataset, features, labels, "custom")


def _nn_train(ctx, args):
    model = _need_model(args[0], "nn.train model")
    dataset = _need_dataset(args[1], "nn.train dataset")
    objective = internalise_enum(_need_str(args[2], "nn.train loss"))
    optimiser = internalise_enum(_need_str(args[3], "nn.train optimiser"))
    epochs = _need_int(args[4], "nn.train epochs")
    learning_rate = _need_float(args[5], "nn.train learning_rate")
    batch_size = _need_int(args[6], "nn.train batch_size")
    seed = _need_int(args[7], "nn.train seed")
    if epochs > ctx.host.max_training_epochs:
        _fail(
            f"epochs {epochs} exceeds the host training limit of {ctx.host.max_training_epochs}",
            "PE4003",
        )
    if len(dataset) > ctx.host.max_dataset_samples:
        _fail("dataset exceeds the host sample limit", "PE4003")
    report = _wrap_engine_errors(
        train_model,
        model,
        dataset,
        objective=objective,
        optimiser=optimiser,
        epochs=epochs,
        learning_rate=learning_rate,
        batch_size=batch_size,
        seed=seed,
    )
    ctx.vm.last_training_report = report
    return list(report.losses)


def _nn_accuracy(ctx, args):
    model = _need_model(args[0], "nn.accuracy model")
    dataset = _need_dataset(args[1], "nn.accuracy dataset")
    return _wrap_engine_errors(evaluate_accuracy, model, dataset)


def _nn_loss(ctx, args):
    model = _need_model(args[0], "nn.loss model")
    dataset = _need_dataset(args[1], "nn.loss dataset")
    objective = internalise_enum(_need_str(args[2], "nn.loss objective"))
    return _wrap_engine_errors(evaluate_loss, model, dataset, objective)


def _nn_predict(ctx, args):
    model = _need_model(args[0], "nn.predict model")
    x = _need_tensor(args[1], "nn.predict input")
    return _wrap_engine_errors(model.predict, x)


def _nn_save(ctx, args):
    model = _need_model(args[0], "nn.save model")
    path = _need_str(args[1], "nn.save path")
    data = _wrap_engine_errors(
        model_to_bytes, model, {"saved_by": "nn.save", "summary": model.summary()}
    )
    ctx.host.write_bytes(path, data)
    return UNIT


def _nn_load(ctx, args):
    path = _need_str(args[0], "nn.load path")
    data = ctx.host.read_bytes(path)
    model, _meta = _wrap_engine_errors(model_from_bytes, data)
    return model


# -- text -------------------------------------------------------------------
def _text_char_at(ctx, args):
    value = _need_str(args[0], "text.char_at")
    index = _need_int(args[1], "text.char_at index")
    if not (0 <= index < len(value)):
        _fail(f"index {index} out of bounds for अक्षरमाला of length {len(value)}")
    return value[index]


def _single_char(value: str, where: str) -> str:
    if len(value) != 1:
        _fail(f"{where} expects a one-character अक्षरमाला, got length {len(value)}")
    return value


def _text_is_alpha(ctx, args):
    ch = _single_char(_need_str(args[0], "text.is_alpha"), "text.is_alpha")
    return ch.isalpha()


def _text_is_digit(ctx, args):
    ch = _single_char(_need_str(args[0], "text.is_digit"), "text.is_digit")
    return ch.isdecimal()


def _text_is_alnum(ctx, args):
    ch = _single_char(_need_str(args[0], "text.is_alnum"), "text.is_alnum")
    return ch.isalpha() or ch.isdecimal()


def _text_is_mark(ctx, args):
    ch = _single_char(_need_str(args[0], "text.is_mark"), "text.is_mark")
    return unicodedata.category(ch) in {"Mn", "Mc", "Me"}


def _text_is_space(ctx, args):
    ch = _single_char(_need_str(args[0], "text.is_space"), "text.is_space")
    return ch.isspace()


def _text_ord(ctx, args):
    ch = _single_char(_need_str(args[0], "text.ord"), "text.ord")
    return ord(ch)


def _text_chr(ctx, args):
    code = _need_int(args[0], "text.chr code")
    if not (0 <= code <= 0x10FFFF):
        _fail("text.chr code point out of range")
    if 0xD800 <= code <= 0xDFFF:
        _fail("text.chr refuses to produce a surrogate code point")
    return chr(code)


def _text_split_lines(ctx, args):
    return _need_str(args[0], "text.split_lines").splitlines()


# -- Sanskrit grammar --------------------------------------------------------
def _grammar_sutra(ctx, args):
    return _wrap_engine_errors(lambda: get_sutra(_need_str(args[0], "vyakarana.sutra id")).display())


def _grammar_count(ctx, args):
    return EXPECTED_SUTRAS


def _grammar_search(ctx, args):
    query = _need_str(args[0], "vyakarana.search query")
    limit = _need_int(args[1], "vyakarana.search limit")
    return _wrap_engine_errors(lambda: [sutra.display() for sutra in search_sutras(query, limit)])


def _grammar_pratyahara(ctx, args):
    return _wrap_engine_errors(lambda: list(expand_pratyahara(_need_str(args[0], "vyakarana.pratyahara"))))


def _grammar_sandhi(ctx, args):
    left, right = _need_str(args[0], "sandhi left"), _need_str(args[1], "sandhi right")
    return _wrap_engine_errors(lambda: sandhi_join(left, right).text)


def _grammar_sandhi_rule(ctx, args):
    left, right = _need_str(args[0], "sandhi left"), _need_str(args[1], "sandhi right")
    return _wrap_engine_errors(lambda: sandhi_join(left, right).rule_id)


def _grammar_anuvritti(ctx, args):
    return _wrap_engine_errors(lambda: [ref.display() for ref in get_sutra(_need_str(args[0], "anuvritti id")).anuvritti])


def _grammar_adhikara(ctx, args):
    return _wrap_engine_errors(lambda: [ref.display() for ref in get_sutra(_need_str(args[0], "adhikara id")).adhikara])


def _grammar_literature(ctx, args):
    return list(grammar_literature())


def _grammar_coverage(ctx, args):
    return len(EXECUTABLE_RULE_IDS)


# -- native UI builder --------------------------------------------------------
def _ui_create(ctx, args):
    return _wrap_engine_errors(UIBuilder, _need_str(args[0], "ui title"), _need_int(args[1], "ui width"), _need_int(args[2], "ui height"), _need_color(args[3], "ui background"))


def _ui_panel(ctx, args):
    ui = _need_ui(args[0], "ui.panel")
    values = [_need_float(args[index], "ui.panel bounds") for index in range(2, 6)]
    return _wrap_engine_errors(ui.panel, _need_int(args[1], "ui parent"), *values, _need_color(args[6], "panel background"))


def _ui_text(ctx, args):
    ui = _need_ui(args[0], "ui.text")
    return _wrap_engine_errors(
        ui.text, _need_int(args[1], "ui parent"), _need_str(args[2], "ui text"),
        *[_need_float(args[index], "ui.text bounds") for index in range(3, 7)],
        _need_color(args[7], "text foreground"), _need_float(args[8], "text size"),
    )


def _ui_button(ctx, args):
    ui = _need_ui(args[0], "ui.button")
    return _wrap_engine_errors(
        ui.button, _need_int(args[1], "ui parent"), _need_str(args[2], "button label"),
        *[_need_float(args[index], "ui.button bounds") for index in range(3, 7)],
        _need_color(args[7], "button background"), _need_color(args[8], "button foreground"),
    )


def _ui_link(ctx, args):
    ui = _need_ui(args[0], "ui.link")
    return _wrap_engine_errors(
        ui.link, _need_int(args[1], "ui parent"), _need_str(args[2], "link label"),
        _need_str(args[3], "link target"),
        *[_need_float(args[index], "ui.link bounds") for index in range(4, 8)],
        _need_color(args[8], "link foreground"), _need_float(args[9], "link size"),
    )


def _ui_flow(ctx, args):
    ui = _need_ui(args[0], "ui.flow")
    direction = internalise_enum(_need_str(args[2], "flow direction"))
    _wrap_engine_errors(ui.flow, _need_int(args[1], "ui parent"), direction, _need_float(args[3], "flow gap"), _need_float(args[4], "flow padding"))
    return UNIT


def _ui_grid(ctx, args):
    ui = _need_ui(args[0], "ui.grid")
    _wrap_engine_errors(ui.grid, _need_int(args[1], "ui parent"), _need_int(args[2], "grid columns"), _need_float(args[3], "grid gap"), _need_float(args[4], "grid padding"))
    return UNIT


def _ui_bounds(ctx, args):
    ui = _need_ui(args[0], "ui.bounds")
    return _wrap_engine_errors(lambda: list(ui.bounds(_need_int(args[1], "ui node"))))


def _ui_hit_test(ctx, args):
    ui = _need_ui(args[0], "ui.hit_test")
    return _wrap_engine_errors(ui.hit_test, _need_float(args[1], "hit x"), _need_float(args[2], "hit y"))


def _ui_audit(ctx, args):
    return _need_ui(args[0], "ui.audit").audit()


def _ui_html(ctx, args):
    return _need_ui(args[0], "ui.to_html").to_html()


def _ui_save(ctx, args):
    ui = _need_ui(args[0], "ui.save")
    path = _need_str(args[1], "ui.save path")
    ctx.host.write_bytes(path, ui.to_html().encode("utf-8"))
    return UNIT


def _ui_node_count(ctx, args):
    return len(_need_ui(args[0], "ui.node_count").nodes)


# -- software 3-D -------------------------------------------------------------
def _scene_create(ctx, args):
    return Scene3D()


def _scene_cube(ctx, args):
    scene = _need_scene(args[0], "scene3d.cube")
    return _wrap_engine_errors(scene.cube, *[_need_float(args[index], "cube") for index in range(1, 5)], _need_color(args[5], "cube colour"))


def _scene_sphere(ctx, args):
    scene = _need_scene(args[0], "scene3d.sphere")
    return _wrap_engine_errors(
        scene.sphere, *[_need_float(args[index], "sphere") for index in range(1, 5)],
        _need_color(args[5], "sphere colour"), _need_int(args[6], "sphere segments"), _need_int(args[7], "sphere rings"),
    )


def _scene_light(ctx, args):
    scene = _need_scene(args[0], "scene3d.light")
    _wrap_engine_errors(scene.light, *[_need_float(args[index], "light") for index in range(1, 4)], _need_color(args[4], "light colour"), _need_float(args[5], "light intensity"))
    return UNIT


def _scene_rotate(ctx, args):
    scene = _need_scene(args[0], "scene3d.rotate")
    _wrap_engine_errors(scene.rotate, _need_int(args[1], "scene object"), *[_need_float(args[index], "rotation") for index in range(2, 5)])
    return UNIT


def _scene_render(ctx, args):
    scene = _need_scene(args[0], "scene3d.render")
    canvas = _need_canvas(args[1], "scene3d.render canvas")
    _wrap_engine_errors(scene.render, canvas, *[_need_float(args[index], "camera") for index in range(2, 6)])
    return UNIT


def _scene_triangle_count(ctx, args):
    return _need_scene(args[0], "scene3d.triangle_count").triangle_count


# -- bounded native agents ----------------------------------------------------
def _agent_create(ctx, args):
    return _wrap_engine_errors(Agent, _need_str(args[0], "agent goal key"), _need_str(args[1], "agent goal value"), _need_int(args[2], "agent max steps"))


def _agent_fact(ctx, args):
    agent = _need_agent(args[0], "agent.fact")
    _wrap_engine_errors(agent.fact, _need_str(args[1], "fact key"), _need_str(args[2], "fact value"))
    return UNIT


def _agent_rule(ctx, args):
    agent = _need_agent(args[0], "agent.rule")
    return _wrap_engine_errors(
        agent.rule, *[_need_str(args[index], "agent rule") for index in range(1, 6)],
        _need_float(args[6], "rule priority"), _need_float(args[7], "rule cost"),
    )


def _agent_plan(ctx, args):
    agent = _need_agent(args[0], "agent.plan")
    actions = _wrap_engine_errors(agent.plan)
    if actions is None:
        agent.status = "stalled"
        return []
    return actions


def _agent_run(ctx, args):
    return _wrap_engine_errors(_need_agent(args[0], "agent.run").run)


def _agent_get(ctx, args):
    agent = _need_agent(args[0], "agent.get")
    return _wrap_engine_errors(agent.get, _need_str(args[1], "agent key"))


def _agent_status(ctx, args):
    return surface_enum(_need_agent(args[0], "agent.status").status)


def _agent_trace(ctx, args):
    return _need_agent(args[0], "agent.trace").trace()


def _agent_facts(ctx, args):
    return _need_agent(args[0], "agent.facts").fact_lines()


# -- motion -----------------------------------------------------------------
def _motion_spring_steps(ctx, args):
    start = _need_float(args[0], "spring start")
    target = _need_float(args[1], "spring target")
    stiffness = _need_float(args[2], "spring stiffness")
    damping = _need_float(args[3], "spring damping")
    steps = _need_int(args[4], "spring steps")
    dt = _need_float(args[5], "spring dt")
    if steps < 0 or steps > 1_000_000:
        _fail("spring steps must be between 0 and 1,000,000", "PE4003")
    config = _wrap_engine_errors(SpringConfig, stiffness, damping, 1.0)
    return _wrap_engine_errors(settle, start, target, config, steps, dt)


def _motion_ease(ctx, args):
    name = internalise_enum(_need_str(args[0], "ease name"))
    return _wrap_engine_errors(ease, name, _need_float(args[1], "ease t"))


# ---------------------------------------------------------------------------
# Method dispatch
# ---------------------------------------------------------------------------
def call_method(ctx: NativeContext, receiver, name: str, args: list):
    try:
        if isinstance(receiver, list):
            return _list_method(receiver, name, args)
        if isinstance(receiver, str):
            return _string_method(receiver, name, args)
        if isinstance(receiver, Tensor):
            return _tensor_method(receiver, name, args)
        if isinstance(receiver, RangeValue):
            if name == "len" and not args:
                return len(receiver)
        if isinstance(receiver, Color):
            if name == "css" and not args:
                return receiver.to_css()
            if name == "luminance" and not args:
                return receiver.luminance()
        if isinstance(receiver, Canvas):
            if name == "save":
                return _graphics_save(ctx, [receiver, _need_str(args[0] if args else None, "save path")])
        if isinstance(receiver, Model):
            if name == "predict":
                return _nn_predict(ctx, [receiver, args[0] if args else None])
            if name == "summary":
                return receiver.summary()
        if isinstance(receiver, Dataset):
            if name == "size":
                return len(receiver)
            if name == "features":
                return receiver.features
            if name == "labels":
                return receiver.labels
        _fail(f"{type_name(receiver)} has no method '{surface(name)}'")
    except TensorError as exc:
        raise VMFault(str(exc), "PE6001") from exc
    except (ColorError, CanvasError) as exc:
        raise VMFault(str(exc), "PE7001") from exc
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise VMFault(str(exc), "PE4002") from exc
    return UNIT


def _list_method(receiver: list, name: str, args: list):
    if name == "len":
        return len(receiver)
    if name == "push":
        receiver.append(args[0])
        return UNIT
    if name == "pop":
        if not receiver:
            _fail("निष्कासय() on an empty सूची", "PE4002")
        return receiver.pop()
    if name == "get":
        idx = _need_int(args[0], "List.get index")
        if not (0 <= idx < len(receiver)):
            _fail(f"index {idx} out of bounds for सूची of length {len(receiver)}", "PE4002")
        return receiver[idx]
    if name == "contains":
        return args[0] in receiver
    if name == "index_of":
        try:
            return receiver.index(args[0])
        except ValueError:
            return -1
    if name == "join":
        sep = _need_str(args[0], "join separator")
        for item in receiver:
            if not isinstance(item, str):
                _fail("संयोजय() requires सूची<अक्षरमाला>")
        return sep.join(receiver)
    if name == "sort":
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in receiver):
            _fail("क्रमय() requires a सूची of पूर्णाङ्क or दशमलव")
        receiver.sort()
        return UNIT
    if name == "reverse":
        receiver.reverse()
        return UNIT
    _fail(f"सूची has no method '{surface(name)}'")
    return UNIT


def _string_method(receiver: str, name: str, args: list):
    if name == "len":
        return len(receiver)
    if name == "upper":
        return receiver.upper()
    if name == "lower":
        return receiver.lower()
    if name == "trim":
        return receiver.strip()
    if name == "contains":
        return _need_str(args[0], "contains") in receiver
    if name == "starts_with":
        return receiver.startswith(_need_str(args[0], "starts_with"))
    if name == "ends_with":
        return receiver.endswith(_need_str(args[0], "ends_with"))
    if name == "split":
        return receiver.split(_need_str(args[0], "split separator"))
    if name == "replace":
        return receiver.replace(_need_str(args[0], "replace old"), _need_str(args[1], "replace new"))
    if name == "substring":
        start = _need_int(args[0], "substring start")
        end = _need_int(args[1], "substring end")
        if not (0 <= start <= end <= len(receiver)):
            _fail(f"substring bounds [{start}, {end}) invalid for string of length {len(receiver)}")
        return receiver[start:end]
    _fail(f"अक्षरमाला has no method '{surface(name)}'")
    return ""


def _tensor_method(receiver: Tensor, name: str, args: list):
    if name in ("sum", "mean", "max", "min") and not args:
        if name == "sum":
            return float(T.sum_all(receiver).item())
        if name == "mean":
            return float(T.mean_all(receiver).item())
        if name == "max":
            return float(T.max_value(receiver))
        return float(T.min_value(receiver))
    if name == "exp" and not args:
        return T.exp(receiver)
    if name == "log" and not args:
        return T.log(receiver)
    if name == "sqrt" and not args:
        return T.sqrt(receiver)
    if name == "abs" and not args:
        return absolute(receiver)
    if name == "relu" and not args:
        return T.relu(receiver)
    if name == "tanh" and not args:
        return T.tanh(receiver)
    if name == "sigmoid" and not args:
        return T.sigmoid(receiver)
    if name == "softmax" and not args:
        return T.softmax(receiver, -1)
    if name == "reshape":
        shape = _need_list(args[0], "reshape dims")
        for d in shape:
            if not is_int(d):
                _fail("पुनराकृति dims must be पूर्णाङ्क values")
        return T.reshape(receiver, shape)
    if name == "transpose" and not args:
        return T.transpose(receiver)
    if name == "matmul":
        return T.matmul(receiver, _need_tensor(args[0], "matmul argument"))
    if name == "backward" and not args:
        receiver.backward()
        return UNIT
    if name == "zero_grad" and not args:
        receiver.zero_grad()
        return UNIT
    if name == "item" and not args:
        return float(receiver.item())
    _fail(f"आयाम has no method '{surface(name)}'")
    return UNIT


# ---------------------------------------------------------------------------
# Properties and dispatch tables
# ---------------------------------------------------------------------------
def get_property(ctx: NativeContext, receiver, name: str):
    if isinstance(receiver, Tensor):
        if name == "rank":
            return receiver.rank
        if name == "shape":
            return list(receiver.shape)
        if name == "dtype":
            return receiver.dtype
        if name == "size":
            return receiver.size
        if name == "requires_grad":
            return receiver.requires_grad
        if name == "grad":
            if receiver.grad is None:
                _fail("gradient is not available; call backward() first", "PE6001")
            return receiver.grad
    if isinstance(receiver, Canvas):
        if name == "width":
            return receiver.width
        if name == "height":
            return receiver.height
    if isinstance(receiver, Model) and name == "parameter_count":
        return receiver.parameter_count
    if isinstance(receiver, Dataset):
        if name == "size":
            return len(receiver)
        if name == "features":
            return receiver.features
        if name == "labels":
            return receiver.labels
    _fail(f"{type_name(receiver)} has no property '{surface(name)}'")
    return UNIT


_IMPLS = {
    "print": _print,
    "str": _str,
    "len": _len,
    "range": _range,
    "tensor": _tensor,
    "int": _int,
    "float": _float,
    "abs": _abs,
    "type_name": _type_name,
    "panic": _panic,
    "colour.srgb": _colour_srgb,
    "colour.oklch": _colour_oklch,
    "colour.oklab": _colour_oklab,
    "colour.from_hex": _colour_from_hex,
    "colour.mix": _colour_mix,
    "colour.lighten": _colour_lighten,
    "colour.darken": _colour_darken,
    "colour.rotate_hue": _colour_rotate,
    "colour.complement": _colour_complement,
    "colour.to_css": _colour_css,
    "colour.luminance": _colour_luminance,
    "colour.contrast": _colour_contrast,
    "colour.palette": _colour_palette,
    "colour.mix_many": _colour_mix_many,
    "colour.delta_e": _colour_delta_e,
    "colour.gamut_map": _colour_gamut_map,
    "graphics.canvas": _graphics_canvas,
    "graphics.clear": _graphics_clear,
    "graphics.fill": _graphics_fill,
    "graphics.rect": _graphics_rect,
    "graphics.circle": _graphics_circle,
    "graphics.line": _graphics_line,
    "graphics.gradient": _graphics_gradient,
    "graphics.glow": _graphics_glow,
    "graphics.aurora": _graphics_aurora,
    "graphics.save": _graphics_save,
    "graphics.present": _graphics_present,
    "nn.xor": _nn_xor,
    "nn.spiral": _nn_spiral,
    "nn.dataset": _nn_dataset,
    "nn.train": _nn_train,
    "nn.accuracy": _nn_accuracy,
    "nn.loss": _nn_loss,
    "nn.predict": _nn_predict,
    "nn.save": _nn_save,
    "nn.load": _nn_load,
    "process.args": _process_args,
    "fs.read_text": _fs_read_text,
    "fs.write_text": _fs_write_text,
    "fs.create_dir": _fs_create_dir,
    "vyakarana.sutra": _grammar_sutra,
    "vyakarana.sutra_count": _grammar_count,
    "vyakarana.search": _grammar_search,
    "vyakarana.pratyahara": _grammar_pratyahara,
    "vyakarana.sandhi": _grammar_sandhi,
    "vyakarana.sandhi_rule": _grammar_sandhi_rule,
    "vyakarana.anuvritti": _grammar_anuvritti,
    "vyakarana.adhikara_info": _grammar_adhikara,
    "vyakarana.literature": _grammar_literature,
    "vyakarana.coverage": _grammar_coverage,
    "ui.create": _ui_create,
    "ui.panel": _ui_panel,
    "ui.text": _ui_text,
    "ui.button": _ui_button,
    "ui.link": _ui_link,
    "ui.flow": _ui_flow,
    "ui.grid": _ui_grid,
    "ui.bounds": _ui_bounds,
    "ui.hit_test": _ui_hit_test,
    "ui.audit": _ui_audit,
    "ui.to_html": _ui_html,
    "ui.save": _ui_save,
    "ui.node_count": _ui_node_count,
    "scene3d.create": _scene_create,
    "scene3d.cube": _scene_cube,
    "scene3d.sphere": _scene_sphere,
    "scene3d.light": _scene_light,
    "scene3d.rotate": _scene_rotate,
    "scene3d.render": _scene_render,
    "scene3d.triangle_count": _scene_triangle_count,
    "agent.create": _agent_create,
    "agent.fact": _agent_fact,
    "agent.rule": _agent_rule,
    "agent.plan": _agent_plan,
    "agent.run": _agent_run,
    "agent.get": _agent_get,
    "agent.status": _agent_status,
    "agent.trace": _agent_trace,
    "agent.facts": _agent_facts,
    "nn.parameter": _nn_parameter,
    "nn.max_abs_diff": _nn_max_abs_diff,
    "nn.mse": _nn_mse,
    "nn.cross_entropy": _nn_cross_entropy,
    "text.char_at": _text_char_at,
    "text.is_alpha": _text_is_alpha,
    "text.is_digit": _text_is_digit,
    "text.is_alnum": _text_is_alnum,
    "text.is_mark": _text_is_mark,
    "text.is_space": _text_is_space,
    "text.ord": _text_ord,
    "text.chr": _text_chr,
    "text.split_lines": _text_split_lines,
    "motion.spring_steps": _motion_spring_steps,
    "motion.ease": _motion_ease,
}
_IMPLS.update(_math_impls())


def call_native(ctx: NativeContext, name: str, args: list):
    impl = _IMPLS.get(name)
    if impl is None:
        raise VMFault(f"native function '{surface(name)}' is not implemented", "PE4999")
    result = impl(ctx, args)
    if result is None:
        raise VMFault(f"native function '{name}' returned no value", "PE4999")
    return result
