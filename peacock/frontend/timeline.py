"""Keyframe timelines with numeric and perceptual-colour interpolation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .colour import Color
from .easing import ease


@dataclass(frozen=True)
class Keyframe:
    time: float
    value: object
    easing: str = "ease_in_out_cubic"


@dataclass
class Track:
    """A sorted keyframe track.

    The easing attached to a keyframe controls the segment that *ends* at that
    keyframe, matching CSS keyframe-animation semantics.
    """

    keyframes: list[Keyframe]
    loop: bool = False

    def __post_init__(self):
        if not self.keyframes:
            raise ValueError("a track requires at least one keyframe")
        self.keyframes = sorted(self.keyframes, key=lambda k: k.time)
        for i, k in enumerate(self.keyframes):
            if not math.isfinite(k.time):
                raise ValueError("keyframe times must be finite")
            if i and k.time == self.keyframes[i - 1].time:
                raise ValueError("keyframe times must be strictly increasing")
            if not isinstance(k.value, (int, float, Color)):
                raise ValueError("keyframe values must be numbers or Colors")

    @property
    def duration(self) -> float:
        return self.keyframes[-1].time

    def sample(self, time: float) -> object:
        if not math.isfinite(time):
            raise ValueError("sample time must be finite")
        start_t = self.keyframes[0].time
        end_t = self.keyframes[-1].time
        if self.loop and end_t > start_t:
            span = end_t - start_t
            time = start_t + ((time - start_t) % span)
        if time <= start_t:
            return self.keyframes[0].value
        if time >= end_t:
            return self.keyframes[-1].value
        for i in range(1, len(self.keyframes)):
            if time <= self.keyframes[i].time:
                a = self.keyframes[i - 1]
                b = self.keyframes[i]
                u = (time - a.time) / (b.time - a.time)
                return _interpolate(a.value, b.value, ease(b.easing, u))
        return self.keyframes[-1].value


def _interpolate(a, b, t: float):
    if isinstance(a, Color) or isinstance(b, Color):
        if not (isinstance(a, Color) and isinstance(b, Color)):
            raise ValueError("cannot interpolate between Color and numeric values")
        return a.mix(b, 0.0 if t < 0 else (1.0 if t > 1 else t), "oklab")
    return a + (b - a) * t


@dataclass
class Timeline:
    tracks: dict[str, Track] = field(default_factory=dict)

    def add(self, name: str, track: Track) -> None:
        if name in self.tracks:
            raise ValueError(f"track '{name}' already exists")
        self.tracks[name] = track

    @property
    def duration(self) -> float:
        return max((track.duration for track in self.tracks.values()), default=0.0)

    def sample(self, time: float) -> dict[str, object]:
        return {name: track.sample(time) for name, track in self.tracks.items()}
