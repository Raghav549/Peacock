"""Deterministic pseudo-random number generator.

Original implementation of the public-domain xoshiro256** algorithm by Blackman
and Vigna, seeded with SplitMix64. Algorithms are public knowledge; this code is
an independent implementation. Determinism is guaranteed for a given seed across
platforms for integer output; floating-point transforms are deterministic on a
single platform and may differ in the last bit across libm implementations.
"""

from __future__ import annotations

import math
from typing import Sequence

_MASK = (1 << 64) - 1


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (64 - k))) & _MASK


class RNG:
    def __init__(self, seed: int = 0):
        if not isinstance(seed, int):
            raise TypeError("seed must be an int")
        self._state = [0, 0, 0, 0]
        self._seed_splitmix(seed & _MASK)

    def _seed_splitmix(self, seed: int) -> None:
        state = seed
        for i in range(4):
            state = (state + 0x9E3779B97F4A7C15) & _MASK
            z = state
            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
            self._state[i] = z ^ (z >> 31)

    def next_u64(self) -> int:
        s = self._state
        result = (_rotl((s[1] * 5) & _MASK, 7) * 9) & _MASK
        t = (s[1] << 17) & _MASK
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = _rotl(s[3], 45)
        return result

    def next_float(self) -> float:
        """Uniform float in [0, 1)."""
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def uniform(self, low: float, high: float) -> float:
        if not high >= low:
            raise ValueError("uniform requires high >= low")
        return low + (high - low) * self.next_float()

    def randint(self, low: int, high: int) -> int:
        """Uniform integer in [low, high)."""
        if high <= low:
            raise ValueError("randint requires high > low")
        span = high - low
        limit = (1 << 64) - ((1 << 64) % span)
        while True:
            x = self.next_u64()
            if x < limit:
                return low + x % span

    def normal(self, mean: float = 0.0, std: float = 1.0) -> float:
        """Box–Muller transform."""
        u1 = max(self.next_float(), 1e-300)
        u2 = self.next_float()
        return mean + std * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def shuffle(self, values: list) -> None:
        """In-place Fisher–Yates shuffle."""
        for i in range(len(values) - 1, 0, -1):
            j = self.randint(0, i + 1)
            values[i], values[j] = values[j], values[i]

    def permutation(self, n: int) -> list[int]:
        values = list(range(n))
        self.shuffle(values)
        return values

    def state(self) -> tuple[int, int, int, int]:
        return tuple(self._state)  # type: ignore[return-value]

    def __repr__(self) -> str:  # pragma: no cover
        return f"RNG(state={self._state})"


def deterministic_samples(seed: int, count: int) -> list[float]:
    rng = RNG(seed)
    return [rng.next_float() for _ in range(count)]
