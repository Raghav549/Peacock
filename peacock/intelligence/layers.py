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


class Sequential(Module):
    def __init__(self, layers: Sequence[Dense], input_dim: int | None = None):
        if not layers:
            raise TensorError("Sequential requires at least one layer")
        self.layers = list(layers)
        for i in range(1, len(self.layers)):
            prev, cur = self.layers[i - 1], self.layers[i]
            if cur.input_dim != prev.units:
                raise TensorError(
                    f"layer {i} expects {cur.input_dim} inputs but layer {i - 1} produces {prev.units}"
                )
        self.input_dim = input_dim if input_dim is not None else self.layers[0].input_dim
        if self.input_dim != self.layers[0].input_dim:
            raise TensorError("Sequential input_dim does not match its first layer")
        self.output_dim = self.layers[-1].units

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
        return {
            "input_shape": list(self.input_shape),
            "output_shape": list(self.output_shape),
            "layers": [
                {"units": layer.units, "activation": layer.activation}
                for layer in self.network.layers
            ],
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

    ``layers`` items may be ``(units, activation)`` tuples or dicts with keys
    ``units`` and ``activation``.
    """
    input_shape = tuple(int(d) for d in input_shape)
    output_shape = tuple(int(d) for d in output_shape)
    if not input_shape or not output_shape:
        raise TensorError("model shapes must have rank >= 1")
    specs = []
    for item in layers:
        if isinstance(item, dict):
            specs.append((int(item["units"]), str(item.get("activation", "linear"))))
        else:
            units, activation = item
            specs.append((int(units), str(activation)))
    if not specs:
        raise TensorError("model has no layers")
    rng = RNG(seed)
    dense: list[Dense] = []
    current = input_shape[-1]
    for i, (units, activation) in enumerate(specs):
        if units <= 0:
            raise TensorError("Dense units must be positive")
        dense.append(Dense(current, units, activation, rng=rng, dtype=dtype))
        current = units
    if current != output_shape[-1]:
        raise TensorError(
            f"model stack produces {current} outputs but the declared output last dimension is {output_shape[-1]}"
        )
    network = Sequential(dense, input_dim=input_shape[-1])
    return Model(network, input_shape, output_shape)


def model_from_architecture(arch: dict, seed: int = 0) -> Model:
    return build_model(
        arch["input_shape"],
        arch["output_shape"],
        arch.get("layers", []),
        seed=seed,
    )
