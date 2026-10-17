"""Evaluation metrics with explicit definitions and no hidden averaging."""

from __future__ import annotations

from dataclasses import dataclass, field

from .datasets import labels_as_indices
from .tensor import Tensor, TensorError, argmax_last


def accuracy_score(logits: Tensor, labels: Tensor) -> float:
    if logits.rank != 2:
        raise TensorError("accuracy_score expects logits of shape [samples, classes]")
    if logits.shape[0] != labels.shape[0]:
        raise TensorError("logits and labels have different sample counts")
    predictions = argmax_last(logits)
    targets = labels_as_indices(labels)
    if len(predictions) != len(targets):
        raise TensorError("prediction and label counts differ")
    if not targets:
        raise TensorError("cannot evaluate an empty dataset")
    correct = sum(1 for p, t in zip(predictions, targets) if p == t)
    return correct / len(targets)


def confusion_matrix(logits: Tensor, labels: Tensor, num_classes: int | None = None) -> list[list[int]]:
    predictions = argmax_last(logits)
    targets = labels_as_indices(labels)
    if num_classes is None:
        num_classes = max(max(predictions, default=0), max(targets, default=0)) + 1
    if num_classes <= 0:
        raise TensorError("num_classes must be positive")
    matrix = [[0] * num_classes for _ in range(num_classes)]
    for p, t in zip(predictions, targets):
        if not (0 <= p < num_classes and 0 <= t < num_classes):
            raise TensorError("class index out of range for confusion matrix")
        matrix[t][p] += 1
    return matrix


def classification_report(logits: Tensor, labels: Tensor) -> dict:
    predictions = argmax_last(logits)
    targets = labels_as_indices(labels)
    if not targets:
        raise TensorError("cannot evaluate an empty dataset")
    classes = sorted(set(targets) | set(predictions))
    matrix = confusion_matrix(logits, labels, (max(classes) + 1) if classes else 0)
    per_class = {}
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[r][c] for r in range(len(matrix)) if r != c)
        fn = sum(matrix[c][j] for j in range(len(matrix)) if j != c)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        per_class[str(c)] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for t in targets if t == c),
        }
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(per_class) if per_class else 0.0
    return {
        "accuracy": sum(1 for p, t in zip(predictions, targets) if p == t) / len(targets),
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "samples": len(targets),
    }


def evaluate_model(model, dataset) -> dict:
    """Full-batch evaluation. Returns accuracy and (for classification) a report."""
    features = dataset.features
    logits = model.forward(features)
    accuracy = accuracy_score(logits, dataset.labels)
    return {
        "accuracy": accuracy,
        "samples": len(dataset),
        "report": classification_report(logits, dataset.labels),
    }
