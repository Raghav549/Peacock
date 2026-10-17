"""PEACOCK Intelligence Engine — tensors, autodiff, neural networks, training.

Implemented from scratch in pure Python. The only external boundary used is the
platform's scalar ``libm`` (accessed through :mod:`math`) for transcendental
functions. See ``docs/ai-engine/README.md``.
"""

from .tensor import Tensor, TensorError
from .datasets import Dataset, xor_dataset, spiral_dataset
from .layers import Dense, Sequential, Model, build_model
from .training import TrainingReport, train_model, evaluate_accuracy, loss_value
from .random import RNG

__all__ = [
    "Tensor",
    "TensorError",
    "Dataset",
    "xor_dataset",
    "spiral_dataset",
    "Dense",
    "Sequential",
    "Model",
    "build_model",
    "TrainingReport",
    "train_model",
    "evaluate_accuracy",
    "loss_value",
    "RNG",
]
