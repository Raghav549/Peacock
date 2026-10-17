"""Deterministic training and evaluation loops.

Every training run records its full configuration, dataset provenance and
parameter count. No experimental result is claimed without this record.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from .datasets import Dataset
from .evaluation import accuracy_score
from .layers import Model
from .optim import make_optimizer
from .random import RNG
from .tensor import (
    Tensor,
    TensorError,
    log_softmax,
    mean_all,
    mul,
    select_rows,
    sub,
    sum_all,
)


def _targets_tensor(logits: Tensor, labels: Tensor) -> Tensor:
    if logits.rank != 2:
        raise TensorError("loss expects logits of shape [samples, classes]")
    if labels.rank == 2:
        if labels.shape != logits.shape:
            raise TensorError(
                f"label shape {list(labels.shape)} does not match logits {list(logits.shape)}"
            )
        return labels
    if labels.rank == 1:
        if labels.shape[0] != logits.shape[0]:
            raise TensorError("label row count does not match logits")
        classes = logits.shape[1]
        data = [0.0] * (logits.shape[0] * classes)
        for i, value in enumerate(labels.data):
            cls = int(value)
            if cls != value or not (0 <= cls < classes):
                raise TensorError(f"class label {value!r} out of range for {classes} classes")
            data[i * classes + cls] = 1.0
        return Tensor(data, (logits.shape[0], classes), "Float32")
    raise TensorError("labels must be rank 1 or rank 2")


def cross_entropy_loss(logits: Tensor, labels: Tensor) -> Tensor:
    """Mean cross entropy from raw logits with one-hot or class-index labels."""
    targets = _targets_tensor(logits, labels)
    log_probs = log_softmax(logits, axis=-1)
    product = mul(log_probs, targets)
    total = sum_all(product)
    batch = logits.shape[0]
    return mul(total, -1.0 / batch)


def mse_loss(predictions: Tensor, targets: Tensor) -> Tensor:
    if predictions.shape != targets.shape:
        raise TensorError(
            f"MSE requires equal shapes, got {list(predictions.shape)} and {list(targets.shape)}"
        )
    diff = sub(predictions, targets)
    return mean_all(mul(diff, diff))


def compute_loss(objective: str, logits: Tensor, labels: Tensor) -> Tensor:
    if objective == "cross_entropy":
        return cross_entropy_loss(logits, labels)
    if objective == "mse":
        return mse_loss(logits, labels)
    raise TensorError(f"unknown objective '{objective}'")


@dataclass
class TrainingReport:
    objective: str
    optimiser: str
    epochs: int
    learning_rate: float
    batch_size: int
    seed: int
    losses: list[float]
    accuracies: list[float]
    parameter_count: int
    samples: int
    elapsed_seconds: float
    dataset: dict = field(default_factory=dict)
    model_summary: str = ""
    notes: list[str] = field(default_factory=list)
    final_loss: float | None = None
    final_accuracy: float | None = None

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "optimiser": self.optimiser,
            "epochs": self.epochs,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "seed": self.seed,
            "losses": list(self.losses),
            "accuracies": list(self.accuracies),
            "parameter_count": self.parameter_count,
            "samples": self.samples,
            "elapsed_seconds": self.elapsed_seconds,
            "dataset": self.dataset,
            "model_summary": self.model_summary,
            "notes": list(self.notes),
            "final_loss": self.final_loss,
            "final_accuracy": self.final_accuracy,
        }


def _batch_labels(labels: Tensor, indices: list[int]) -> Tensor:
    if labels.rank == 2:
        return select_rows(labels, indices)
    return Tensor._wrap([labels.data[i] for i in indices], (len(indices),), labels.dtype)


def _gradients_finite(parameters: list[Tensor]) -> bool:
    for p in parameters:
        if p.grad is not None:
            for v in p.grad.data:
                if not math.isfinite(v):
                    return False
    return True


def train_model(
    model: Model,
    dataset: Dataset,
    *,
    objective: str = "cross_entropy",
    optimiser: str = "adam",
    epochs: int = 10,
    learning_rate: float = 0.01,
    batch_size: int = 16,
    seed: int = 0,
) -> TrainingReport:
    if not isinstance(model, Model):
        raise TensorError("train_model expects a Model")
    if not isinstance(dataset, Dataset):
        raise TensorError("train_model expects a Dataset")
    if not isinstance(epochs, int) or epochs < 1:
        raise TensorError("epochs must be an integer >= 1")
    if not isinstance(batch_size, int) or batch_size < 1:
        raise TensorError("batch_size must be an integer >= 1")
    if not isinstance(learning_rate, (int, float)) or learning_rate <= 0:
        raise TensorError("learning_rate must be positive")
    if not isinstance(seed, int):
        raise TensorError("seed must be an integer")
    objective = objective.lower()
    optimiser = optimiser.lower()
    if objective not in ("cross_entropy", "mse"):
        raise TensorError(f"unknown objective '{objective}'")
    if len(dataset) == 0:
        raise TensorError("cannot train on an empty dataset")
    if dataset.feature_dim != model.input_shape[-1]:
        raise TensorError(
            f"dataset has {dataset.feature_dim} features but model expects {model.input_shape[-1]}"
        )
    if objective == "cross_entropy":
        if dataset.labels.rank == 2 and dataset.labels.shape[1] != model.output_shape[-1]:
            raise TensorError(
                f"dataset has {dataset.labels.shape[1]} classes but model outputs {model.output_shape[-1]}"
            )
    if objective == "mse" and dataset.labels.shape != (len(dataset), model.output_shape[-1]):
        if dataset.labels.shape != model.output_shape:
            raise TensorError("MSE requires labels shaped like model outputs")

    parameters = model.parameters()
    if not parameters:
        raise TensorError("model has no trainable parameters")
    optimizer = make_optimizer(optimiser, parameters, learning_rate)
    rng = RNG(seed)
    losses: list[float] = []
    accuracies: list[float] = []
    start_time = time.perf_counter()
    effective_batch = min(batch_size, len(dataset))

    for epoch in range(epochs):
        order = rng.permutation(len(dataset))
        epoch_loss = 0.0
        batches = 0
        for start in range(0, len(dataset), effective_batch):
            indices = order[start : start + effective_batch]
            features = select_rows(dataset.features, indices)
            labels = _batch_labels(dataset.labels, indices)
            logits = model.forward(features)
            loss = compute_loss(objective, logits, labels)
            loss_value = loss.item()
            if not math.isfinite(loss_value):
                raise TensorError(
                    f"non-finite loss {loss_value!r} at epoch {epoch + 1}, batch {batches + 1}; "
                    "training aborted rather than silently diverging"
                )
            loss.backward()
            if not _gradients_finite(parameters):
                raise TensorError(
                    f"non-finite gradient at epoch {epoch + 1}, batch {batches + 1}; training aborted"
                )
            optimizer.step()
            optimizer.zero_grad()
            epoch_loss += float(loss_value)
            batches += 1
        losses.append(epoch_loss / max(1, batches))
        if objective == "cross_entropy":
            try:
                accuracies.append(evaluate_accuracy(model, dataset))
            except TensorError:
                accuracies.append(0.0)
        else:
            accuracies.append(0.0)
    elapsed = time.perf_counter() - start_time

    final_loss = evaluate_loss(model, dataset, objective)
    final_accuracy = evaluate_accuracy(model, dataset) if objective == "cross_entropy" else None
    notes = [
        "Reference engine arithmetic is binary64; Float32 parameters are rounded at construction and serialization.",
        "Timing is wall-clock on the machine that ran the experiment and is not a cross-device benchmark.",
        "Determinism is guaranteed for a fixed seed on one platform; libm differences may change trailing bits.",
    ]
    return TrainingReport(
        objective=objective,
        optimiser=optimiser,
        epochs=epochs,
        learning_rate=float(learning_rate),
        batch_size=effective_batch,
        seed=seed,
        losses=losses,
        accuracies=accuracies,
        parameter_count=model.parameter_count,
        samples=len(dataset),
        elapsed_seconds=elapsed,
        dataset=dataset.metadata(),
        model_summary=model.summary(),
        notes=notes,
        final_loss=final_loss,
        final_accuracy=final_accuracy,
    )


def evaluate_accuracy(model: Model, dataset: Dataset) -> float:
    if len(dataset) == 0:
        raise TensorError("cannot evaluate an empty dataset")
    logits = model.forward(dataset.features)
    return accuracy_score(logits, dataset.labels)


def evaluate_loss(model: Model, dataset: Dataset, objective: str = "cross_entropy") -> float:
    if len(dataset) == 0:
        raise TensorError("cannot evaluate an empty dataset")
    logits = model.forward(dataset.features)
    return compute_loss(objective, logits, dataset.labels).item()


def loss_value(model: Model, dataset: Dataset, objective: str = "cross_entropy") -> float:
    return evaluate_loss(model, dataset, objective)
