"""PEACOCK tensor core with reverse-mode automatic differentiation.

Design notes
------------
* Storage is a flat Python list plus a shape tuple. This reference backend is
  optimised for clarity and correctness, not speed.
* All arithmetic is performed in IEEE-754 binary64 (Python ``float``). The
  ``Float32`` dtype is a **declared** dtype: host-constructed Float32 tensors are
  rounded to single precision on construction and on serialization, but
  intermediate arithmetic is binary64 in the bootstrap engine. This deviation is
  documented in STATUS.md and tested explicitly.
* Broadcasting follows NumPy's right-aligned rules, implemented from scratch.
* Autodiff is reverse-mode with a topological traversal. Gradients are validated
  against central finite differences in ``tests/ai/test_autodiff.py``.

Only ``math`` (platform libm) is used from outside this package.
"""

from __future__ import annotations

import math
import struct
from typing import Iterable, Sequence

from .random import RNG

FLOAT_DTYPES = ("Float32", "Float64")
NUMERIC_DTYPES = ("Bool", "Int32", "Float32", "Float64")
_DTYPE_RANK = {"Bool": 0, "Int32": 1, "Float32": 2, "Float64": 3}


class TensorError(ValueError):
    """Raised for tensor shape, dtype and numerical-domain errors."""


def _prod(shape: Sequence[int]) -> int:
    out = 1
    for d in shape:
        out *= d
    return out


def _normalize_shape(shape: Iterable[int]) -> tuple[int, ...]:
    dims = tuple(shape)
    for d in dims:
        if not isinstance(d, int) or isinstance(d, bool) or d < 0:
            raise TensorError(f"invalid tensor dimension {d!r}")
    return dims


def _strides(shape: Sequence[int]) -> tuple[int, ...]:
    if not shape:
        return ()
    out = [1] * len(shape)
    for i in range(len(shape) - 2, -1, -1):
        out[i] = out[i + 1] * shape[i + 1]
    return tuple(out)


def _round_f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def _cast_value(value, dtype: str):
    if dtype == "Float32":
        return _round_f32(float(value))
    if dtype == "Float64":
        return float(value)
    if dtype == "Int32":
        return int(value)
    if dtype == "Bool":
        return bool(value)
    raise TensorError(f"unknown dtype {dtype!r}")


def _cast_output(value, dtype: str):
    # Intermediate float32 arithmetic stays in binary64 (documented).
    if dtype == "Int32":
        return int(value)
    if dtype == "Bool":
        return bool(value)
    return float(value)


def promote_dtype(a: str, b: str) -> str:
    return a if _DTYPE_RANK[a] >= _DTYPE_RANK[b] else b


def _is_float_dtype(dtype: str) -> bool:
    return dtype in FLOAT_DTYPES


def _broadcast_shape(a: Sequence[int], b: Sequence[int]) -> tuple[int, ...]:
    out: list[int] = []
    for i in range(1, max(len(a), len(b)) + 1):
        da = a[-i] if i <= len(a) else 1
        db = b[-i] if i <= len(b) else 1
        if da == db:
            out.append(da)
        elif da == 1:
            out.append(db)
        elif db == 1:
            out.append(da)
        else:
            raise TensorError(f"cannot broadcast shapes {list(a)} and {list(b)}")
    return tuple(reversed(out))


def _effective_strides(shape: Sequence[int], out_shape: Sequence[int]) -> tuple[int, ...]:
    """Strides into ``shape`` when read with ``out_shape`` (0 for broadcast dims)."""
    base = _strides(shape)
    aligned = (0,) * (len(out_shape) - len(shape)) + base
    eff = []
    for d in range(len(out_shape)):
        dim = shape[d - (len(out_shape) - len(shape))] if d >= len(out_shape) - len(shape) else 1
        eff.append(0 if dim == 1 else aligned[d])
    return tuple(eff)


class Tensor:
    __slots__ = ("data", "shape", "dtype", "requires_grad", "grad", "_parents", "_backward", "_op")

    def __init__(
        self,
        data: Sequence,
        shape: Sequence[int],
        dtype: str = "Float32",
        requires_grad: bool = False,
        *,
        _parents: tuple["Tensor", ...] = (),
        _backward=None,
        _op: str = "",
        _cast: bool = True,
    ):
        self.shape = _normalize_shape(shape)
        if dtype not in NUMERIC_DTYPES:
            raise TensorError(f"unknown dtype {dtype!r}")
        size = _prod(self.shape)
        if len(data) != size:
            raise TensorError(
                f"tensor data length {len(data)} does not match shape {list(self.shape)} (size {size})"
            )
        if requires_grad and not _is_float_dtype(dtype):
            raise TensorError("only floating-point tensors can require gradients")
        self.dtype = dtype
        self.data = [_cast_value(v, dtype) for v in data] if _cast else list(data)
        self.requires_grad = requires_grad
        self.grad: Tensor | None = None
        self._parents = _parents if requires_grad else ()
        self._backward = _backward if requires_grad else None
        self._op = _op

    # -- construction ------------------------------------------------------
    @classmethod
    def _wrap(cls, data, shape, dtype, requires_grad=False, parents=(), backward=None, op=""):
        return cls(
            data,
            shape,
            dtype,
            requires_grad,
            _parents=parents,
            _backward=backward,
            _op=op,
            _cast=False,
        )

    @classmethod
    def zeros(cls, shape, dtype: str = "Float32", requires_grad: bool = False) -> "Tensor":
        shape = _normalize_shape(shape)
        return cls([_cast_value(0, dtype)] * _prod(shape), shape, dtype, requires_grad)

    @classmethod
    def ones(cls, shape, dtype: str = "Float32", requires_grad: bool = False) -> "Tensor":
        shape = _normalize_shape(shape)
        return cls([_cast_value(1, dtype)] * _prod(shape), shape, dtype, requires_grad)

    @classmethod
    def full(cls, shape, value, dtype: str = "Float32", requires_grad: bool = False) -> "Tensor":
        shape = _normalize_shape(shape)
        return cls([value] * _prod(shape), shape, dtype, requires_grad)

    @classmethod
    def from_nested(cls, nested, dtype: str | None = None, requires_grad: bool = False) -> "Tensor":
        flat, shape, inferred = _flatten_nested(nested)
        if dtype is None:
            dtype = inferred
        if dtype in FLOAT_DTYPES:
            flat = [float(v) for v in flat]
        return cls(flat, shape, dtype, requires_grad)

    @classmethod
    def from_flat(
        cls, data: Sequence, shape, dtype: str = "Float32", requires_grad: bool = False
    ) -> "Tensor":
        return cls(data, shape, dtype, requires_grad)

    @classmethod
    def arange(cls, start: int, stop: int, step: int = 1) -> "Tensor":
        if step == 0:
            raise TensorError("arange step may not be zero")
        values = list(range(start, stop, step))
        return cls(values, (len(values),), "Int32")

    @classmethod
    def eye(cls, n: int, dtype: str = "Float32") -> "Tensor":
        if n < 0:
            raise TensorError("eye size must be non-negative")
        data = [0.0] * (n * n)
        for i in range(n):
            data[i * n + i] = 1.0
        return cls(data, (n, n), dtype)

    @classmethod
    def randn(
        cls, shape, seed: int = 0, mean: float = 0.0, std: float = 1.0, dtype: str = "Float32",
        requires_grad: bool = False,
    ) -> "Tensor":
        shape = _normalize_shape(shape)
        rng = RNG(seed)
        return cls([rng.normal(mean, std) for _ in range(_prod(shape))], shape, dtype, requires_grad)

    @classmethod
    def rand_uniform(
        cls, shape, low: float = 0.0, high: float = 1.0, seed: int = 0, dtype: str = "Float32"
    ) -> "Tensor":
        shape = _normalize_shape(shape)
        rng = RNG(seed)
        return cls([rng.uniform(low, high) for _ in range(_prod(shape))], shape, dtype)

    # -- basic properties --------------------------------------------------
    @property
    def rank(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        return len(self.data)

    def item(self):
        if self.size != 1:
            raise TensorError(f"item() requires a single-element tensor, shape is {list(self.shape)}")
        value = self.data[0]
        return bool(value) if self.dtype == "Bool" else value

    def tolist(self):
        return _nest(self.data, self.shape)

    def clone(self) -> "Tensor":
        return Tensor._wrap(
            list(self.data), self.shape, self.dtype, self.requires_grad, (), None, "clone"
        )

    def detach(self) -> "Tensor":
        return Tensor._wrap(list(self.data), self.shape, self.dtype, False)

    def to(self, dtype: str) -> "Tensor":
        if dtype not in NUMERIC_DTYPES:
            raise TensorError(f"unknown dtype {dtype!r}")
        if dtype == self.dtype:
            return self
        requires = self.requires_grad and _is_float_dtype(dtype)
        if self.requires_grad and not requires:
            raise TensorError("refusing to convert a gradient-tracking tensor to a non-float dtype")
        data = [_cast_value(v, dtype) for v in self.data]
        if not self.requires_grad:
            return Tensor._wrap(data, self.shape, dtype)
        out = Tensor._wrap(data, self.shape, dtype, True, (self,), None, "to")
        src = self

        def backward(g):
            _accumulate(src, Tensor._wrap(list(g.data), src.shape, src.dtype))

        out._backward = backward
        return out

    # -- autodiff ----------------------------------------------------------
    def backward(self, gradient: "Tensor | None" = None) -> None:
        if not self.requires_grad:
            raise TensorError("backward() called on a tensor that does not require gradients")
        if gradient is None:
            if self.size != 1:
                raise TensorError(
                    "backward() requires a scalar tensor (use .sum() or .mean() first), "
                    f"got shape {list(self.shape)}"
                )
            gradient = Tensor._wrap([1.0], self.shape, self.dtype)
        elif gradient.shape != self.shape:
            raise TensorError("gradient shape must match tensor shape")

        topo: list[Tensor] = []
        visited: set[int] = set()
        stack: list[tuple[Tensor, bool]] = [(self, False)]
        while stack:
            node, processed = stack.pop()
            ident = id(node)
            if processed:
                if ident not in visited:
                    visited.add(ident)
                    topo.append(node)
                continue
            if ident in visited:
                continue
            stack.append((node, True))
            for parent in node._parents:
                if id(parent) not in visited:
                    stack.append((parent, False))
        if self.grad is None:
            self.grad = Tensor._wrap(list(gradient.data), self.shape, self.dtype)
        else:
            for i, v in enumerate(gradient.data):
                self.grad.data[i] += v
        for node in reversed(topo):
            if node._backward is not None and node.grad is not None:
                node._backward(node.grad)

    def zero_grad(self) -> None:
        self.grad = None

    # -- operators ---------------------------------------------------------
    def __add__(self, other):
        return add(self, other)

    def __radd__(self, other):
        return add(other, self)

    def __sub__(self, other):
        return sub(self, other)

    def __rsub__(self, other):
        return sub(other, self)

    def __mul__(self, other):
        return mul(self, other)

    def __rmul__(self, other):
        return mul(other, self)

    def __truediv__(self, other):
        return divide(self, other)

    def __rtruediv__(self, other):
        return divide(other, self)

    def __neg__(self):
        return negative(self)

    def __pow__(self, exponent):
        return power(self, exponent)

    def __matmul__(self, other):
        return matmul(self, other)

    def __len__(self) -> int:
        if not self.shape:
            raise TypeError("scalar tensor has no len()")
        return self.shape[0]

    def __repr__(self) -> str:
        body = self.tolist()
        text = repr(body)
        if len(text) > 120:
            text = text[:117] + "..."
        return f"<Tensor {self.dtype}{list(self.shape)} {text}>"


def _nest(data, shape):
    if not shape:
        return data[0]
    if len(shape) == 1:
        return list(data)
    stride = _prod(shape[1:])
    return [_nest(data[i * stride : (i + 1) * stride], shape[1:]) for i in range(shape[0])]


def _flatten_nested(nested) -> tuple[list, tuple[int, ...], str]:
    if isinstance(nested, Tensor):
        return list(nested.data), nested.shape, nested.dtype
    if not isinstance(nested, (list, tuple)):
        if isinstance(nested, bool):
            return [nested], (), "Bool"
        if isinstance(nested, int):
            return [nested], (), "Int32"
        if isinstance(nested, float):
            return [nested], (), "Float32"
        raise TensorError(f"cannot build a tensor from {type(nested).__name__}")
    if not nested:
        raise TensorError("cannot infer the shape of an empty tensor literal")
    flat: list = []
    child_shape = None
    saw_float = False
    saw_int = False
    saw_bool = False
    for element in nested:
        sub, shape, _ = _flatten_nested(element)
        if child_shape is None:
            child_shape = shape
        elif shape != child_shape:
            raise TensorError("nested tensor data must be rectangular")
        flat.extend(sub)
        for v in sub:
            if isinstance(v, bool):
                saw_bool = True
            elif isinstance(v, int):
                saw_int = True
            elif isinstance(v, float):
                saw_float = True
    if saw_float and (saw_int or saw_bool):
        dtype = "Float32"
    elif saw_float:
        dtype = "Float32"
    elif saw_bool and saw_int:
        dtype = "Int32"
    elif saw_bool:
        dtype = "Bool"
    else:
        dtype = "Int32"
    if saw_float:
        flat = [float(v) for v in flat]
    return flat, (len(nested),) + (child_shape or ()), dtype


def ensure_tensor(value) -> Tensor:
    if isinstance(value, Tensor):
        return value
    if isinstance(value, bool):
        return Tensor._wrap([value], (), "Bool")
    if isinstance(value, int):
        return Tensor._wrap([value], (), "Int32")
    if isinstance(value, float):
        return Tensor._wrap([value], (), "Float32")
    raise TensorError(f"expected a Tensor or scalar, found {type(value).__name__}")


def _accumulate(tensor: Tensor, grad: Tensor) -> None:
    if not tensor.requires_grad:
        return
    if tensor.grad is None:
        tensor.grad = Tensor._wrap(list(grad.data), tensor.shape, tensor.dtype)
    else:
        if len(grad.data) == 1 and tensor.size > 1:
            value = grad.data[0]
            for i in range(tensor.size):
                tensor.grad.data[i] += value
        else:
            if len(grad.data) != tensor.size:
                raise TensorError("internal gradient shape mismatch")
            for i, v in enumerate(grad.data):
                tensor.grad.data[i] += v


# ---------------------------------------------------------------------------
# Broadcasting binary operations
# ---------------------------------------------------------------------------
def _binary(a_in, b_in, op: str) -> Tensor:
    a = ensure_tensor(a_in)
    b = ensure_tensor(b_in)
    out_shape = _broadcast_shape(a.shape, b.shape)
    out_dtype = promote_dtype(a.dtype, b.dtype)
    out_size = _prod(out_shape)
    ndim = len(out_shape)
    a_strides = _effective_strides(a.shape, out_shape)
    b_strides = _effective_strides(b.shape, out_shape)
    adata, bdata = a.data, b.data
    out: list = [0] * out_size
    zero_division = False
    indices = [0] * ndim
    for flat in range(out_size):
        oa = 0
        ob = 0
        for d in range(ndim):
            i = indices[d]
            oa += i * a_strides[d]
            ob += i * b_strides[d]
        va = adata[oa]
        vb = bdata[ob]
        if op == "add":
            out[flat] = va + vb
        elif op == "sub":
            out[flat] = va - vb
        elif op == "mul":
            out[flat] = va * vb
        elif op == "div":
            if vb == 0:
                zero_division = True
                break
            out[flat] = va / vb
        else:  # pragma: no cover
            raise TensorError(f"unknown binary op {op}")
        # Odometer increment.
        d = ndim - 1
        while d >= 0:
            indices[d] += 1
            if indices[d] < out_shape[d]:
                break
            indices[d] = 0
            d -= 1
    if zero_division:
        raise TensorError("division by zero in tensor operation")
    if out_dtype == "Int32" and op == "div":
        out = [int(v) for v in out]
    parent_req = a.requires_grad or b.requires_grad
    backward = None
    if parent_req:
        def backward(g: Tensor):
            ga = [0.0] * a.size if a.requires_grad else None
            gb = [0.0] * b.size if b.requires_grad else None
            grad_indices = [0] * ndim
            for flat in range(out_size):
                oa = 0
                ob = 0
                for d in range(ndim):
                    i = grad_indices[d]
                    oa += i * a_strides[d]
                    ob += i * b_strides[d]
                go = g.data[flat]
                va = adata[oa]
                vb = bdata[ob]
                if ga is not None:
                    if op == "add":
                        ga[oa] += go
                    elif op == "sub":
                        ga[oa] += go
                    elif op == "mul":
                        ga[oa] += go * vb
                    elif op == "div":
                        ga[oa] += go / vb
                if gb is not None:
                    if op == "add":
                        gb[ob] += go
                    elif op == "sub":
                        gb[ob] -= go
                    elif op == "mul":
                        gb[ob] += go * va
                    elif op == "div":
                        gb[ob] -= go * va / (vb * vb)
                d = ndim - 1
                while d >= 0:
                    grad_indices[d] += 1
                    if grad_indices[d] < out_shape[d]:
                        break
                    grad_indices[d] = 0
                    d -= 1
            if ga is not None:
                _accumulate(a, Tensor._wrap(ga, a.shape, a.dtype))
            if gb is not None:
                _accumulate(b, Tensor._wrap(gb, b.shape, b.dtype))

    result = Tensor._wrap(out, out_shape, out_dtype, parent_req, (a, b), backward, op)
    return result


def add(a, b) -> Tensor:
    return _binary(a, b, "add")


def sub(a, b) -> Tensor:
    return _binary(a, b, "sub")


def mul(a, b) -> Tensor:
    return _binary(a, b, "mul")


def divide(a, b) -> Tensor:
    return _binary(a, b, "div")


def power(base, exponent) -> Tensor:
    t = ensure_tensor(base)
    if isinstance(exponent, Tensor):
        if exponent.size != 1:
            raise TensorError("tensor exponent must be a scalar in this engine")
        e = exponent.item()
    else:
        e = exponent
    if not isinstance(e, (int, float)) or isinstance(e, bool):
        raise TensorError("exponent must be numeric")
    if t.dtype == "Int32":
        if not isinstance(e, int) or e < 0:
            raise TensorError("integer tensors require a non-negative integer exponent")
        data = [int(v) ** e for v in t.data]
    else:
        data = []
        for v in t.data:
            if v < 0 and not float(e).is_integer():
                raise TensorError("fractional power of a negative tensor value is not real")
            if v == 0 and e < 0:
                raise TensorError("zero raised to a negative power")
            data.append(float(v) ** e)
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            if e == 0:
                gd = [0.0] * t.size
            else:
                gd = [g.data[i] * e * (t.data[i] ** (e - 1)) for i in range(t.size)]
            _accumulate(t, Tensor._wrap(gd, t.shape, t.dtype))

    return Tensor._wrap(data, t.shape, t.dtype, requires, (t,), backward, "power")


# ---------------------------------------------------------------------------
# Unary operations
# ---------------------------------------------------------------------------
def _unary(t_in, name: str, fn, grad_fn, out_dtype: str | None = None) -> Tensor:
    t = ensure_tensor(t_in)
    if t.dtype == "Bool":
        raise TensorError(f"operation '{name}' is not defined for Bool tensors")
    out_dtype = out_dtype or t.dtype
    data = [fn(v) for v in t.data]
    if out_dtype == "Int32":
        data = [int(v) for v in data]
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            gd = grad_fn(t.data, data, g.data)
            _accumulate(t, Tensor._wrap(gd, t.shape, t.dtype))

    return Tensor._wrap(data, t.shape, out_dtype, requires, (t,), backward, name)


def _float_result_dtype(t: Tensor) -> str:
    return t.dtype if t.dtype in FLOAT_DTYPES else "Float32"


def exp(t) -> Tensor:
    tt = ensure_tensor(t)
    return _unary(t, "exp", math.exp, lambda x, y, g: [g[i] * y[i] for i in range(len(x))], _float_result_dtype(tt))


def log(t) -> Tensor:
    tt = ensure_tensor(t)
    for v in tt.data:
        if v <= 0:
            raise TensorError("log is defined only for positive values in PEACOCK's reference engine")
    return _unary(t, "log", math.log, lambda x, y, g: [g[i] / x[i] for i in range(len(x))], _float_result_dtype(tt))


def sqrt(t) -> Tensor:
    tt = ensure_tensor(t)
    for v in tt.data:
        if v < 0:
            raise TensorError("sqrt of a negative value")
    return _unary(t, "sqrt", math.sqrt, lambda x, y, g: [g[i] / (2.0 * y[i]) if y[i] != 0 else 0.0 for i in range(len(x))], _float_result_dtype(tt))


def absolute(t) -> Tensor:
    return _unary(t, "abs", abs, lambda x, y, g: [g[i] * (1.0 if x[i] >= 0 else -1.0) for i in range(len(x))])


def negative(t) -> Tensor:
    return _unary(t, "neg", lambda v: -v, lambda x, y, g: [-v for v in g])


def relu(t) -> Tensor:
    return _unary(t, "relu", lambda v: v if v > 0 else 0.0, lambda x, y, g: [g[i] if x[i] > 0 else 0.0 for i in range(len(x))])


def tanh(t) -> Tensor:
    tt = ensure_tensor(t)
    return _unary(t, "tanh", math.tanh, lambda x, y, g: [g[i] * (1.0 - y[i] * y[i]) for i in range(len(x))], _float_result_dtype(tt))


def sigmoid(t) -> Tensor:
    def fn(v):
        if v >= 0:
            return 1.0 / (1.0 + math.exp(-v))
        z = math.exp(v)
        return z / (1.0 + z)

    tt = ensure_tensor(t)
    return _unary(t, "sigmoid", fn, lambda x, y, g: [g[i] * y[i] * (1.0 - y[i]) for i in range(len(x))], _float_result_dtype(tt))


def gelu(t) -> Tensor:
    """Gaussian Error Linear Unit (Hendrycks & Gimpel 2016 tanh approximation)."""
    k = math.sqrt(2.0 / math.pi)
    c = 0.044715

    def fn(x: float) -> float:
        u = k * (x + c * x * x * x)
        return 0.5 * x * (1.0 + math.tanh(u))

    def grad_fn(xs, _ys, gs):
        out = []
        for x, g in zip(xs, gs):
            u = k * (x + c * x * x * x)
            s = math.tanh(u)
            du = k * (1.0 + 3.0 * c * x * x)
            dgelu = 0.5 * (1.0 + s) + 0.5 * x * (1.0 - s * s) * du
            out.append(g * dgelu)
        return out

    tt = ensure_tensor(t)
    return _unary(t, "gelu", fn, grad_fn, _float_result_dtype(tt))


def layer_norm(t: Tensor, eps: float = 1e-5) -> Tensor:
    """Zero-mean, unit-variance normalisation along the last axis with autodiff."""
    t = ensure_tensor(t)
    if eps <= 0 or not math.isfinite(eps):
        raise TensorError("layer_norm eps must be a positive finite float")
    _axis, outer, inner, n = _axis_groups(t.shape, -1)
    out = [0.0] * t.size
    inv_stds = [0.0] * (outer * inner)
    for o in range(outer):
        for i in range(inner):
            base = o * n * inner + i
            vals = [float(t.data[base + k * inner]) for k in range(n)]
            mean = sum(vals) / n
            var = sum((v - mean) * (v - mean) for v in vals) / n
            inv_std = 1.0 / math.sqrt(var + eps)
            inv_stds[o * inner + i] = inv_std
            for k in range(n):
                out[base + k * inner] = (vals[k] - mean) * inv_std
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            gd = [0.0] * t.size
            for o in range(outer):
                for i in range(inner):
                    base = o * n * inner + i
                    inv_std = inv_stds[o * inner + i]
                    g_vals = [float(g.data[base + k * inner]) for k in range(n)]
                    xhat = [out[base + k * inner] for k in range(n)]
                    sum_g = sum(g_vals)
                    sum_gx = sum(gv * xv for gv, xv in zip(g_vals, xhat))
                    scale = inv_std / n
                    for k in range(n):
                        gd[base + k * inner] = scale * (n * g_vals[k] - sum_g - xhat[k] * sum_gx)
            _accumulate(t, Tensor._wrap(gd, t.shape, t.dtype))

    return Tensor._wrap(out, t.shape, _float_result_dtype(t), requires, (t,), backward, "layer_norm")


def cosine_similarity(a: Tensor, b: Tensor, eps: float = 1e-8) -> float:
    """Cosine similarity between two identically shaped non-empty tensors."""
    a = ensure_tensor(a)
    b = ensure_tensor(b)
    if a.shape != b.shape or a.size == 0:
        raise TensorError(
            f"cosine_similarity requires identical non-empty shapes, got {list(a.shape)} and {list(b.shape)}"
        )
    dot = sum(float(x) * float(y) for x, y in zip(a.data, b.data))
    na = math.sqrt(sum(float(x) * float(x) for x in a.data))
    nb = math.sqrt(sum(float(y) * float(y) for y in b.data))
    denom = max(eps, na * nb)
    return dot / denom


def _axis_groups(shape: Sequence[int], axis: int):
    if not shape:
        raise TensorError("operation requires rank >= 1")
    if axis < 0:
        axis += len(shape)
    if not (0 <= axis < len(shape)):
        raise TensorError(f"axis {axis} out of range for shape {list(shape)}")
    outer = _prod(shape[:axis])
    inner = _prod(shape[axis + 1 :])
    return axis, outer, inner, shape[axis]


def softmax(t: Tensor, axis: int = -1) -> Tensor:
    t = ensure_tensor(t)
    axis, outer, inner, n = _axis_groups(t.shape, axis)
    out = [0.0] * t.size
    for o in range(outer):
        for i in range(inner):
            base = o * n * inner + i
            values = [t.data[base + k * inner] for k in range(n)]
            m = max(values)
            exps = [math.exp(v - m) for v in values]
            s = sum(exps)
            for k in range(n):
                out[base + k * inner] = exps[k] / s
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            gd = [0.0] * t.size
            for o in range(outer):
                for i in range(inner):
                    base = o * n * inner + i
                    dot = sum(g.data[base + k * inner] * out[base + k * inner] for k in range(n))
                    for k in range(n):
                        idx = base + k * inner
                        gd[idx] = out[idx] * (g.data[idx] - dot)
            _accumulate(t, Tensor._wrap(gd, t.shape, t.dtype))

    return Tensor._wrap(out, t.shape, _float_result_dtype(t), requires, (t,), backward, "softmax")


def log_softmax(t: Tensor, axis: int = -1) -> Tensor:
    t = ensure_tensor(t)
    axis, outer, inner, n = _axis_groups(t.shape, axis)
    out = [0.0] * t.size
    for o in range(outer):
        for i in range(inner):
            base = o * n * inner + i
            values = [t.data[base + k * inner] for k in range(n)]
            m = max(values)
            s = sum(math.exp(v - m) for v in values)
            lse = m + math.log(s)
            for k in range(n):
                out[base + k * inner] = values[k] - lse
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            gd = [0.0] * t.size
            for o in range(outer):
                for i in range(inner):
                    base = o * n * inner + i
                    total = sum(g.data[base + k * inner] for k in range(n))
                    for k in range(n):
                        idx = base + k * inner
                        gd[idx] = g.data[idx] - math.exp(out[idx]) * total
            _accumulate(t, Tensor._wrap(gd, t.shape, t.dtype))

    return Tensor._wrap(out, t.shape, _float_result_dtype(t), requires, (t,), backward, "log_softmax")


# ---------------------------------------------------------------------------
# Reductions
# ---------------------------------------------------------------------------
def sum_all(t: Tensor) -> Tensor:
    t = ensure_tensor(t)
    total = sum(t.data)
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            _accumulate(t, Tensor._wrap([g.data[0]] * t.size, t.shape, t.dtype))

    dtype = t.dtype if t.dtype != "Bool" else "Int32"
    return Tensor._wrap([_cast_output(total, dtype)], (), dtype, requires, (t,), backward, "sum")


def mean_all(t: Tensor) -> Tensor:
    t = ensure_tensor(t)
    if t.size == 0:
        raise TensorError("mean of an empty tensor")
    total = sum(t.data) / t.size
    dtype = "Float32" if t.dtype in ("Int32", "Bool") else t.dtype
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            _accumulate(t, Tensor._wrap([g.data[0] / t.size] * t.size, t.shape, t.dtype))

    return Tensor._wrap([total], (), dtype, requires, (t,), backward, "mean")


def max_value(t: Tensor):
    t = ensure_tensor(t)
    if t.size == 0:
        raise TensorError("max of an empty tensor")
    return max(t.data)


def min_value(t: Tensor):
    t = ensure_tensor(t)
    if t.size == 0:
        raise TensorError("min of an empty tensor")
    return min(t.data)


# ---------------------------------------------------------------------------
# Shape operations
# ---------------------------------------------------------------------------
def reshape(t: Tensor, shape: Sequence[int]) -> Tensor:
    t = ensure_tensor(t)
    shape = _normalize_shape(shape)
    if _prod(shape) != t.size:
        raise TensorError(
            f"cannot reshape tensor of size {t.size} to shape {list(shape)}"
        )
    requires = t.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            _accumulate(t, Tensor._wrap(list(g.data), t.shape, t.dtype))

    return Tensor._wrap(list(t.data), shape, t.dtype, requires, (t,), backward, "reshape")


def transpose(t: Tensor, axes: Sequence[int] | None = None) -> Tensor:
    t = ensure_tensor(t)
    if axes is None:
        axes = tuple(range(t.rank - 1, -1, -1))
    axes = tuple(axes)
    if sorted(axes) != list(range(t.rank)):
        raise TensorError("transpose axes must be a permutation of all dimensions")
    old_strides = _strides(t.shape)
    new_shape = tuple(t.shape[a] for a in axes)
    new_strides = _strides(new_shape)
    out = [0] * t.size
    if t.size:
        idx = [0] * t.rank
        for flat in range(t.size):
            old = 0
            for d in range(t.rank):
                old += idx[d] * old_strides[d]
            new_flat = 0
            for d, axis in enumerate(axes):
                new_flat += idx[axis] * new_strides[d]
            out[new_flat] = t.data[old]
            d = t.rank - 1
            while d >= 0:
                idx[d] += 1
                if idx[d] < t.shape[d]:
                    break
                idx[d] = 0
                d -= 1
    requires = t.requires_grad
    backward = None
    if requires:
        inverse = [axes.index(i) for i in range(t.rank)]
        def backward(g: Tensor):
            _accumulate(t, transpose(g, inverse))

    return Tensor._wrap(out, new_shape, t.dtype, requires, (t,), backward, "transpose")


def matmul(a: Tensor, b: Tensor) -> Tensor:
    a = ensure_tensor(a)
    b = ensure_tensor(b)
    if a.rank != 2 or b.rank != 2:
        raise TensorError("matmul supports 2-D tensors only in the reference engine")
    if a.shape[1] != b.shape[0]:
        raise TensorError(f"matmul inner dimensions differ: {a.shape[1]} and {b.shape[0]}")
    m, k = a.shape
    k2, n = b.shape
    out_dtype = promote_dtype(a.dtype, b.dtype)
    ad, bd = a.data, b.data
    out = [0.0] * (m * n)
    for i in range(m):
        arow = i * k
        orow = i * n
        for p in range(k):
            av = ad[arow + p]
            brow = p * n
            for j in range(n):
                out[orow + j] += av * bd[brow + j]
    if out_dtype == "Int32":
        out = [int(v) for v in out]
    requires = a.requires_grad or b.requires_grad
    backward = None
    if requires:
        def backward(g: Tensor):
            gd = g.data
            if a.requires_grad:
                ga = [0.0] * a.size
                for i in range(m):
                    for p in range(k):
                        total = 0.0
                        for j in range(n):
                            total += gd[i * n + j] * bd[p * n + j]
                        ga[i * k + p] += total
                _accumulate(a, Tensor._wrap(ga, a.shape, a.dtype))
            if b.requires_grad:
                gb = [0.0] * b.size
                for p in range(k):
                    for j in range(n):
                        total = 0.0
                        for i in range(m):
                            total += ad[i * k + p] * gd[i * n + j]
                        gb[p * n + j] += total
                _accumulate(b, Tensor._wrap(gb, b.shape, b.dtype))

    return Tensor._wrap(out, (m, n), out_dtype, requires, (a, b), backward, "matmul")


def max_abs_diff(a: Tensor, b: Tensor) -> float:
    """Maximum absolute elementwise difference between two identically shaped tensors."""
    if a.shape != b.shape:
        raise TensorError(
            f"max_abs_diff requires equal shapes, got {list(a.shape)} and {list(b.shape)}"
        )
    return max((abs(x - y) for x, y in zip(a.data, b.data)), default=0.0)


def argmax_last(t: Tensor) -> list[int]:
    """Class indices along the last axis (used by evaluation)."""
    t = ensure_tensor(t)
    if not t.shape:
        return [0]
    n = t.shape[-1]
    outer = t.size // n
    out: list[int] = []
    for o in range(outer):
        base = o * n
        best = 0
        best_v = t.data[base]
        for j in range(1, n):
            if t.data[base + j] > best_v:
                best = j
                best_v = t.data[base + j]
        out.append(best)
    return out


def select_rows(t: Tensor, indices: Sequence[int]) -> Tensor:
    """Gather rows of a rank-2 tensor. The result does not participate in autodiff."""
    t = ensure_tensor(t)
    if t.rank != 2:
        raise TensorError("select_rows requires a 2-D tensor")
    columns = t.shape[1]
    data = []
    for idx in indices:
        if not isinstance(idx, int) or idx < 0 or idx >= t.shape[0]:
            raise TensorError(f"row index {idx!r} out of range for {t.shape[0]} rows")
        start = idx * columns
        data.extend(t.data[start : start + columns])
    return Tensor._wrap(data, (len(indices), columns), t.dtype)
