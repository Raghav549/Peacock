"""Optimisers implemented from scratch.

Updates are performed in place on parameter tensors; the autodiff graph is
never extended by an optimiser step.
"""

from __future__ import annotations

import math

from .tensor import Tensor, TensorError


class Optimizer:
    def __init__(self, parameters: list[Tensor], learning_rate: float):
        if not parameters:
            raise TensorError("optimiser requires at least one parameter")
        if not isinstance(learning_rate, (int, float)) or learning_rate <= 0:
            raise TensorError("learning_rate must be positive")
        self.parameters = parameters
        self.learning_rate = float(learning_rate)
        self.step_count = 0

    def zero_grad(self) -> None:
        for p in self.parameters:
            p.zero_grad()

    def step(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class SGD(Optimizer):
    def __init__(self, parameters, learning_rate: float = 0.01, momentum: float = 0.0):
        super().__init__(parameters, learning_rate)
        if not (0.0 <= momentum < 1.0):
            raise TensorError("momentum must be in [0, 1)")
        self.momentum = momentum
        self._velocity = [[0.0] * p.size for p in self.parameters]

    def step(self) -> None:
        self.step_count += 1
        for p, velocity in zip(self.parameters, self._velocity):
            if p.grad is None:
                continue
            grad = p.grad.data
            for i in range(p.size):
                if self.momentum:
                    velocity[i] = self.momentum * velocity[i] + grad[i]
                    update = velocity[i]
                else:
                    update = grad[i]
                p.data[i] -= self.learning_rate * update


class Adam(Optimizer):
    def __init__(
        self,
        parameters,
        learning_rate: float = 0.001,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ):
        super().__init__(parameters, learning_rate)
        if not (0.0 <= beta1 < 1.0 and 0.0 <= beta2 < 1.0):
            raise TensorError("Adam beta values must be in [0, 1)")
        if epsilon <= 0:
            raise TensorError("Adam epsilon must be positive")
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self._m = [[0.0] * p.size for p in self.parameters]
        self._v = [[0.0] * p.size for p in self.parameters]

    def step(self) -> None:
        self.step_count += 1
        t = self.step_count
        bias1 = 1.0 - self.beta1**t
        bias2 = 1.0 - self.beta2**t
        for p, m, v in zip(self.parameters, self._m, self._v):
            if p.grad is None:
                continue
            grad = p.grad.data
            for i in range(p.size):
                g = grad[i]
                m[i] = self.beta1 * m[i] + (1.0 - self.beta1) * g
                v[i] = self.beta2 * v[i] + (1.0 - self.beta2) * g * g
                m_hat = m[i] / bias1
                v_hat = v[i] / bias2
                p.data[i] -= self.learning_rate * m_hat / (math.sqrt(v_hat) + self.epsilon)


def make_optimizer(name: str, parameters: list[Tensor], learning_rate: float) -> Optimizer:
    name = name.lower()
    if name == "sgd":
        return SGD(parameters, learning_rate)
    if name == "adam":
        return Adam(parameters, learning_rate)
    raise TensorError(f"unknown optimiser '{name}' (supported: sgd, adam)")
