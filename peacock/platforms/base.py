"""Platform-neutral frame and backend contracts."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass

from peacock.frontend.canvas import Canvas
from peacock.frontend.png import canvas_to_rgba8, encode_png


@dataclass
class Frame:
    """A rendered RGBA8 frame produced by a PEACOCK canvas."""

    canvas: Canvas
    sequence: int = 0

    @property
    def width(self) -> int:
        return self.canvas.width

    @property
    def height(self) -> int:
        return self.canvas.height

    def rgba8(self, tone_map: str = "clip") -> bytes:
        return canvas_to_rgba8(self.canvas, tone_map)

    def to_png(self, tone_map: str = "clip", compress_level: int = 6) -> bytes:
        return encode_png(self.canvas, tone_map, compress_level)

    def data_uri(self, tone_map: str = "clip") -> str:
        payload = base64.b64encode(self.to_png(tone_map)).decode("ascii")
        return f"data:image/png;base64,{payload}"


class Backend(ABC):
    """A host that can display or persist PEACOCK frames."""

    name = "backend"

    @abstractmethod
    def present(self, canvas: Canvas) -> Frame:
        """Accept a frame from the host application."""

    def close(self) -> None:  # pragma: no cover - optional hook
        """Release resources. The default implementation does nothing."""
