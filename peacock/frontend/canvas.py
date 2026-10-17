"""An original software 2-D rasteriser.

Pixel model: premultiplied, **linear-light** RGBA floats. The framebuffer is
row-major, origin top-left, y down; pixel centres are at (x + 0.5, y + 0.5).
Shape edges are anti-aliased with 4×4 coverage sampling (a documented
approximation, not an analytic area integral).

Compositing implements the source-over operator from Porter & Duff (1984).
Additive blending is an artistic approximation for luminous effects and is
labelled as such; it is not a physically based bloom simulation.
"""

from __future__ import annotations

import math

from .colour import Color, ColorError, palette, sample_gradient

MAX_DIMENSION = 4096
MAX_PIXELS = 1_048_576


class CanvasError(ValueError):
    pass


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = (x - edge0) / (edge1 - edge0)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _hash2(x: int, y: int, seed: int) -> float:
    n = (x * 374761393 + y * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFFFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFFFF) / 0xFFFFFFFF


def _value_noise(x: float, y: float, seed: int) -> float:
    xi = math.floor(x)
    yi = math.floor(y)
    fx = x - xi
    fy = y - yi
    u = fx * fx * (3.0 - 2.0 * fx)
    v = fy * fy * (3.0 - 2.0 * fy)
    a = _hash2(xi, yi, seed)
    b = _hash2(xi + 1, yi, seed)
    c = _hash2(xi, yi + 1, seed)
    d = _hash2(xi + 1, yi + 1, seed)
    ab = a + (b - a) * u
    cd = c + (d - c) * u
    return ab + (cd - ab) * v


def _fbm(x: float, y: float, seed: int, octaves: int = 3) -> float:
    total = 0.0
    amplitude = 0.5
    frequency = 1.0
    norm = 0.0
    for i in range(octaves):
        total += amplitude * _value_noise(x * frequency, y * frequency, seed + i * 101)
        norm += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return total / norm


class Canvas:
    def __init__(self, width: int, height: int):
        if not isinstance(width, int) or not isinstance(height, int):
            raise CanvasError("canvas dimensions must be integers")
        if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION):
            raise CanvasError(f"canvas dimensions must be between 1 and {MAX_DIMENSION}")
        if width * height > MAX_PIXELS:
            raise CanvasError(
                f"canvas has {width * height} pixels, exceeding the {MAX_PIXELS}-pixel safety limit"
            )
        self.width = width
        self.height = height
        self.data = [0.0] * (width * height * 4)
        self.draw_calls = 0

    # -- pixels ------------------------------------------------------------
    def _store(self, index: int, color: Color, coverage: float = 1.0, additive: bool = False) -> None:
        if coverage <= 0.0:
            return
        if color.alpha <= 0.0:
            return
        sa = color.alpha * coverage
        if sa <= 0.0:
            return
        if sa > 1.0:
            sa = 1.0
        sr = color.r * sa
        sg = color.g * sa
        sb = color.b * sa
        d = self.data
        if additive:
            d[index] += sr
            d[index + 1] += sg
            d[index + 2] += sb
            da = d[index + 3]
            d[index + 3] = da + sa * (1.0 - da)
        else:
            inv = 1.0 - sa
            d[index] = sr + d[index] * inv
            d[index + 1] = sg + d[index + 1] * inv
            d[index + 2] = sb + d[index + 2] * inv
            d[index + 3] = sa + d[index + 3] * inv

    def clear(self, color: Color | None = None) -> None:
        if color is None:
            self.data = [0.0] * (self.width * self.height * 4)
        else:
            sa = color.alpha
            values = [color.r * sa, color.g * sa, color.b * sa, sa]
            self.data = values * (self.width * self.height)
        self.draw_calls += 1

    def fill(self, color: Color) -> None:
        self.clear(color)

    def pixel(self, x: int, y: int) -> tuple[float, float, float, float]:
        """Premultiplied linear RGBA at integer coordinates."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise CanvasError("pixel coordinates out of bounds")
        i = (y * self.width + x) * 4
        return tuple(self.data[i : i + 4])  # type: ignore[return-value]

    def pixel_straight(self, x: int, y: int) -> tuple[float, float, float, float]:
        r, g, b, a = self.pixel(x, y)
        if a <= 0.0:
            return 0.0, 0.0, 0.0, 0.0
        return r / a, g / a, b / a, a

    # -- shapes ------------------------------------------------------------
    def rect(self, x: float, y: float, width: float, height: float, color: Color) -> None:
        if width < 0:
            x += width
            width = -width
        if height < 0:
            y += height
            height = -height
        if width == 0 or height == 0 or color.alpha == 0:
            return
        x0, x1 = x, x + width
        y0, y1 = y, y + height
        start_x = max(0, math.floor(x0))
        end_x = min(self.width, math.ceil(x1))
        start_y = max(0, math.floor(y0))
        end_y = min(self.height, math.ceil(y1))
        samples = 4
        offsets = [(s + 0.5) / samples for s in range(samples)]
        for py in range(start_y, end_y):
            for px in range(start_x, end_x):
                inside = 0
                for oy in offsets:
                    sy = py + oy
                    if sy < y0 or sy > y1:
                        continue
                    for ox in offsets:
                        sx = px + ox
                        if x0 <= sx <= x1:
                            inside += 1
                if inside:
                    self._store((py * self.width + px) * 4, color, inside / (samples * samples))
        self.draw_calls += 1

    def circle(self, cx: float, cy: float, radius: float, color: Color) -> None:
        if radius <= 0 or color.alpha == 0:
            return
        start_x = max(0, math.floor(cx - radius))
        end_x = min(self.width, math.ceil(cx + radius))
        start_y = max(0, math.floor(cy - radius))
        end_y = min(self.height, math.ceil(cy + radius))
        samples = 4
        offsets = [(s + 0.5) / samples for s in range(samples)]
        r2 = radius * radius
        for py in range(start_y, end_y):
            for px in range(start_x, end_x):
                inside = 0
                for oy in offsets:
                    sy = py + oy - cy
                    for ox in offsets:
                        sx = px + ox - cx
                        if sx * sx + sy * sy <= r2:
                            inside += 1
                if inside:
                    self._store((py * self.width + px) * 4, color, inside / (samples * samples))
        self.draw_calls += 1

    def line(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        width: float,
        color: Color,
    ) -> None:
        if width <= 0 or color.alpha == 0:
            return
        half = width / 2.0
        pad = half + 1.0
        start_x = max(0, math.floor(min(x0, x1) - pad))
        end_x = min(self.width, math.ceil(max(x0, x1) + pad))
        start_y = max(0, math.floor(min(y0, y1) - pad))
        end_y = min(self.height, math.ceil(max(y0, y1) + pad))
        dx = x1 - x0
        dy = y1 - y0
        length2 = dx * dx + dy * dy
        samples = 4
        offsets = [(s + 0.5) / samples for s in range(samples)]
        for py in range(start_y, end_y):
            for px in range(start_x, end_x):
                inside = 0
                for oy in offsets:
                    sy = py + oy
                    for ox in offsets:
                        sx = px + ox
                        if length2 == 0:
                            dist2 = (sx - x0) ** 2 + (sy - y0) ** 2
                        else:
                            t = ((sx - x0) * dx + (sy - y0) * dy) / length2
                            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                            qx = x0 + t * dx
                            qy = y0 + t * dy
                            dist2 = (sx - qx) ** 2 + (sy - qy) ** 2
                        if dist2 <= half * half:
                            inside += 1
                if inside:
                    self._store((py * self.width + px) * 4, color, inside / (samples * samples))
        self.draw_calls += 1

    # -- procedural fills --------------------------------------------------
    def gradient(self, colors: list[Color], angle_degrees: float = 0.0) -> None:
        if not colors:
            raise CanvasError("gradient requires at least one colour")
        angle = math.radians(angle_degrees)
        dx = math.cos(angle)
        dy = math.sin(angle)
        corners = [
            (0.0, 0.0),
            (float(self.width), 0.0),
            (0.0, float(self.height)),
            (float(self.width), float(self.height)),
        ]
        projections = [cx * dx + cy * dy for cx, cy in corners]
        lo, hi = min(projections), max(projections)
        span = hi - lo
        if span <= 0:
            self.fill(colors[0])
            return
        lut_size = 512
        lut = [sample_gradient(colors, i / (lut_size - 1)) for i in range(lut_size)]
        lut_data = [(c.r, c.g, c.b, c.alpha) for c in lut]
        for py in range(self.height):
            for px in range(self.width):
                projection = (px + 0.5) * dx + (py + 0.5) * dy
                t = (projection - lo) / span
                pos = t * (lut_size - 1)
                i0 = int(pos)
                if i0 >= lut_size - 1:
                    i0 = lut_size - 2
                    frac = 1.0
                else:
                    frac = pos - i0
                c0 = lut_data[i0]
                c1 = lut_data[i0 + 1]
                color = Color(
                    c0[0] + (c1[0] - c0[0]) * frac,
                    c0[1] + (c1[1] - c0[1]) * frac,
                    c0[2] + (c1[2] - c0[2]) * frac,
                    c0[3] + (c1[3] - c0[3]) * frac,
                )
                self._store((py * self.width + px) * 4, color)
        self.draw_calls += 1

    def glow(
        self,
        cx: float,
        cy: float,
        radius: float,
        color: Color,
        intensity: float = 1.0,
    ) -> None:
        if radius <= 0 or color.alpha == 0 or intensity <= 0:
            return
        start_x = max(0, math.floor(cx - radius))
        end_x = min(self.width, math.ceil(cx + radius))
        start_y = max(0, math.floor(cy - radius))
        end_y = min(self.height, math.ceil(cy + radius))
        for py in range(start_y, end_y):
            for px in range(start_x, end_x):
                d = math.hypot(px + 0.5 - cx, py + 0.5 - cy)
                if d >= radius:
                    continue
                falloff = (1.0 - d / radius) ** 2
                self._store(
                    (py * self.width + px) * 4,
                    color,
                    coverage=min(1.0, falloff * intensity),
                    additive=True,
                )
        self.draw_calls += 1

    def aurora(self, time: float = 0.0, seed: int = 0) -> None:
        """A deterministic painterly aurora field (artistic, not volumetric)."""
        if not math.isfinite(time):
            raise CanvasError("aurora time must be finite")
        colors = palette(4, seed)
        lut = [sample_gradient(colors, i / 255.0) for i in range(256)]
        lut_data = [(c.r, c.g, c.b) for c in lut]
        width, height = self.width, self.height
        for py in range(height):
            v = (py + 0.5) / height
            if v > 0.85:
                continue
            for px in range(width):
                u = (px + 0.5) / width
                n = _fbm(u * 2.4 + time * 0.03, v * 2.0 - time * 0.01, seed, 3)
                curtain = 0.5 + 0.5 * math.sin(
                    (u * 7.0 + n * 3.2 + time * 0.25) * math.pi
                )
                curtain = curtain**4
                center = 0.30 + 0.10 * math.sin(u * 5.0 + time * 0.2)
                band = math.exp(-((v - center) ** 2) / (2.0 * 0.16 * 0.16))
                horizontal = 0.45 + 0.55 * math.sin((u + time * 0.05) * math.pi) ** 2
                strength = curtain * band * horizontal * 0.55
                if strength <= 0.001:
                    continue
                idx = int((n * 0.65 + u * 0.25 + time * 0.02) * 255.0) % 256
                r, g, b = lut_data[idx]
                self._store(
                    (py * width + px) * 4,
                    Color(r, g, b, 1.0),
                    coverage=min(1.0, strength),
                    additive=True,
                )
        self.draw_calls += 1

    # -- diagnostics -------------------------------------------------------
    def stats(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "pixels": self.width * self.height,
            "draw_calls": self.draw_calls,
            "framebuffer_bytes_estimate": self.width * self.height * 4 * 4,
        }
