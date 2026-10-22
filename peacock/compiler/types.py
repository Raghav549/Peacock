"""PEACOCK's static type model (v0.3).

The model is deliberately small and explicit. There is no implicit numeric
conversion between ``Int`` and ``Float``; tensor dtypes follow the promotion
table in :func:`promote_dtype` and shapes are checked statically whenever both
sides are known (see SPECIFICATION.md §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from peacock.sanskrit import surface_type


class Type:
    """Base class for all PEACOCK types."""

    def display(self) -> str:  # pragma: no cover - overridden
        return type(self).__name__


@dataclass(frozen=True, slots=True)
class PrimitiveType(Type):
    name: str

    def display(self) -> str:
        return surface_type(self.name)


IntType = PrimitiveType("Int")
FloatType = PrimitiveType("Float")
BoolType = PrimitiveType("Bool")
StringType = PrimitiveType("String")
UnitType = PrimitiveType("Unit")
NeverType = PrimitiveType("Never")
AnyType = PrimitiveType("Any")
ErrorType = PrimitiveType("<error>")


@dataclass(frozen=True, slots=True)
class TensorType(Type):
    dtype: str
    shape: tuple[int, ...] | None = None  # None means "shape known only at run time"

    def display(self) -> str:
        if self.shape is None:
            return surface_type(f"Tensor<{self.dtype}>")
        dims = ", ".join(str(d) for d in self.shape)
        return surface_type(f"Tensor<{self.dtype}, [{dims}]>")


@dataclass(frozen=True, slots=True)
class ListType(Type):
    element: Type

    def display(self) -> str:
        return surface_type(f"List<{self.element.display()}>")


@dataclass(frozen=True, slots=True)
class StructType(Type):
    name: str

    def display(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class ModelDeclType(Type):
    name: str

    def display(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class TrainingDeclType(Type):
    name: str

    def display(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class OpaqueType(Type):
    name: str

    def display(self) -> str:
        return surface_type(self.name)


ColorType = OpaqueType("Color")
CanvasType = OpaqueType("Canvas")
ModelType = OpaqueType("Model")
DatasetType = OpaqueType("Dataset")
RangeType = OpaqueType("Range")
UIType = OpaqueType("UI")
Scene3DType = OpaqueType("Scene3D")
AgentType = OpaqueType("Agent")
NamespaceType = OpaqueType("<namespace>")

#: Scalar types accepted as tensor dtypes.
TENSOR_DTYPES = ("Float32", "Float64", "Int32", "Bool")

#: Promotion rank for tensor dtypes.
_DTYPE_RANK = {"Bool": 0, "Int32": 1, "Float32": 2, "Float64": 3}


def promote_dtype(a: str, b: str) -> str:
    return a if _DTYPE_RANK[a] >= _DTYPE_RANK[b] else b


def scalar_tensor_dtype(scalar: Type) -> str | None:
    if scalar == IntType:
        return "Int32"
    if scalar == FloatType:
        return "Float32"
    if scalar == BoolType:
        return "Bool"
    return None


def is_numeric(t: Type) -> bool:
    return t in (IntType, FloatType)


def is_assignable(source: Type, target: Type) -> bool:
    """Return True if a value of ``source`` may be used where ``target`` is expected.

    Rules:
    * exact type equality;
    * ``Never`` (bottom) is assignable to everything;
    * a statically-shaped ``Tensor`` is assignable to the same dtype with an
      unknown shape, but not vice versa;
    * ``Any`` is *not* freely assignable — it exists only to describe native
      parameters that genuinely accept heterogeneous values (``print``,
      ``str``). A native signature with ``Any`` is matched by the checker.
    """
    if source == target:
        return True
    if source is ErrorType or target is ErrorType:
        return True
    if source == NeverType:
        return True
    if isinstance(source, TensorType) and isinstance(target, TensorType):
        if source.dtype != target.dtype:
            return False
        if target.shape is None:
            return True
        return source.shape == target.shape
    return False


def broadcast_shapes(a: Sequence[int], b: Sequence[int]) -> tuple[int, ...] | None:
    """NumPy-style right-aligned broadcasting; returns None if incompatible."""
    out: list[int] = []
    for i in range(1, max(len(a), len(b)) + 1):
        da = a[-i] if i <= len(a) else 1
        db = b[-i] if i <= len(b) else 1
        if da == db or db == 1:
            out.append(da)
        elif da == 1:
            out.append(db)
        else:
            return None
    return tuple(reversed(out))


def tensor_binary_result(op: str, left: Type, right: Type) -> tuple[Type | None, str | None]:
    """Compute the result type of a tensor-involving binary operation.

    Returns ``(type, error)``; exactly one is None.
    """
    for side, a, b in (("left", left, right), ("right", right, left)):
        if isinstance(a, TensorType):
            if isinstance(b, TensorType):
                dtype = promote_dtype(a.dtype, b.dtype)
                if a.shape is None or b.shape is None:
                    return TensorType(dtype, None), None
                shape = broadcast_shapes(a.shape, b.shape)
                if shape is None:
                    return None, (
                        f"cannot broadcast shapes {list(a.shape)} and {list(b.shape)} "
                        f"in operator '{op}'"
                    )
                return TensorType(dtype, shape), None
            scalar_dtype = scalar_tensor_dtype(b)
            if scalar_dtype is None:
                return None, f"operator '{op}' is not defined between {a.display()} and {b.display()}"
            dtype = promote_dtype(a.dtype, scalar_dtype)
            return TensorType(dtype, a.shape), None
    return None, None


def common_type(a: Type, b: Type) -> Type | None:
    if a == b:
        return a
    if isinstance(a, TensorType) and isinstance(b, TensorType):
        dtype = promote_dtype(a.dtype, b.dtype)
        if a.shape is None or b.shape is None:
            return TensorType(dtype, None)
        shape = broadcast_shapes(a.shape, b.shape)
        return TensorType(dtype, shape) if shape is not None else None
    return None
