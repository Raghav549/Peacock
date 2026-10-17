"""Spring dynamics: a damped harmonic oscillator integrated with explicit substeps.

This is a numerical simulation, not a closed-form solution. Substeps keep the
integration stable for UI-sized time steps; tests assert convergence, finiteness
and bounded overshoot for a range of configurations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MAX_SUBSTEP = 1.0 / 240.0


@dataclass(frozen=True)
class SpringConfig:
    stiffness: float = 170.0
    damping: float = 26.0
    mass: float = 1.0

    def __post_init__(self):
        if not math.isfinite(self.stiffness) or self.stiffness <= 0:
            raise ValueError("spring stiffness must be positive and finite")
        if not math.isfinite(self.damping) or self.damping <= 0:
            raise ValueError("spring damping must be positive and finite")
        if not math.isfinite(self.mass) or self.mass <= 0:
            raise ValueError("spring mass must be positive and finite")


def step_spring(
    position: float,
    velocity: float,
    target: float,
    config: SpringConfig,
    dt: float,
) -> tuple[float, float]:
    if not all(math.isfinite(v) for v in (position, velocity, target, dt)):
        raise ValueError("spring inputs must be finite")
    if dt <= 0:
        raise ValueError("spring dt must be positive")
    substeps = min(64, max(1, int(math.ceil(dt / MAX_SUBSTEP))))
    h = dt / substeps
    pos = position
    vel = velocity
    for _ in range(substeps):
        accel = (config.stiffness * (target - pos) - config.damping * vel) / config.mass
        vel += accel * h
        pos += vel * h
    return pos, vel


def settle(
    start: float,
    target: float,
    config: SpringConfig,
    steps: int,
    dt: float = 1.0 / 60.0,
) -> list[float]:
    if not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be a non-negative integer")
    values = [start]
    position, velocity = start, 0.0
    for _ in range(steps):
        position, velocity = step_spring(position, velocity, target, config, dt)
        values.append(position)
    return values


def is_settled(position: float, target: float, velocity: float, tolerance: float = 1e-3) -> bool:
    return abs(target - position) <= tolerance and abs(velocity) <= tolerance
