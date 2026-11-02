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
    scaled_dot_product_attention,
    transpose,
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
        if x.shape[-1] != self.input_dim:
            raise TensorError(
                f"Dense expects {self.input_dim} features, got {x.shape[-1]} in shape {list(x.shape)}"
            )
        if x.rank == 1:
            x2 = reshape(x, (1, self.input_dim))
            z = add(matmul(x2, self.weight), self.bias)
            z = apply_activation(self.activation, z)
            return reshape(z, (self.units,))
        # ND case: last dim is features, leading dims are batch/sequence
        if x.rank == 2:
            z = add(matmul(x, self.weight), self.bias)
            return apply_activation(self.activation, z)
        # rank >=3: flatten leading dims, matmul, then reshape back
        leading_shape = x.shape[:-1]
        leading_size = 1
        for d in leading_shape:
            leading_size *= d
        x2 = reshape(x, (leading_size, self.input_dim))
        z2 = add(matmul(x2, self.weight), self.bias)
        z2 = apply_activation(self.activation, z2)
        out_shape = leading_shape + (self.units,)
        return reshape(z2, out_shape)

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


def positional_encoding(seq_len: int, d_model: int, dtype: str = "Float32") -> Tensor:
    """Sinusoidal positional encoding as in Vaswani et al. 2017: shape (seq_len, d_model)."""
    if seq_len <= 0 or d_model <= 0:
        raise TensorError("positional_encoding requires positive seq_len and d_model")
    data = [0.0] * (seq_len * d_model)
    for pos in range(seq_len):
        for i in range(d_model):
            angle = pos / (10000 ** (2 * (i // 2) / d_model))
            if i % 2 == 0:
                data[pos * d_model + i] = math.sin(angle)
            else:
                data[pos * d_model + i] = math.cos(angle)
    return Tensor(data, (seq_len, d_model), dtype)


class MultiHeadAttention(Module):
    """Multi-head scaled dot-product attention."""

    def __init__(
        self,
        input_dim: int,
        d_model: int,
        num_heads: int,
        dtype: str = "Float32",
        seed: int = 0,
    ):
        if not isinstance(input_dim, int) or input_dim <= 0:
            raise TensorError("MultiHeadAttention input_dim must be positive")
        if not isinstance(d_model, int) or d_model <= 0:
            raise TensorError("MultiHeadAttention d_model must be positive")
        if not isinstance(num_heads, int) or num_heads <= 0:
            raise TensorError("MultiHeadAttention num_heads must be positive")
        if d_model % num_heads != 0:
            raise TensorError(f"d_model {d_model} must be divisible by num_heads {num_heads}")
        if dtype not in ("Float32", "Float64"):
            raise TensorError("MultiHeadAttention parameters must use a floating dtype")
        self.input_dim = input_dim
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.dtype = dtype
        rng = RNG(seed)
        # Xavier uniform for Q, K, V, O
        def _xavier(in_dim: int, out_dim: int) -> list[float]:
            limit = math.sqrt(6.0 / (in_dim + out_dim))
            return [rng.uniform(-limit, limit) for _ in range(in_dim * out_dim)]

        self.w_q = Tensor(_xavier(input_dim, d_model), (input_dim, d_model), dtype, requires_grad=True)
        self.b_q = Tensor.zeros((d_model,), dtype, requires_grad=True)
        self.w_k = Tensor(_xavier(input_dim, d_model), (input_dim, d_model), dtype, requires_grad=True)
        self.b_k = Tensor.zeros((d_model,), dtype, requires_grad=True)
        self.w_v = Tensor(_xavier(input_dim, d_model), (input_dim, d_model), dtype, requires_grad=True)
        self.b_v = Tensor.zeros((d_model,), dtype, requires_grad=True)
        self.w_o = Tensor(_xavier(d_model, d_model), (d_model, d_model), dtype, requires_grad=True)
        self.b_o = Tensor.zeros((d_model,), dtype, requires_grad=True)

    def _split_heads(self, x: Tensor) -> Tensor:
        # x: (batch, seq_len, d_model) -> (batch, num_heads, seq_len, head_dim)
        batch, seq_len = x.shape[0], x.shape[1]
        # reshape to (batch, seq_len, num_heads, head_dim)
        x_4 = reshape(x, (batch, seq_len, self.num_heads, self.head_dim))
        # transpose to (batch, num_heads, seq_len, head_dim) = axes (0,2,1,3)
        return transpose(x_4, (0, 2, 1, 3))

    def _combine_heads(self, x: Tensor) -> Tensor:
        # x: (batch, num_heads, seq_len, head_dim) -> (batch, seq_len, d_model)
        # transpose to (batch, seq_len, num_heads, head_dim)
        x_t = transpose(x, (0, 2, 1, 3))
        batch, seq_len = x_t.shape[0], x_t.shape[1]
        return reshape(x_t, (batch, seq_len, self.d_model))

    def forward(self, x: Tensor) -> Tensor:
        if not isinstance(x, Tensor):
            raise TensorError("MultiHeadAttention expects a Tensor input")
        if x.dtype not in ("Float32", "Float64"):
            raise TensorError("MultiHeadAttention expects a floating-point input tensor")
        # Handle rank 2 (seq_len, input_dim) as batch=1
        squeeze_batch = False
        orig_rank = x.rank
        if x.rank == 2:
            if x.shape[1] != self.input_dim:
                raise TensorError(f"MultiHeadAttention expects last dim {self.input_dim}, got {x.shape[1]}")
            x = reshape(x, (1, x.shape[0], x.shape[1]))
            squeeze_batch = True
        elif x.rank == 3:
            if x.shape[2] != self.input_dim:
                raise TensorError(f"MultiHeadAttention expects last dim {self.input_dim}, got {x.shape[2]}")
        else:
            raise TensorError("MultiHeadAttention expects rank-2 (seq_len, input_dim) or rank-3 (batch, seq_len, input_dim)")
        batch, seq_len = x.shape[0], x.shape[1]
        # Linear projections: (batch, seq_len, input_dim) @ (input_dim, d_model) -> (batch, seq_len, d_model)
        # Use Dense-style logic: flatten batch*seq, matmul, reshape
        def _linear(inp: Tensor, w: Tensor, b: Tensor) -> Tensor:
            flat = reshape(inp, (batch * seq_len, self.input_dim))
            proj = matmul(flat, w)  # (B*S, d_model)
            # add bias via broadcast: reshape bias to (1, d_model) and add
            # Use add with broadcasting - need to ensure bias broadcasts correctly
            # Expand bias to (B*S, d_model) by adding
            proj = add(proj, b)  # b is (d_model,) broadcasts to (B*S, d_model)
            return reshape(proj, (batch, seq_len, self.d_model))

        q = _linear(x, self.w_q, self.b_q)
        k = _linear(x, self.w_k, self.b_k)
        v = _linear(x, self.w_v, self.b_v)
        # Split heads
        qh = self._split_heads(q)
        kh = self._split_heads(k)
        vh = self._split_heads(v)
        # Attention: (batch, heads, seq, head_dim) -> (batch, heads, seq, head_dim)
        attn_out = scaled_dot_product_attention(qh, kh, vh)
        # Combine heads
        combined = self._combine_heads(attn_out)
        # Output projection
        flat_out = reshape(combined, (batch * seq_len, self.d_model))
        proj = matmul(flat_out, self.w_o)
        proj = add(proj, self.b_o)
        out = reshape(proj, (batch, seq_len, self.d_model))
        if squeeze_batch:
            out = reshape(out, (seq_len, self.d_model))
        return out

    def parameters(self) -> list[Tensor]:
        return [self.w_q, self.b_q, self.w_k, self.b_k, self.w_v, self.b_v, self.w_o, self.b_o]

    def named_parameters(self, prefix: str = "") -> list[tuple[str, Tensor]]:
        p = f"{prefix}." if prefix else ""
        return [
            (f"{p}w_q", self.w_q),
            (f"{p}b_q", self.b_q),
            (f"{p}w_k", self.w_k),
            (f"{p}b_k", self.b_k),
            (f"{p}w_v", self.w_v),
            (f"{p}b_v", self.b_v),
            (f"{p}w_o", self.w_o),
            (f"{p}b_o", self.b_o),
        ]

    def __repr__(self) -> str:  # pragma: no cover
        return f"MultiHeadAttention(input_dim={self.input_dim}, d_model={self.d_model}, heads={self.num_heads})"


class TransformerBlock(Module):
    """Transformer encoder block: Attention -> Add&Norm -> FFN -> Add&Norm."""

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int | None = None,
        dtype: str = "Float32",
        seed: int = 0,
    ):
        if d_model <= 0:
            raise TensorError("TransformerBlock d_model must be positive")
        d_ff = d_ff or 4 * d_model
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_ff = d_ff
        self.dtype = dtype
        # Sub-layers
        self.attn = MultiHeadAttention(d_model, d_model, num_heads, dtype=dtype, seed=seed)
        self.norm1 = LayerNorm(d_model, dtype=dtype)
        self.norm2 = LayerNorm(d_model, dtype=dtype)
        # Feed-forward
        self.ff1 = Dense(d_model, d_ff, activation="relu", seed=seed + 1, dtype=dtype)
        self.ff2 = Dense(d_ff, d_model, activation="linear", seed=seed + 2, dtype=dtype)

    def forward(self, x: Tensor) -> Tensor:
        # Pre-norm vs post-norm: use post-norm as original: x + Attn(LayerNorm(x))? Actually original is LayerNorm(x + Sublayer(x))
        # We'll do: residual = x; x_norm = norm1(x); attn = attn(x_norm); x = residual + attn; then similar for FFN
        # But simpler: x = norm(add(x, attn(x))) style
        # Let's do post-norm: x1 = attn(x); x = norm1(add(x, x1))
        from .tensor import add as t_add

        # Self-attention block
        attn_out = self.attn.forward(x)
        # residual add
        if x.shape != attn_out.shape:
            raise TensorError(f"TransformerBlock residual shape mismatch: {x.shape} vs {attn_out.shape}")
        x_res = t_add(x, attn_out)
        x = self.norm1.forward(x_res)
        # Feed-forward block
        ff_out = self.ff2.forward(self.ff1.forward(x))
        x_res2 = t_add(x, ff_out)
        x = self.norm2.forward(x_res2)
        return x

    def parameters(self) -> list[Tensor]:
        out: list[Tensor] = []
        for m in [self.attn, self.norm1, self.norm2, self.ff1, self.ff2]:
            out.extend(m.parameters())
        return out

    def named_parameters(self, prefix: str = "") -> list[tuple[str, Tensor]]:
        out: list[tuple[str, Tensor]] = []
        for i, (name, mod) in enumerate(
            [("attn", self.attn), ("norm1", self.norm1), ("norm2", self.norm2), ("ff1", self.ff1), ("ff2", self.ff2)]
        ):
            base = f"{prefix}.{name}" if prefix else name
            out.extend(mod.named_parameters(base))
        return out

    def __repr__(self) -> str:  # pragma: no cover
        return f"TransformerBlock(d_model={self.d_model}, heads={self.num_heads}, d_ff={self.d_ff})"


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
            if isinstance(m, MultiHeadAttention):
                return m.d_model
            if isinstance(m, TransformerBlock):
                return m.d_model
            raise TensorError(f"unknown layer type {type(m).__name__}")

        def _in_dim(m: Module) -> int:
            if isinstance(m, Dense):
                return m.input_dim
            if isinstance(m, LayerNorm):
                return m.normalized_dim
            if isinstance(m, MultiHeadAttention):
                return m.input_dim
            if isinstance(m, TransformerBlock):
                return m.d_model
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
        if x.rank >= 2:
            if x.shape[-1] != self.input_shape[-1]:
                raise TensorError(
                    f"model expects {self.input_shape[-1]} features, got {x.shape[-1]} in shape {list(x.shape)}"
                )
            return self.network.forward(x)
        raise TensorError("model expects a tensor with rank >= 1")

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
            elif isinstance(layer, MultiHeadAttention):
                layers.append(
                    {
                        "type": "attention",
                        "input_dim": layer.input_dim,
                        "d_model": layer.d_model,
                        "num_heads": layer.num_heads,
                    }
                )
            elif isinstance(layer, TransformerBlock):
                layers.append(
                    {
                        "type": "transformer",
                        "d_model": layer.d_model,
                        "num_heads": layer.num_heads,
                        "d_ff": layer.d_ff,
                    }
                )
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
    ``type``/``units``/``activation`` for dense, ``type: layernorm``
    with ``normalized_dim``/``eps`` for LayerNorm, ``type: attention``
    with ``input_dim``/``d_model``/``num_heads`` for MultiHeadAttention,
    or ``type: transformer`` with ``d_model``/``num_heads``/``d_ff`` for
    TransformerBlock.
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
            elif t == "attention":
                inp = int(item.get("input_dim", current))
                dm = int(item.get("d_model", item.get("units", inp)))
                heads = int(item.get("num_heads", 1))
                if inp != current:
                    raise TensorError(f"Attention expects {current} features, got {inp}")
                built.append(MultiHeadAttention(inp, dm, heads, dtype=dtype, seed=rng.next_u64() % (1<<31)))
                current = dm
            elif t == "transformer":
                dm = int(item.get("d_model", current))
                heads = int(item.get("num_heads", 1))
                dff = int(item.get("d_ff", 4 * dm)) if "d_ff" in item else None
                if dm != current:
                    raise TensorError(f"TransformerBlock expects {current} features, got {dm}")
                built.append(TransformerBlock(dm, heads, d_ff=dff, dtype=dtype, seed=rng.next_u64() % (1<<31)))
                current = dm
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
