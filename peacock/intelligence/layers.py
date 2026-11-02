"""Neural-network layers and models, built on PEACOCK's own tensor engine."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from .random import RNG
from .tensor import (
    Tensor,
    TensorError,
    add,
    matmul,
    relu,
    reshape,
    sigmoid,
    softmax,
    tanh,
)

_ACTIVATIONS = ("linear", "relu", "sigmoid", "tanh", "softmax")


def apply_activation(name: str, x: Tensor) -> Tensor:
    if name == "linear":
        return x
    if name == "relu":
        return relu(x)
    if name == "sigmoid":
        return sigmoid(x)
    if name == "tanh":
        return tanh(x)
    if name == "softmax":
        return softmax(x, axis=-1)
    raise TensorError(f"unknown activation '{name}'")


class Module:
    def parameters(self) -> list[Tensor]:  # pragma: no cover - abstract
        raise NotImplementedError

    def named_parameters(self, prefix: str = "") -> list[tuple[str, Tensor]]:
        raise NotImplementedError

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.zero_grad()

    def parameter_count(self) -> int:
        return sum(p.size for p in self.parameters())

    def forward(self, x: Tensor) -> Tensor:  # pragma: no cover - abstract
        raise NotImplementedError


class Dense(Module):
    """Affine transform followed by a named activation."""

    def __init__(
        self,
        input_dim: int,
        units: int,
        activation: str = "linear",
        rng: RNG | None = None,
        seed: int = 0,
        dtype: str = "Float32",
    ):
        if not isinstance(input_dim, int) or input_dim <= 0:
            raise TensorError("Dense input_dim must be a positive integer")
        if not isinstance(units, int) or units <= 0:
            raise TensorError("Dense units must be a positive integer")
        if activation not in _ACTIVATIONS:
            raise TensorError(f"unknown activation '{activation}'")
        if dtype not in ("Float32", "Float64"):
            raise TensorError("Dense parameters must use a floating dtype")
        self.input_dim = input_dim
        self.units = units
        self.activation = activation
        self.dtype = dtype
        rng = rng or RNG(seed)
        if activation == "relu":
            std = math.sqrt(2.0 / input_dim)
            weights = [rng.normal(0.0, std) for _ in range(input_dim * units)]
        else:
            limit = math.sqrt(6.0 / (input_dim + units))
            weights = [rng.uniform(-limit, limit) for _ in range(input_dim * units)]
        self.weight = Tensor(weights, (input_dim, units), dtype, requires_grad=True)
        self.bias = Tensor.zeros((units,), dtype, requires_grad=True)

    def forward(self, x: Tensor) -> Tensor:
        if not isinstance(x, Tensor):
            raise TensorError("Dense expects a Tensor input")
        if x.dtype not in ("Float32", "Float64"):
            raise TensorError("Dense expects a floating-point input tensor")
        original_rank = x.rank
        if original_rank == 1:
            if x.shape[0] != self.input_dim:
                raise TensorError(
                    f"Dense expects {self.input_dim} features, got {x.shape[0]}"
                )
            x2 = reshape(x, (1, self.input_dim))
            z = add(matmul(x2, self.weight), self.bias)
            z = apply_activation(self.activation, z)
            return reshape(z, (self.units,))
        if original_rank == 2:
            if x.shape[1] != self.input_dim:
                raise TensorError(
                    f"Dense expects {self.input_dim} features, got {x.shape[1]}"
                )
            z = add(matmul(x, self.weight), self.bias)
            return apply_activation(self.activation, z)
        raise TensorError("Dense expects a rank-1 or rank-2 input tensor")

    def parameters(self) -> list[Tensor]:
        return [self.weight, self.bias]

    def named_parameters(self, prefix: str = "") -> list[tuple[str, Tensor]]:
        p = f"{prefix}." if prefix else ""
        return [(f"{p}weight", self.weight), (f"{p}bias", self.bias)]

    def __repr__(self) -> str:  # pragma: no cover
        return f"Dense({self.input_dim}->{self.units}, {self.activation})"


class LayerNorm(Module):
    """Layer normalization over the last dimension with learnable scale and shift."""

    def __init__(
        self,
        normalized_dim: int,
        eps: float = 1e-5,
        dtype: str = "Float32",
    ):
        if not isinstance(normalized_dim, int) or normalized_dim <= 0:
            raise TensorError("LayerNorm normalized_dim must be a positive integer")
        if dtype not in ("Float32", "Float64"):
            raise TensorError("LayerNorm parameters must use a floating dtype")
        self.normalized_dim = normalized_dim
        self.eps = float(eps)
        self.dtype = dtype
        self.gamma = Tensor.ones((normalized_dim,), dtype, requires_grad=True)
        self.beta = Tensor.zeros((normalized_dim,), dtype, requires_grad=True)

    def forward(self, x: Tensor) -> Tensor:
        from .tensor import layer_norm as _layer_norm

        if not isinstance(x, Tensor):
            raise TensorError("LayerNorm expects a Tensor input")
        if x.shape[-1] != self.normalized_dim:
            raise TensorError(
                f"LayerNorm expects last dim {self.normalized_dim}, got {x.shape[-1]} in shape {list(x.shape)}"
            )
        return _layer_norm(x, self.gamma, self.beta, self.eps)

    def parameters(self) -> list[Tensor]:
        return [self.gamma, self.beta]

    def named_parameters(self, prefix: str = "") -> list[tuple[str, Tensor]]:
        p = f"{prefix}." if prefix else ""
        return [(f"{p}gamma", self.gamma), (f"{p}beta", self.beta)]

    def __repr__(self) -> str:  # pragma: no cover
        return f"LayerNorm({self.normalized_dim}, eps={self.eps})"


class Sequential(Module):
    def __init__(self, layers: Sequence[Module], input_dim: int | None = None):
        if not layers:
            raise TensorError("Sequential requires at least one layer")
        self.layers = list(layers)

        def _out_dim(m: Module) -> int:
            if isinstance(m, Dense):
                return m.units
            if isinstance(m, LayerNorm):
                return m.normalized_dim
            raise TensorError(f"unknown layer type {type(m).__name__}")

        def _in_dim(m: Module) -> int:
            if isinstance(m, Dense):
                return m.input_dim
            if isinstance(m, LayerNorm):
                return m.normalized_dim
            raise TensorError(f"unknown layer type {type(m).__name__}")

        for i in range(1, len(self.layers)):
            prev, cur = self.layers[i - 1], self.layers[i]
            if _in_dim(cur) != _out_dim(prev):
                raise TensorError(
                    f"layer {i} expects {_in_dim(cur)} inputs but layer {i - 1} produces {_out_dim(prev)}"
                )
        first_in = _in_dim(self.layers[0])
        self.input_dim = input_dim if input_dim is not None else first_in
        if self.input_dim != first_in:
            raise TensorError("Sequential input_dim does not match its first layer")
        self.output_dim = _out_dim(self.layers[-1])

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def parameters(self) -> list[Tensor]:
        out: list[Tensor] = []
        for layer in self.layers:
            out.extend(layer.parameters())
        return out

    def named_parameters(self, prefix: str = "") -> list[tuple[str, Tensor]]:
        out: list[tuple[str, Tensor]] = []
        for i, layer in enumerate(self.layers):
            base = f"layers.{i}"
            if prefix:
                base = f"{prefix}.{base}"
            out.extend(layer.named_parameters(base))
        return out

    def summary(self) -> str:
        layers = ", ".join(repr(layer) for layer in self.layers)
        return (
            f"Sequential(input={self.input_dim}, layers=[{layers}], "
            f"params={self.parameter_count()}, output={self.output_dim})"
        )

    def __repr__(self) -> str:  # pragma: no cover
        return self.summary()


class Model:
    """A serialisable model: architecture plus a concrete network."""

    def __init__(self, network: Sequential, input_shape: Sequence[int], output_shape: Sequence[int]):
        self.network = network
        self.input_shape = tuple(input_shape)
        self.output_shape = tuple(output_shape)
        if not self.input_shape or not self.output_shape:
            raise TensorError("model input and output shapes must have rank >= 1")
        if self.input_shape[-1] != network.input_dim:
            raise TensorError("model input feature dimension does not match the network")
        if self.output_shape[-1] != network.output_dim:
            raise TensorError("model output dimension does not match the network")

    # -- evaluation --------------------------------------------------------
    def forward(self, x: Tensor) -> Tensor:
        if not isinstance(x, Tensor):
            raise TensorError("model input must be a Tensor")
        if x.rank == 1:
            if x.shape[0] != self.input_shape[-1]:
                raise TensorError(
                    f"model expects {self.input_shape[-1]} features, got {x.shape[0]}"
                )
            return self.network.forward(x)
        if x.rank == 2:
            if x.shape[1] != self.input_shape[-1]:
                raise TensorError(
                    f"model expects {self.input_shape[-1]} features, got {x.shape[1]}"
                )
            return self.network.forward(x)
        raise TensorError("model expects a rank-1 or rank-2 input tensor")

    def predict(self, x: Tensor) -> Tensor:
        out = self.forward(x)
        return out.detach()

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)

    # -- parameters --------------------------------------------------------
    def parameters(self) -> list[Tensor]:
        return self.network.parameters()

    def named_parameters(self) -> list[tuple[str, Tensor]]:
        return self.network.named_parameters()

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.zero_grad()

    @property
    def parameter_count(self) -> int:
        return self.network.parameter_count()

    def summary(self) -> str:
        return self.network.summary()

    # -- serialisation -----------------------------------------------------
    def architecture(self) -> dict:
        layers = []
        for layer in self.network.layers:
            if isinstance(layer, Dense):
                layers.append({"type": "dense", "units": layer.units, "activation": layer.activation})
            elif isinstance(layer, LayerNorm):
                layers.append({"type": "layernorm", "normalized_dim": layer.normalized_dim, "eps": layer.eps})
            else:
                raise TensorError(f"unknown layer type {type(layer).__name__}")
        return {
            "input_shape": list(self.input_shape),
            "output_shape": list(self.output_shape),
            "layers": layers,
            "input_dim": self.network.input_dim,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"Model({self.summary()})"


def build_model(
    input_shape: Sequence[int],
    output_shape: Sequence[int],
    layers: Iterable,
    seed: int = 0,
    dtype: str = "Float32",
) -> Model:
    """Build a model from a language declaration.

    ``layers`` items may be ``(units, activation)`` tuples, dicts with
    ``type``/``units``/``activation`` for dense, or ``type: layernorm``
    with ``normalized_dim``/``eps`` for LayerNorm.
    """
    input_shape = tuple(int(d) for d in input_shape)
    output_shape = tuple(int(d) for d in output_shape)
    if not input_shape or not output_shape:
        raise TensorError("model shapes must have rank >= 1")
    rng = RNG(seed)
    built: list[Module] = []
    current = input_shape[-1]
    for item in layers:
        if isinstance(item, dict):
            t = str(item.get("type", "dense"))
            if t == "layernorm":
                nd = int(item.get("normalized_dim", item.get("units", current)))
                eps = float(item.get("eps", 1e-5))
                if nd != current:
                    raise TensorError(f"LayerNorm expects {current} features, got {nd}")
                built.append(LayerNorm(nd, eps=eps, dtype=dtype))
            else:  # dense
                units = int(item["units"])
                activation = str(item.get("activation", "linear"))
                if units <= 0:
                    raise TensorError("Dense units must be positive")
                built.append(Dense(current, units, activation, rng=rng, dtype=dtype))
                current = units
        else:
            # legacy tuple (units, activation) -> dense
            units, activation = item
            units = int(units)
            activation = str(activation)
            if units <= 0:
                raise TensorError("Dense units must be positive")
            built.append(Dense(current, units, activation, rng=rng, dtype=dtype))
            current = units
    if not built:
        raise TensorError("model has no layers")
    if current != output_shape[-1]:
        raise TensorError(
            f"model stack produces {current} outputs but the declared output last dimension is {output_shape[-1]}"
        )
    network = Sequential(built, input_dim=input_shape[-1])
    return Model(network, input_shape, output_shape)


def model_from_architecture(arch: dict, seed: int = 0) -> Model:
    return build_model(
        arch["input_shape"],
        arch["output_shape"],
        arch.get("layers", []),
        seed=seed,
    )
