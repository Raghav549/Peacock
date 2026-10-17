"""Easing functions and a cubic Bézier solver.

All functions map [0, 1] to [0, 1] (some overshoot, by design) and are
deterministic. The Bézier solver is a Newton iteration with a bisection
fallback, implemented from the published definition of CSS cubic-bezier easing.
"""

from __future__ import annotations

import math

EASINGS = {
    "linear": lambda t: t,
    "ease_in_quad": lambda t: t * t,
    "ease_out_quad": lambda t: 1.0 - (1.0 - t) * (1.0 - t),
    "ease_in_out_quad": lambda t: 2 * t * t if t < 0.5 else 1.0 - ((-2 * t + 2) ** 2) / 2,
    "ease_in_cubic": lambda t: t**3,
    "ease_out_cubic": lambda t: 1.0 - (1.0 - t) ** 3,
    "ease_in_out_cubic": lambda t: 4 * t**3 if t < 0.5 else 1.0 - ((-2 * t + 2) ** 3) / 2,
    "ease_in_quart": lambda t: t**4,
    "ease_out_quart": lambda t: 1.0 - (1.0 - t) ** 4,
    "ease_in_sine": lambda t: 1.0 - math.cos((t * math.pi) / 2),
    "ease_out_sine": lambda t: math.sin((t * math.pi) / 2),
    "ease_in_out_sine": lambda t: -(math.cos(math.pi * t) - 1.0) / 2,
    "ease_in_expo": lambda t: 0.0 if t == 0 else 2 ** (10 * t - 10),
    "ease_out_expo": lambda t: 1.0 if t == 1 else 1.0 - 2 ** (-10 * t),
    "smoothstep": lambda t: t * t * (3.0 - 2.0 * t),
    "ease_in_back": lambda t: 2.70158 * t**3 - 1.70158 * t**2,
    "ease_out_back": lambda t: 1.0 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
}


def clamp_unit(t: float) -> float:
    if not math.isfinite(t):
        raise ValueError("easing input must be finite")
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def ease(name: str, t: float) -> float:
    if name not in EASINGS:
        raise ValueError(f"unknown easing '{name}'; known: {', '.join(sorted(EASINGS))}")
    return EASINGS[name](clamp_unit(t))


def cubic_bezier(x1: float, y1: float, x2: float, y2: float, t: float) -> float:
    """Evaluate a CSS-style cubic Bézier timing function at x = t."""
    t = clamp_unit(t)
    # x(s) = 3(1-s)^2 s x1 + 3(1-s)s^2 x2 + s^3
    def curve(s: float, p1: float, p2: float) -> float:
        return 3.0 * (1 - s) ** 2 * s * p1 + 3.0 * (1 - s) * s * s * p2 + s**3

    def curve_derivative(s: float, p1: float, p2: float) -> float:
        return (
            3.0 * (1 - s) ** 2 * p1
            + 6.0 * (1 - s) * s * (p2 - p1)
            + 3.0 * s * s * (1 - p2)
        )

    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    s = t
    for _ in range(8):
        x = curve(s, x1, x2) - t
        if abs(x) < 1e-7:
            break
        d = curve_derivative(s, x1, x2)
        if abs(d) < 1e-7:
            break
        s -= x / d
        s = 0.0 if s < 0.0 else (1.0 if s > 1.0 else s)
    lo, hi = 0.0, 1.0
    for _ in range(40):
        x = curve(s, x1, x2)
        if abs(x - t) < 1e-7:
            break
        if x < t:
            lo = s
        else:
            hi = s
        s = (lo + hi) / 2.0
    return curve(s, y1, y2)
