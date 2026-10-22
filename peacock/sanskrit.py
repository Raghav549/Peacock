"""Canonical Sanskrit vocabulary for the PEACOCK / मयूर source language.

The compiler's IR deliberately uses stable, language-independent internal names.
This module is the *only* translation boundary between those names and the native
Sanskrit source notation.  Keeping the mapping here prevents the lexer, runtime,
editor grammar and documentation generator from drifting apart.

No Sanskrit word is translated by a machine-learning model or by a third-party
Sanskrit package.  The vocabulary is an explicit, auditable part of the language
specification.  User identifiers outside this reserved vocabulary are preserved
(after Unicode NFC normalisation).
"""

from __future__ import annotations

import unicodedata

SOURCE_EXTENSION = ".सूत्र"
ARTIFACT_EXTENSION = ".बीज"
MODEL_EXTENSION = ".ज्ञान"
LANGUAGE_NAME = "मयूर"
ENTRY_POINT = "मुख्य"

# Internal name -> native source name.  These are reserved standard vocabulary,
# not translations performed on arbitrary user identifiers.
_LEXICON: dict[str, str] = {
    # Entry point and contextual declaration vocabulary.
    "main": "मुख्य",
    "input": "निवेश",
    "output": "निर्गम",
    "stack": "क्रम",
    "Dense": "सघन",
    "units": "एककानि",
    "activation": "सक्रियण",
    "init": "प्रारम्भ",
    "run": "चलाय",
    "evaluate": "मूल्याङ्कय",
    # Scalar, compound and opaque types.
    "Int": "पूर्णाङ्क",
    "Float": "दशमलव",
    "Bool": "सत्यता",
    "String": "अक्षरमाला",
    "Unit": "एकक",
    "Never": "अभाव",
    "Any": "सर्व",
    "List": "सूची",
    "Tensor": "आयाम",
    "Color": "वर्ण",
    "Canvas": "चित्रपट",
    "Model": "प्रतिमानप्रकार",
    "Dataset": "दत्तसमूह",
    "Range": "सीमा",
    "Float32": "दशमलव३२",
    "Float64": "दशमलव६४",
    "Int32": "पूर्णाङ्क३२",
    # Capabilities and standard-library namespaces.
    "compute": "गणना",
    "fs": "सञ्चय",
    "ui": "दृश्य",
    "math": "गणित",
    "nn": "तन्त्रजाल",
    "colour": "रङ्ग",
    "graphics": "चित्र",
    "motion": "गति",
    "text": "पाठ्य",
    "process": "प्रक्रिया",
    # Global functions.
    "print": "मुद्रय",
    "str": "पाठ्यीकरण",
    "len": "दैर्घ्य",
    "range": "परिसर",
    "tensor": "आयामीकरण",
    "int": "पूर्णीकरण",
    "float": "दशमलवीकरण",
    "abs": "निरपेक्ष",
    "type_name": "प्रकारनाम",
    "panic": "विह्वल",
    # Mathematics.
    "sqrt": "वर्गमूल",
    "exp": "घाताङ्क",
    "log": "लघुगणक",
    "log2": "द्विलघुगणक",
    "sin": "ज्या",
    "cos": "कोटिज्या",
    "tan": "स्पर्शज्या",
    "atan2": "द्विस्पर्शज्या",
    "pow": "घात",
    "floor": "अधोमूल्य",
    "ceil": "ऊर्ध्वमूल्य",
    "round": "पूर्णीत",
    "min": "न्यूनतम",
    "max": "अधिकतम",
    "clamp": "सीमित",
    "pi": "वृत्तानुपात",
    "e": "घाताधार",
    # Colour and graphics.
    "srgb": "एसआरजीबी",
    "oklab": "ओकलैब",
    "oklch": "ओकएलसीएच",
    "from_hex": "षोडशात्",
    "mix": "मिश्रय",
    "lighten": "दीप्तय",
    "darken": "मन्दय",
    "rotate_hue": "वर्णभ्रमय",
    "complement": "पूरकवर्ण",
    "to_css": "शैलीपाठ्य",
    "luminance": "द्युति",
    "contrast": "विरोधद्युति",
    "palette": "वर्णावली",
    "canvas": "चित्रपट्ट",
    "clear": "शुद्धय",
    "fill": "पूरय",
    "rect": "आयत",
    "circle": "वृत्त",
    "line": "रेखा",
    "gradient": "वर्णक्रम",
    "glow": "प्रभा",
    "aurora": "उषोद्युति",
    "save": "रक्ष",
    "present": "प्रदर्शय",
    # Files, process and text.
    "args": "तर्कावली",
    "read_text": "पाठ्यपठन",
    "write_text": "पाठ्यलेखन",
    "create_dir": "निधिरचना",
    "char_at": "अक्षरम्",
    "is_alpha": "वर्णः",
    "is_digit": "अङ्कः",
    "is_alnum": "वर्णाङ्कः",
    "is_mark": "चिह्नमात्रा",
    "is_space": "रिक्तिः",
    "ord": "अक्षरसङ्ख्या",
    "chr": "सङ्ख्याक्षर",
    "split_lines": "पङ्क्तिविभाजन",
    # Neural-network construction, training and evaluation.
    "parameter": "प्राचल",
    "mse": "माध्यवर्गदोष",
    "cross_entropy": "अन्तरएन्ट्रॉपी",
    "max_abs_diff": "अधिकतमनिरपेक्षान्तर",
    "xor": "असमानयोग",
    "spiral": "सर्पिल",
    "dataset": "दत्तरचना",
    "train": "अभ्यासय",
    "accuracy": "शुद्धता",
    "loss": "दोष",
    "predict": "पूर्वानुमान",
    "load": "आहारय",
    "sgd": "यादृच्छिकअवरोह",
    "adam": "आदम",
    # Model declaration options.
    "objective": "उद्देश्य",
    "optimiser": "अनुकूलक",
    "epochs": "आवृत्ति",
    "learning_rate": "अधिगमदर",
    "batch_size": "समूहमान",
    "seed": "बीज",
    # Activations.
    "linear": "रैखिक",
    "relu": "धनाङ्क",
    "sigmoid": "वक्रसीमा",
    "tanh": "अतिस्पर्शज्या",
    "softmax": "कोमलाधिकतम",
    # Motion.
    "spring_steps": "स्पृङ्गचरण",
    "ease": "गतिशैली",
    "ease_in_quad": "आरम्भद्विघात",
    "ease_out_quad": "अन्तद्विघात",
    "ease_in_out_quad": "आरम्भान्तद्विघात",
    "ease_in_cubic": "आरम्भत्रिघात",
    "ease_out_cubic": "अन्तत्रिघात",
    "ease_in_out_cubic": "आरम्भान्तत्रिघात",
    "ease_in_quart": "आरम्भचतुर्घात",
    "ease_out_quart": "अन्तचतुर्घात",
    "ease_in_sine": "आरम्भज्या",
    "ease_out_sine": "अन्तज्या",
    "ease_in_out_sine": "आरम्भान्तज्या",
    "ease_in_expo": "आरम्भघाताङ्क",
    "ease_out_expo": "अन्तघाताङ्क",
    "smoothstep": "सुसंगतचरण",
    "ease_in_back": "आरम्भपश्चात्",
    "ease_out_back": "अन्तपश्चात्",
    # Properties and methods shared by built-in values.
    "rank": "कोटि",
    "shape": "आकृति",
    "dtype": "दत्तप्रकार",
    "size": "मान",
    "grad": "अवकल",
    "requires_grad": "अवकलआवश्यक",
    "width": "विस्तार",
    "height": "औन्नत्य",
    "parameter_count": "प्राचलसंख्या",
    "features": "विशेषक",
    "labels": "चिह्न",
    "push": "योजय",
    "pop": "निष्कासय",
    "get": "प्राप्नु",
    "contains": "अन्तर्भूत",
    "index_of": "सूचकाङ्क",
    "join": "संयोजय",
    "sort": "क्रमय",
    "reverse": "विपर्यय",
    "upper": "बृहदक्षर",
    "lower": "लघ्वक्षर",
    "trim": "शोधय",
    "starts_with": "आरम्भयुक्त",
    "ends_with": "अन्तयुक्त",
    "split": "विभाजय",
    "replace": "प्रतिस्थापय",
    "substring": "उपपाठ्य",
    "sum": "योग",
    "mean": "माध्य",
    "reshape": "पुनराकृति",
    "transpose": "परिवर्त",
    "matmul": "आव्यूहगुणन",
    "backward": "पश्चप्रसार",
    "zero_grad": "शून्यअवकल",
    "item": "अवयव",
    "summary": "सारांश",
    "css": "शैली",
    # Named native arguments.  They are standard vocabulary so positional and
    # named calls produce exactly the same internal IR.
    "value": "मूल्य",
    "start": "आरम्भ",
    "end": "अन्त",
    "data": "दत्त",
    "message": "सन्देश",
    "base": "आधार",
    "exponent": "घाताङ्कः",
    "low": "अधः",
    "high": "ऊर्ध्व",
    "hex": "षोडश",
    "amount": "परिमाण",
    "degrees": "अंश",
    "count": "संख्या",
    "path": "पथ",
    "content": "अन्तर्वस्तु",
    "predictions": "पूर्वानुमानानि",
    "targets": "लक्ष्याणि",
    "logits": "असंस्कृतमान",
    "x": "क्ष",
    "y": "य",
    "a": "अ",
    "b": "ब",
    "t": "त",
    "c": "च",
    "r": "र",
    "g": "ग",
    "alpha": "अपारदर्शिता",
    "model": "प्रतिमानमूल्य",
    "features_in": "निवेशविशेषक",
    "target": "लक्ष्य",
    "stiffness": "दृढता",
    "damping": "अवमन्दन",
    "steps": "चरणानि",
    "dt": "कालान्तर",
    "index": "सूचक",
    "code": "संकेत",
    "name": "नाम",
    "angle": "कोण",
    "time": "काल",
    "colors": "वर्णावलीः",
    "cx": "केन्द्रक्ष",
    "cy": "केन्द्रय",
    "radius": "त्रिज्या",
    "x0": "क्ष०",
    "x1": "क्ष१",
    "y0": "य०",
    "y1": "य१",
    "per_class": "प्रतिवर्ग",
    "noise": "विक्षोभ",
    "optimisation": "अनुकूलन",
}

# Additive 0.3 vocabulary. These internal names were never valid English source
# words in 0.2, so they must not join the withdrawn-0.1 rejection inventory:
# existing user identifiers such as ``left``, ``weights`` and ``node`` stay valid.
_V03_LEXICON: dict[str, str] = {
    # Sanskrit grammar, UI, 3-D and agent types/namespaces.
    "UI": "दृश्यरचना",
    "Scene3D": "त्रिअयामदृश्य",
    "Agent": "अभिकर्तृप्रकार",
    "scene3d": "त्रिअयाम",
    "vyakarana": "व्याकरण",
    "agent": "अभिकर्तृ",
    # Advanced colour operations.
    "mix_many": "बहुमिश्रय",
    "delta_e": "वर्णान्तर",
    "gamut_map": "वर्णक्षेत्रीकरण",
    "subtractive": "व्यवकलन",
    # Native UI builder.
    "create": "सृज",
    "panel": "पटल",
    "button": "नोदक",
    "link": "सम्पर्क",
    "flow": "प्रवाह",
    "grid": "जालक",
    "bounds": "परिसीमा",
    "hit_test": "स्पर्शपरीक्षा",
    "audit": "अन्वीक्षा",
    "to_html": "एचटीएमएलपाठ्य",
    "node_count": "ग्रन्थिसंख्या",
    "bind": "बन्धन",
    "post_event": "घटनाप्रेषय",
    "next_event": "अग्रघटना",
    "pending_events": "घटनासंख्या",
    "set_text": "पाठ्यस्थापय",
    "set_enabled": "सक्रियतास्थापय",
    "focus": "अवधान",
    "kind": "घटनाप्रकार",
    "enabled": "सक्रियता",
    "timeout": "विलम्ब",
    "click": "स्पर्श",
    "pointer_down": "अधःस्पर्श",
    "pointer_up": "उत्सर्ग",
    "submit": "प्रेषण",
    "node": "ग्रन्थि",
    "parent": "जनक",
    "label": "नामपट्ट",
    "href": "गन्तव्य",
    "foreground": "अग्रवर्ण",
    "background": "पृष्ठवर्ण",
    "direction": "दिशा",
    "gap": "अन्तर",
    "padding": "अन्तराल",
    "columns": "स्तम्भानि",
    "row": "पङ्क्ति",
    "column": "स्तम्भ",
    # Software 3-D renderer.
    "cube": "घन",
    "sphere": "गोलक",
    "light": "प्रकाश",
    "rotate": "भ्रमय",
    "render": "अङ्कन",
    "triangle_count": "त्रिभुजसंख्या",
    "z": "जेड",
    "segments": "खण्डानि",
    "rings": "वलयानि",
    "intensity": "तीव्रता",
    "yaw": "पार्श्वभ्रम",
    "pitch": "अनुभ्रम",
    "distance": "दूरी",
    "fov": "दृष्टिकोण",
    # Deterministic agent construction and planning.
    "network": "सञ्जाल",
    "server": "सेवक",
    "listen": "श्रृणु",
    "accept": "स्वीकुरु",
    "respond": "प्रत्युत्तरय",
    "port": "द्वार",
    "gpu": "गणनयन्त्र",
    "backends": "पश्चात्तन्त्राणि",
    "info": "विवरण",
    "auto": "स्वयम्",
    "cpu": "क्रमक",
    "opencl": "त्वरक",
    "multiply": "गुणय",
    "add": "संकलय",
    "autonomous": "स्वायत्त",
    "close": "पिदध्मि",
    "fact": "तथ्य",
    "rule": "नियम",
    "plan": "योजना",
    "status": "स्थिति",
    "trace": "अनुसरण",
    "facts": "तथ्यावली",
    "goal_key": "लक्ष्यसूची",
    "goal_value": "लक्ष्यमूल्य",
    "max_steps": "अधिकतमचरण",
    "when_key": "यदासूची",
    "when_value": "यदामूल्य",
    "action": "क्रिया",
    "set_key": "स्थापनसूची",
    "set_value": "स्थापनमूल्य",
    "priority": "प्राथमिकता",
    "cost": "व्यय",
    "key": "कुञ्जिका",
    "weights": "भारावली",
    "space": "वर्णावकाश",
    "scene": "त्रिअयाममूल्य",
    "title": "शीर्षक",
    "color": "वर्णमूल्य",
    "ready": "सज्ज",
    "succeeded": "सिद्ध",
    "stalled": "स्थगित",
    # Executable Pāṇinian tools and complete sūtra text lookup.
    "sutra": "सूत्र",
    "sutra_count": "सूत्रसंख्या",
    "search": "अन्वेषय",
    "pratyahara": "प्रत्याहार",
    "sandhi": "संधि",
    "sandhi_rule": "संधिसूत्र",
    "anuvritti": "अनुवृत्ति",
    "adhikara_info": "अधिकारविवरण",
    "literature": "साहित्य",
    "coverage": "आच्छादन",
    "left": "वाम",
    "right": "दक्षिण",
    "query": "अन्वेषण",
    "limit": "अवधि",
    "id": "परिचय",
}
_LEXICON.update(_V03_LEXICON)

# Sanskrit string values accepted where an algorithm name is a value rather than
# an identifier (training declarations, nn.train/nn.loss and motion.ease).
_ENUM_VALUES = {
    key: _LEXICON[key]
    for key in (
        "linear", "relu", "sigmoid", "tanh", "softmax",
        "cross_entropy", "mse", "sgd", "adam",
        "ease_in_quad", "ease_out_quad", "ease_in_out_quad",
        "ease_in_cubic", "ease_out_cubic", "ease_in_out_cubic",
        "ease_in_quart", "ease_out_quart", "ease_in_sine",
        "ease_out_sine", "ease_in_out_sine", "ease_in_expo",
        "ease_out_expo", "smoothstep", "ease_in_back", "ease_out_back",
        "oklab", "oklch", "srgb", "subtractive", "row", "column",
        "ready", "succeeded", "stalled",
        "click", "pointer_down", "pointer_up", "key", "text", "focus", "submit", "close",
        "auto", "cpu", "opencl",
    )
}

# English vocabulary from the withdrawn 0.1 surface is rejected with a targeted
# diagnostic rather than silently becoming a second source language.
# Mathematical single-letter names remain available as user identifiers; the
# rest of the withdrawn English standard vocabulary receives PE1007.
LEGACY_STANDARD_WORDS = frozenset(
    set(_LEXICON) - set(_V03_LEXICON)
    - {"x", "y", "a", "b", "c", "t", "r", "g", "e", "x0", "x1", "y0", "y1"}
)

LEGACY_KEYWORDS: dict[str, str] = {
    "module": "प्रकरण",
    "use": "उपयोग",
    "as": "रूपेण",
    "fn": "कार्य",
    "let": "स्थापय",
    "mut": "परिवर्तनीय",
    "if": "यदि",
    "else": "अन्यथा",
    "while": "यावत्",
    "for": "प्रति",
    "in": "मध्ये",
    "return": "प्रत्यानय",
    "break": "विच्छिन्दु",
    "continue": "अनुवर्तय",
    "struct": "संघटन",
    "model": "प्रतिमान",
    "training": "अभ्यास",
    "capability": "अधिकार",
    "try": "यत्न",
    "catch": "गृह्ण",
    "finally": "अन्ते",
    "throw": "क्षिप",
    "assert": "निश्चिनु",
    "true": "सत्य",
    "false": "असत्य",
    "and": "तथा",
    "or": "वा",
    "not": "न",
    "enum": "सूचीभेद",
    "match": "मिलान",
    "impl": "कार्यान्वयन",
    "pub": "सार्वजनिक",
    "const": "स्थिर",
    "import": "आयात",
    "async": "असामकालिक",
    "await": "प्रतीक्षा",
    "spawn": "जनय",
    "yield": "उत्पादय",
}


def _build_reverse() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for internal, source in _LEXICON.items():
        previous = reverse.setdefault(source, internal)
        if previous != internal:
            raise RuntimeError(
                f"Sanskrit vocabulary collision: {source!r} maps to both {previous!r} and {internal!r}"
            )
    return reverse


SOURCE_TO_INTERNAL = _build_reverse()
INTERNAL_TO_SOURCE = dict(_LEXICON)
SOURCE_ENUM_TO_INTERNAL = {source: internal for internal, source in _ENUM_VALUES.items()}
INTERNAL_ENUM_TO_SOURCE = dict(_ENUM_VALUES)


def normalize_identifier(text: str) -> str:
    """Return the canonical NFC spelling used for symbol identity."""

    return unicodedata.normalize("NFC", text)


def internalise(text: str) -> str:
    """Map one reserved Sanskrit identifier to its stable internal name."""

    return SOURCE_TO_INTERNAL.get(normalize_identifier(text), normalize_identifier(text))


def internalise_path(parts: list[str] | tuple[str, ...]) -> list[str]:
    return [internalise(part) for part in parts]


def surface(text: str) -> str:
    """Render an internal identifier or dotted native name in Sanskrit."""

    return ".".join(INTERNAL_TO_SOURCE.get(part, part) for part in text.split("."))


def surface_type(text: str) -> str:
    """Localise the standard type constructors inside a displayed type."""

    result = text
    # Longest first prevents Int being replaced inside Int32.
    for internal in sorted(INTERNAL_TO_SOURCE, key=len, reverse=True):
        if internal in {"Int", "Float", "Bool", "String", "Unit", "Never", "Any", "List", "Tensor", "Color", "Canvas", "Model", "Dataset", "Range", "Float32", "Float64", "Int32"}:
            result = result.replace(internal, INTERNAL_TO_SOURCE[internal])
    return result


def internalise_enum(value: str) -> str:
    """Translate a native algorithm/literal value; leave unknown values intact."""

    return SOURCE_ENUM_TO_INTERNAL.get(value, value)


def surface_enum(value: str) -> str:
    return INTERNAL_ENUM_TO_SOURCE.get(value, value)


def is_identifier_start(ch: str) -> bool:
    """Unicode identifier start, restricted to letters and underscore."""

    return bool(ch) and (ch == "_" or ch.isalpha())


def is_identifier_continue(ch: str) -> bool:
    """Unicode letters, decimal digits, combining marks and underscore.

    Devanagari vowel signs, virāma, anusvāra and visarga are marks, so ``isalnum``
    alone is insufficient for real Sanskrit words.
    """

    if not ch:
        return False
    return is_identifier_start(ch) or ch.isdecimal() or unicodedata.category(ch) in {"Mn", "Mc", "Me"}


def is_decimal_digit(ch: str) -> bool:
    return bool(ch) and ch.isdecimal()


def decimal_value(ch: str) -> int:
    """Unicode decimal digit value without accepting non-decimal numerics."""

    if not is_decimal_digit(ch):
        raise ValueError(f"not a Unicode decimal digit: {ch!r}")
    return unicodedata.decimal(ch)


def ascii_digits(text: str) -> str:
    """Normalise Unicode decimal digits for numeric conversion routines."""

    return "".join(str(decimal_value(ch)) if is_decimal_digit(ch) else ch for ch in text)


def devanagari_digits(text: str) -> str:
    """Canonical display form for numeric literals in Sanskrit documentation."""

    return str(text).translate(str.maketrans("0123456789", "०१२३४५६७८९"))
