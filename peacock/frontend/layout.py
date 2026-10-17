"""A small, deterministic flex layout engine.

This is deliberately simpler than a full constraint solver (Cassowary-style
solving is planned for a later phase). It supports row/column stacks, padding,
gaps, grow factors, min sizes and overflow reporting, which is enough to test the
layout architecture end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutChild:
    width: float
    height: float
    grow: float = 0.0
    min_width: float = 0.0
    min_height: float = 0.0

    def __post_init__(self):
        for name in ("width", "height", "grow", "min_width", "min_height"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"layout child '{name}' must be a non-negative number")


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass
class LayoutResult:
    rects: list[Rect]
    overflow: float


def _distribute(children: list[LayoutChild], available: float, direction: str) -> list[float]:
    sizes = [
        max(c.width if direction == "row" else c.height,
            c.min_width if direction == "row" else c.min_height)
        for c in children
    ]
    total = sum(sizes)
    extra = available - total
    if extra <= 0:
        return sizes
    grow = [c.grow for c in children]
    total_grow = sum(grow)
    if total_grow <= 0:
        return sizes
    return [s + extra * g / total_grow for s, g in zip(sizes, grow)]


def layout_row(
    children: list[LayoutChild],
    available_width: float,
    *,
    padding: float = 0.0,
    gap: float = 0.0,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> LayoutResult:
    if available_width < 0 or padding < 0 or gap < 0:
        raise ValueError("layout dimensions must be non-negative")
    inner = available_width - 2 * padding - gap * max(0, len(children) - 1)
    if inner < 0:
        inner = 0
    widths = _distribute(children, inner, "row")
    heights = [
        max(c.height, c.min_height) for c in children
    ]
    x = origin_x + padding
    rects = []
    for child, w, h in zip(children, widths, heights):
        rects.append(Rect(x, origin_y + padding, w, h))
        x += w + gap
    total = sum(widths) + gap * max(0, len(children) - 1) + 2 * padding
    return LayoutResult(rects, max(0.0, total - available_width))


def layout_column(
    children: list[LayoutChild],
    available_height: float,
    *,
    padding: float = 0.0,
    gap: float = 0.0,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> LayoutResult:
    if available_height < 0 or padding < 0 or gap < 0:
        raise ValueError("layout dimensions must be non-negative")
    inner = available_height - 2 * padding - gap * max(0, len(children) - 1)
    if inner < 0:
        inner = 0
    heights = _distribute(children, inner, "column")
    widths = [max(c.width, c.min_width) for c in children]
    y = origin_y + padding
    rects = []
    for child, w, h in zip(children, widths, heights):
        rects.append(Rect(origin_x + padding, y, w, h))
        y += h + gap
    total = sum(heights) + gap * max(0, len(children) - 1) + 2 * padding
    return LayoutResult(rects, max(0.0, total - available_height))
