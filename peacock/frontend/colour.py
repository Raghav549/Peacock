"""Colour science for PEACOCK.

Canonical representation: **linear-light sRGB** (unbounded) plus straight alpha.
Conversions implemented from published formulae:

* sRGB transfer function and D65 XYZ matrices — IEC 61966-2-1 / W3C CSS Color 4;
* Oklab / Oklch — Björn Ottosson's published formulae (2020), implemented
  independently;
* CIELAB with a D65 white point — CIE 015:2018.

No third-party colour library is used. Out-of-gamut colours are preserved in the
linear representation; conversion to 8-bit display clips unless a tone mapper is
requested (see png.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# D65 white point (CIE 15:2018 / sRGB).
WHITE_X = 0.95047
WHITE_Y = 1.0
WHITE_Z = 1.08883


class ColorError(ValueError):
    pass


def srgb_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _linear_rgb_to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    return x, y, z


def _xyz_to_linear_rgb(x: float, y: float, z: float) -> tuple[float, float, float]:
    r = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return r, g, b


def _linear_rgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_ = math.cbrt(l)
    m_ = math.cbrt(m)
    s_ = math.cbrt(s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, a, bb


def _oklab_to_linear_rgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, bb


def _xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    eps = 216.0 / 24389.0
    kappa = 24389.0 / 27.0

    def f(t: float) -> float:
        return math.cbrt(t) if t > eps else (kappa * t + 16.0) / 116.0

    fx = f(x / WHITE_X)
    fy = f(y / WHITE_Y)
    fz = f(z / WHITE_Z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def _lab_to_xyz(L: float, a: float, b: float) -> tuple[float, float, float]:
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    eps = 216.0 / 24389.0
    kappa = 24389.0 / 27.0

    def inv(f: float) -> float:
        cube = f * f * f
        return cube if cube > eps else (116.0 * f - 16.0) / kappa

    return inv(fx) * WHITE_X, inv(fy) * WHITE_Y, inv(fz) * WHITE_Z


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


@dataclass(frozen=True)
class Color:
    #: Linear-light sRGB components (may exceed [0, 1] for HDR / wide gamut).
    r: float
    g: float
    b: float
    alpha: float = 1.0

    def __post_init__(self):
        for name, value in (("r", self.r), ("g", self.g), ("b", self.b), ("alpha", self.alpha)):
            if not math.isfinite(value):
                raise ColorError(f"colour component '{name}' must be finite")
        if not (0.0 <= self.alpha <= 1.0):
            raise ColorError("alpha must be in [0, 1]")

    # -- constructors ------------------------------------------------------
    @classmethod
    def from_srgb(cls, r: float, g: float, b: float, alpha: float = 1.0) -> "Color":
        return cls(srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), alpha)

    @classmethod
    def from_oklab(cls, L: float, a: float, b: float, alpha: float = 1.0) -> "Color":
        r, g, bb = _oklab_to_linear_rgb(L, a, b)
        return cls(r, g, bb, alpha)

    @classmethod
    def from_oklch(cls, L: float, C: float, h_deg: float, alpha: float = 1.0) -> "Color":
        if C < 0:
            raise ColorError("Oklch chroma must be non-negative")
        h = math.radians(h_deg)
        return cls.from_oklab(L, C * math.cos(h), C * math.sin(h), alpha)

    @classmethod
    def from_lab(cls, L: float, a: float, b: float, alpha: float = 1.0) -> "Color":
        x, y, z = _lab_to_xyz(L, a, b)
        r, g, bb = _xyz_to_linear_rgb(x, y, z)
        return cls(r, g, bb, alpha)

    @classmethod
    def from_linear(cls, r: float, g: float, b: float, alpha: float = 1.0) -> "Color":
        return cls(r, g, b, alpha)

    @classmethod
    def from_hex(cls, text: str) -> "Color":
        if not isinstance(text, str) or not text.startswith("#"):
            raise ColorError("hex colours must look like #RRGGBB or #RRGGBBAA")
        body = text[1:]
        if len(body) == 3:
            body = "".join(ch * 2 for ch in body)
        elif len(body) == 4:
            body = "".join(ch * 2 for ch in body)
        if len(body) not in (6, 8):
            raise ColorError("hex colours must have 6 or 8 hexadecimal digits")
        try:
            values = [int(body[i : i + 2], 16) for i in range(0, len(body), 2)]
        except ValueError as exc:
            raise ColorError(f"invalid hex colour '{text}'") from exc
        alpha = values[3] / 255.0 if len(values) == 4 else 1.0
        return cls.from_srgb(values[0] / 255.0, values[1] / 255.0, values[2] / 255.0, alpha)

    # -- conversions -------------------------------------------------------
    def srgb(self) -> tuple[float, float, float]:
        return linear_to_srgb(self.r), linear_to_srgb(self.g), linear_to_srgb(self.b)

    def xyz(self) -> tuple[float, float, float]:
        return _linear_rgb_to_xyz(self.r, self.g, self.b)

    def oklab(self) -> tuple[float, float, float]:
        return _linear_rgb_to_oklab(self.r, self.g, self.b)

    def oklch(self) -> tuple[float, float, float]:
        L, a, b = self.oklab()
        C = math.hypot(a, b)
        h = math.degrees(math.atan2(b, a)) % 360.0
        return L, C, h

    def lab(self) -> tuple[float, float, float]:
        x, y, z = self.xyz()
        return _xyz_to_lab(x, y, z)

    # -- perceptual operations --------------------------------------------
    def with_alpha(self, alpha: float) -> "Color":
        return Color(self.r, self.g, self.b, alpha)

    def mix(self, other: "Color", t: float, space: str = "oklab") -> "Color":
        if not math.isfinite(t):
            raise ColorError("mix parameter t must be finite")
        if t < 0.0 or t > 1.0:
            raise ColorError("mix parameter t must be in [0, 1]")
        alpha = self.alpha + (other.alpha - self.alpha) * t
        if space == "oklab":
            l1, a1, b1 = self.oklab()
            l2, a2, b2 = other.oklab()
            return Color.from_oklab(
                l1 + (l2 - l1) * t,
                a1 + (a2 - a1) * t,
                b1 + (b2 - b1) * t,
                alpha,
            )
        if space == "oklch":
            l1, c1, h1 = self.oklch()
            l2, c2, h2 = other.oklch()
            dh = ((h2 - h1 + 180.0) % 360.0) - 180.0
            return Color.from_oklch(
                l1 + (l2 - l1) * t, c1 + (c2 - c1) * t, h1 + dh * t, alpha
            )
        if space == "linear":
            return Color(
                self.r + (other.r - self.r) * t,
                self.g + (other.g - self.g) * t,
                self.b + (other.b - self.b) * t,
                alpha,
            )
        if space == "srgb":
            a = self.srgb()
            b = other.srgb()
            return Color.from_srgb(
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                a[2] + (b[2] - a[2]) * t,
                alpha,
            )
        raise ColorError(f"unknown colour space '{space}'")

    def lighten(self, amount: float) -> "Color":
        L, C, h = self.oklch()
        return Color.from_oklch(_clamp01(L + amount), C, h, self.alpha)

    def darken(self, amount: float) -> "Color":
        L, C, h = self.oklch()
        return Color.from_oklch(_clamp01(L - amount), C, h, self.alpha)

    def rotate_hue(self, degrees: float) -> "Color":
        L, C, h = self.oklch()
        return Color.from_oklch(L, C, (h + degrees) % 360.0, self.alpha)

    def complement(self) -> "Color":
        return self.rotate_hue(180.0)

    # -- accessibility -----------------------------------------------------
    def luminance(self) -> float:
        r = _clamp01(self.r)
        g = _clamp01(self.g)
        b = _clamp01(self.b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast_ratio(self, other: "Color") -> float:
        l1 = self.luminance()
        l2 = other.luminance()
        hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
        return (hi + 0.05) / (lo + 0.05)

    # -- serialisation -----------------------------------------------------
    def in_gamut(self, tolerance: float = 1e-4) -> bool:
        return all(-tolerance <= c <= 1.0 + tolerance for c in (self.r, self.g, self.b))

    def clipped(self) -> "Color":
        return Color(_clamp01(self.r), _clamp01(self.g), _clamp01(self.b), self.alpha)

    def to_hex(self, alpha: bool = False) -> str:
        clipped = self.clipped()
        values = [round(c * 255.0) for c in clipped.srgb()]
        text = "#" + "".join(f"{v:02x}" for v in values)
        if alpha or self.alpha < 1.0:
            text += f"{round(clipped.alpha * 255.0):02x}"
        return text

    def to_css(self) -> str:
        clipped = self.clipped()
        r, g, b = [round(c * 255.0) for c in clipped.srgb()]
        if self.alpha >= 1.0:
            return f"rgb({r} {g} {b})"
        return f"rgb({r} {g} {b} / {self.alpha:.3f})"

    def __repr__(self) -> str:  # pragma: no cover
        return f"Color(linear=({self.r:.4f}, {self.g:.4f}, {self.b:.4f}), alpha={self.alpha:.3f})"


def mix(a: Color, b: Color, t: float, space: str = "oklab") -> Color:
    return a.mix(b, t, space)


def contrast_ratio(a: Color, b: Color) -> float:
    return a.contrast_ratio(b)


def palette(count: int, seed: int = 0) -> list[Color]:
    """Deterministic perceptually spaced palette using the golden angle."""
    if not isinstance(count, int) or count < 1:
        raise ColorError("palette count must be a positive integer")
    if count > 1024:
        raise ColorError("palette count is limited to 1024")
    out: list[Color] = []
    base = (seed * 47.13) % 360.0
    for i in range(count):
        h = (base + i * 137.50776405) % 360.0
        L = 0.58 + 0.14 * math.sin(i * 1.7 + seed * 0.31)
        C = 0.12 + 0.05 * (0.5 + 0.5 * math.cos(i * 0.9 + seed))
        out.append(Color.from_oklch(L, C, h))
    return out


def sample_gradient(colors: list[Color], t: float, space: str = "oklab") -> Color:
    if not colors:
        raise ColorError("gradient requires at least one colour")
    if len(colors) == 1:
        return colors[0]
    t = _clamp01(t)
    pos = t * (len(colors) - 1)
    i = min(int(pos), len(colors) - 2)
    local = pos - i
    return colors[i].mix(colors[i + 1], local, space)


# -- advanced mixing, difference and gamut mapping --------------------------
def _weights(colors: list[Color], weights: list[float]) -> tuple[list[Color], list[float]]:
    if not colors or len(colors) != len(weights):
        raise ColorError("colour mixing needs equally sized, non-empty colour and weight lists")
    if len(colors) > 256:
        raise ColorError("a mixture is limited to 256 colours")
    if any(not isinstance(color, Color) for color in colors):
        raise ColorError("every mixture input must be a colour")
    if any(not math.isfinite(weight) or weight < 0.0 for weight in weights):
        raise ColorError("mixture weights must be finite and non-negative")
    total = sum(weights)
    if total <= 0.0:
        raise ColorError("at least one mixture weight must be positive")
    return colors, [weight / total for weight in weights]


def mix_weighted(colors: list[Color], weights: list[float], space: str = "oklab") -> Color:
    """Mix any number of colours with normalized non-negative weights.

    ``subtractive`` selects the documented three-channel Kubelka–Munk
    approximation in :func:`mix_subtractive`; other spaces are direct component
    mixtures.  Oklch hue uses a weighted circular mean, avoiding a 0°/360° seam.
    """

    colors, weights = _weights(colors, weights)
    if space == "subtractive":
        return mix_subtractive(colors, weights)
    alpha = sum(color.alpha * weight for color, weight in zip(colors, weights))
    if space == "oklab":
        components = [color.oklab() for color in colors]
        values = [sum(component[i] * weight for component, weight in zip(components, weights)) for i in range(3)]
        return Color.from_oklab(*values, alpha)
    if space == "oklch":
        components = [color.oklch() for color in colors]
        lightness = sum(component[0] * weight for component, weight in zip(components, weights))
        chroma = sum(component[1] * weight for component, weight in zip(components, weights))
        x = sum(math.cos(math.radians(component[2])) * weight for component, weight in zip(components, weights))
        y = sum(math.sin(math.radians(component[2])) * weight for component, weight in zip(components, weights))
        hue = math.degrees(math.atan2(y, x)) % 360.0 if math.hypot(x, y) > 1e-12 else 0.0
        return Color.from_oklch(lightness, chroma, hue, alpha)
    if space == "linear":
        return Color(
            sum(color.r * weight for color, weight in zip(colors, weights)),
            sum(color.g * weight for color, weight in zip(colors, weights)),
            sum(color.b * weight for color, weight in zip(colors, weights)),
            alpha,
        )
    if space == "srgb":
        components = [color.srgb() for color in colors]
        values = [sum(component[i] * weight for component, weight in zip(components, weights)) for i in range(3)]
        return Color.from_srgb(*values, alpha)
    raise ColorError(f"unknown colour mixing space '{space}'")


def mix_subtractive(colors: list[Color], weights: list[float]) -> Color:
    """Approximate pigment mixing with single-constant Kubelka–Munk curves.

    Linear sRGB channels are treated as three broad reflectance bands.  This is
    useful for art tools but is **not** a spectral or measured-paint simulation.
    Weights are normalized here as well as by :func:`mix_weighted`, so direct
    Python callers receive the same result as native callers.
    """

    colors, weights = _weights(colors, weights)
    reflectances = []
    for channel in ("r", "g", "b"):
        ks = 0.0
        for color, weight in zip(colors, weights):
            reflectance = min(1.0 - 1e-7, max(1e-7, getattr(color, channel)))
            ks += weight * (1.0 - reflectance) ** 2 / (2.0 * reflectance)
        reflectances.append(1.0 + ks - math.sqrt(ks * ks + 2.0 * ks))
    alpha = sum(color.alpha * weight for color, weight in zip(colors, weights))
    return Color(*reflectances, alpha)


def map_gamut(color: Color) -> Color:
    """Map to sRGB by reducing Oklch chroma at nearly constant L and hue."""

    if color.in_gamut():
        return color
    lightness, chroma, hue = color.oklch()
    lightness = _clamp01(lightness)
    low, high = 0.0, max(0.0, chroma)
    best = Color.from_oklch(lightness, 0.0, hue, color.alpha)
    for _ in range(28):
        middle = (low + high) / 2.0
        candidate = Color.from_oklch(lightness, middle, hue, color.alpha)
        if candidate.in_gamut(tolerance=1e-6):
            best = candidate
            low = middle
        else:
            high = middle
    return best if best.in_gamut(tolerance=1e-5) else best.clipped()


def delta_e_2000(a: Color, b: Color) -> float:
    """CIEDE2000 colour difference between two CIELAB/D65 representations."""

    L1, a1, b1 = a.lab()
    L2, a2, b2 = b.lab()
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0
    cbar7 = Cbar ** 7
    G = 0.5 * (1.0 - math.sqrt(cbar7 / (cbar7 + 25.0 ** 7)))
    a1p, a2p = (1.0 + G) * a1, (1.0 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0
    dLp, dCp = L2 - L1, C2p - C1p
    difference = h2p - h1p
    if C1p * C2p == 0.0:
        dhp = 0.0
    elif abs(difference) <= 180.0:
        dhp = difference
    elif difference > 180.0:
        dhp = difference - 360.0
    else:
        dhp = difference + 360.0
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)
    Lbarp, Cbarp = (L1 + L2) / 2.0, (C1p + C2p) / 2.0
    if C1p * C2p == 0.0:
        hbarp = h1p + h2p
    elif abs(difference) <= 180.0:
        hbarp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hbarp = (h1p + h2p + 360.0) / 2.0
    else:
        hbarp = (h1p + h2p - 360.0) / 2.0
    T = (
        1.0
        - 0.17 * math.cos(math.radians(hbarp - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * hbarp))
        + 0.32 * math.cos(math.radians(3.0 * hbarp + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * hbarp - 63.0))
    )
    dtheta = 30.0 * math.exp(-((hbarp - 275.0) / 25.0) ** 2)
    cbarp7 = Cbarp ** 7
    Rc = 2.0 * math.sqrt(cbarp7 / (cbarp7 + 25.0 ** 7))
    Sl = 1.0 + 0.015 * (Lbarp - 50.0) ** 2 / math.sqrt(20.0 + (Lbarp - 50.0) ** 2)
    Sc, Sh = 1.0 + 0.045 * Cbarp, 1.0 + 0.015 * Cbarp * T
    Rt = -math.sin(math.radians(2.0 * dtheta)) * Rc
    l_term, c_term, h_term = dLp / Sl, dCp / Sc, dHp / Sh
    return math.sqrt(max(0.0, l_term * l_term + c_term * c_term + h_term * h_term + Rt * c_term * h_term))
