"""Small, deterministic datasets with recorded provenance.

The engine intentionally ships only synthetic datasets. Nothing is downloaded.
Every dataset records how it was generated so experiments can be reproduced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .random import RNG
from .tensor import Tensor, TensorError, select_rows


@dataclass
class Dataset:
    features: Tensor
    labels: Tensor
    name: str = "unnamed"
    provenance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.features, Tensor) or not isinstance(self.labels, Tensor):
            raise TensorError("Dataset features and labels must be Tensors")
        if self.features.rank != 2:
            raise TensorError("Dataset features must be rank 2 [samples, features]")
        if self.labels.rank not in (1, 2):
            raise TensorError("Dataset labels must be rank 1 [samples] or rank 2 [samples, classes]")
        if self.labels.shape[0] != self.features.shape[0]:
            raise TensorError(
                f"Dataset has {self.features.shape[0]} feature rows but {self.labels.shape[0]} label rows"
            )
        if self.features.dtype not in ("Float32", "Float64"):
            self.features = self.features.to("Float32")
        if self.labels.dtype == "Bool":
            self.labels = self.labels.to("Float32")

    def __len__(self) -> int:
        return self.features.shape[0]

    @property
    def size(self) -> int:
        return len(self)

    @property
    def feature_dim(self) -> int:
        return self.features.shape[1]

    @property
    def classes(self) -> int | None:
        if self.labels.rank == 2:
            return self.labels.shape[1]
        return None

    def subset(self, indices: list[int]) -> "Dataset":
        if self.labels.rank == 2:
            labels = select_rows(self.labels, indices)
        else:
            labels = Tensor._wrap(
                [self.labels.data[i] for i in indices], (len(indices),), self.labels.dtype
            )
        return Dataset(select_rows(self.features, indices), labels, self.name, dict(self.provenance))

    def metadata(self) -> dict:
        return {
            "name": self.name,
            "samples": len(self),
            "feature_dim": self.feature_dim,
            "label_shape": list(self.labels.shape),
            "label_dtype": self.labels.dtype,
            "provenance": dict(self.provenance),
        }


def xor_dataset() -> Dataset:
    features = Tensor.from_nested(
        [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]], dtype="Float32"
    )
    labels = Tensor.from_nested(
        [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]], dtype="Float32"
    )
    return Dataset(
        features,
        labels,
        "xor",
        {
            "kind": "synthetic",
            "generator": "truth table",
            "samples": 4,
            "classes": 2,
            "seed": None,
            "licence": "generated locally; no external data",
        },
    )


def spiral_dataset(per_class: int = 100, noise: float = 0.1, seed: int = 0) -> Dataset:
    if not isinstance(per_class, int) or per_class < 1:
        raise TensorError("per_class must be a positive integer")
    if not isinstance(noise, (int, float)) or noise < 0:
        raise TensorError("noise must be non-negative")
    rng = RNG(seed)
    features: list[float] = []
    labels: list[float] = []
    total = per_class * 2
    for cls in range(2):
        for k in range(per_class):
            t = k / max(1, per_class - 1)
            radius = 0.08 + 0.92 * t
            angle = 1.9 * 2.0 * math.pi * t + cls * math.pi
            x = radius * math.cos(angle) + rng.normal(0.0, noise * 0.3)
            y = radius * math.sin(angle) + rng.normal(0.0, noise * 0.3)
            features.extend([x, y])
            labels.extend([1.0, 0.0] if cls == 0 else [0.0, 1.0])
    ds = Dataset(
        Tensor(features, (total, 2), "Float32"),
        Tensor(labels, (total, 2), "Float32"),
        "spiral",
        {
            "kind": "synthetic",
            "generator": "two-arm Archimedean spiral",
            "per_class": per_class,
            "noise": noise,
            "seed": seed,
            "samples": total,
            "classes": 2,
            "licence": "generated locally; no external data",
        },
    )
    return ds


def make_dataset(features: Tensor, labels: Tensor, name: str = "custom") -> Dataset:
    return Dataset(features, labels, name, {"kind": "host-supplied", "licence": "unknown"})


def labels_as_indices(labels: Tensor) -> list[int]:
    """Return class indices for rank-1 label ids or rank-2 one-hot labels."""
    if labels.rank == 1:
        return [int(v) for v in labels.data]
    if labels.rank == 2:
        out = []
        n = labels.shape[1]
        for i in range(labels.shape[0]):
            row = labels.data[i * n : (i + 1) * n]
            out.append(max(range(n), key=lambda j: row[j]))
        return out
    raise TensorError("labels must be rank 1 or 2")
