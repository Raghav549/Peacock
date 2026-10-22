"""Runtime value helpers: the unit value, structs, ranges and display formatting."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from peacock.frontend.colour import Color
from peacock.intelligence.tensor import Tensor
from peacock.sanskrit import INTERNAL_TO_SOURCE, surface_type


class Unit:
    __slots__ = ()

    def __repr__(self) -> str:
        return "Unit()"

    def __bool__(self) -> bool:
        raise TypeError("PEACOCK Unit has no truth value")


UNIT = Unit()


@dataclass
class StructInstance:
    type_name: str
    field_order: list[str]
    fields: dict = field(default_factory=dict)

    def get(self, name: str):
        if name not in self.fields:
            raise KeyError(name)
        return self.fields[name]

    def set(self, name: str, value) -> None:
        if name not in self.fields:
            raise KeyError(name)
        self.fields[name] = value


@dataclass(frozen=True)
class RangeValue:
    start: int
    end: int

    def __len__(self) -> int:
        return max(0, self.end - self.start)


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def type_name(value) -> str:
    if value is UNIT:
        return INTERNAL_TO_SOURCE["Unit"]
    if isinstance(value, bool):
        return INTERNAL_TO_SOURCE["Bool"]
    if isinstance(value, int):
        return INTERNAL_TO_SOURCE["Int"]
    if isinstance(value, float):
        return INTERNAL_TO_SOURCE["Float"]
    if isinstance(value, str):
        return INTERNAL_TO_SOURCE["String"]
    if isinstance(value, list):
        return INTERNAL_TO_SOURCE["List"]
    if isinstance(value, Tensor):
        return surface_type(f"Tensor<{value.dtype}>")
    if isinstance(value, Color):
        return INTERNAL_TO_SOURCE["Color"]
    if isinstance(value, RangeValue):
        return INTERNAL_TO_SOURCE["Range"]
    if isinstance(value, StructInstance):
        return value.type_name
    from peacock.frontend.ui import UIBuilder

    if isinstance(value, UIBuilder):
        return INTERNAL_TO_SOURCE["UI"]
    # Opaque engine objects expose a class name; translate standard identities.
    name = type(value).__name__
    return INTERNAL_TO_SOURCE.get(name, name)


def format_float(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return repr(value)


def format_value(value, nested: bool = False) -> str:
    from peacock.frontend.canvas import Canvas
    from peacock.intelligence.datasets import Dataset
    from peacock.intelligence.layers import Model

    if value is UNIT:
        return INTERNAL_TO_SOURCE["Unit"]
    if isinstance(value, bool):
        return "सत्य" if value else "असत्य"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format_float(value)
    if isinstance(value, str):
        if nested:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
            return f'"{escaped}"'
        return value
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v, True) for v in value) + "]"
    if isinstance(value, Tensor):
        if value.size <= 24:
            body = format_value(value.tolist(), True)
        else:
            body = f"<{value.size} values>"
        return f"{INTERNAL_TO_SOURCE['Tensor']}({surface_type(value.dtype)}{list(value.shape)}, {body})"
    if isinstance(value, Color):
        return value.to_css()
    if isinstance(value, RangeValue):
        return f"{INTERNAL_TO_SOURCE['Range']}({value.start}..{value.end})"
    if isinstance(value, StructInstance):
        body = ", ".join(f"{name}={format_value(value.fields[name], True)}" for name in value.field_order)
        return f"{value.type_name}({body})"
    if isinstance(value, Canvas):
        return f"{INTERNAL_TO_SOURCE['Canvas']}({value.width}x{value.height})"
    if isinstance(value, Dataset):
        return f"{INTERNAL_TO_SOURCE['Dataset']}({value.name}, samples={len(value)}, features={value.feature_dim})"
    if isinstance(value, Model):
        return f"{INTERNAL_TO_SOURCE['Model']}({value.summary()})"
    return f"<{type_name(value)}>"
