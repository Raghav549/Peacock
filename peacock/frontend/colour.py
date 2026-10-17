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
