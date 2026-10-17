"""Deterministic 2-D axis-aligned rigid-body physics for UI motion experiments.

Scope is deliberately narrow: AABBs, no rotation, impulse-based restitution and
positional correction. It is not a general-purpose physics engine. Simulation is
deterministic for a given initial state and fixed step sequence; no randomness is
used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

FIXED_DT = 1.0 / 120.0


@dataclass
class Body:
    x: float
    y: float
    width: float
    height: float
    vx: float = 0.0
    vy: float = 0.0
    mass: float = 1.0
    static: bool = False
    restitution: float = 0.2
    friction: float = 0.1

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("body dimensions must be positive")
        if not self.static and self.mass <= 0:
            raise ValueError("dynamic body mass must be positive")
        if not (0.0 <= self.restitution <= 1.0):
            raise ValueError("restitution must be in [0, 1]")

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height


class World:
    def __init__(
        self,
        width: float,
        height: float,
        gravity_x: float = 0.0,
        gravity_y: float = 900.0,
    ):
        if width <= 0 or height <= 0:
            raise ValueError("world dimensions must be positive")
        self.width = width
        self.height = height
        self.gravity_x = gravity_x
        self.gravity_y = gravity_y
        self.bodies: list[Body] = []
        self.time = 0.0
        self._accumulator = 0.0

    def add(self, body: Body) -> Body:
        self.bodies.append(body)
        return body

    def step(self, dt: float) -> None:
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be positive and finite")
        if dt > 0.25:
            raise ValueError("dt is too large for stable simulation (max 0.25s)")
        self._accumulator += dt
        while self._accumulator >= FIXED_DT:
            self._substep(FIXED_DT)
            self._accumulator -= FIXED_DT
            self.time += FIXED_DT

    def _substep(self, h: float) -> None:
        for body in self.bodies:
            if body.static:
                continue
            body.vx += self.gravity_x * h
            body.vy += self.gravity_y * h
            body.x += body.vx * h
            body.y += body.vy * h
        for body in self.bodies:
            if not body.static:
                self._walls(body)
        for i in range(len(self.bodies)):
            for j in range(i + 1, len(self.bodies)):
                a, b = self.bodies[i], self.bodies[j]
                if a.static and b.static:
                    continue
                self._collide(a, b)

    def _walls(self, body: Body) -> None:
        if body.left < 0:
            body.x = 0
            body.vx = -body.vx * body.restitution
            body.vy *= (1.0 - body.friction)
        elif body.right > self.width:
            body.x = self.width - body.width
            body.vx = -body.vx * body.restitution
            body.vy *= (1.0 - body.friction)
        if body.top < 0:
            body.y = 0
            body.vy = -body.vy * body.restitution
            body.vx *= (1.0 - body.friction)
        elif body.bottom > self.height:
            body.y = self.height - body.height
            body.vy = -body.vy * body.restitution
            body.vx *= (1.0 - body.friction)

    def _collide(self, a: Body, b: Body) -> None:
        overlap_x = min(a.right, b.right) - max(a.left, b.left)
        overlap_y = min(a.bottom, b.bottom) - max(a.top, b.top)
        if overlap_x <= 0 or overlap_y <= 0:
            return
        if overlap_x < overlap_y:
            normal_x, normal_y = (1.0 if a.x + a.width / 2 < b.x + b.width / 2 else -1.0), 0.0
            penetration = overlap_x
        else:
            normal_x, normal_y = 0.0, (1.0 if a.y + a.height / 2 < b.y + b.height / 2 else -1.0)
            penetration = overlap_y
        inv_a = 0.0 if a.static else 1.0 / a.mass
        inv_b = 0.0 if b.static else 1.0 / b.mass
        inv_total = inv_a + inv_b
        if inv_total == 0:
            return
        correction = penetration / inv_total * 0.8
        a.x -= normal_x * correction * inv_a
        a.y -= normal_y * correction * inv_a
        b.x += normal_x * correction * inv_b
        b.y += normal_y * correction * inv_b
        rvx = b.vx - a.vx
        rvy = b.vy - a.vy
        normal_velocity = rvx * normal_x + rvy * normal_y
        if normal_velocity > 0:
            return
        e = min(a.restitution, b.restitution)
        impulse = -(1.0 + e) * normal_velocity / inv_total
        impulse_x = impulse * normal_x
        impulse_y = impulse * normal_y
        if not a.static:
            a.vx -= impulse_x * inv_a
            a.vy -= impulse_y * inv_a
        if not b.static:
            b.vx += impulse_x * inv_b
            b.vy += impulse_y * inv_b
        # Tangential friction impulse (simple Coulomb approximation).
        tx, ty = -normal_y, normal_x
        tangent_velocity = rvx * tx + rvy * ty
        friction_impulse = -tangent_velocity / inv_total
        max_friction = impulse * min(a.friction, b.friction)
        friction_impulse = max(-max_friction, min(max_friction, friction_impulse))
        if not a.static:
            a.vx -= friction_impulse * tx * inv_a
            a.vy -= friction_impulse * ty * inv_a
        if not b.static:
            b.vx += friction_impulse * tx * inv_b
            b.vy += friction_impulse * ty * inv_b
