"""Headless backend: keep the latest frame and optionally write PNG files."""

from __future__ import annotations

import os
from pathlib import Path

from peacock.frontend.canvas import Canvas

from .base import Backend, Frame


class HeadlessBackend(Backend):
    name = "headless"

    def __init__(self, output_dir: str | os.PathLike | None = None, write_every_frame: bool = True):
        self.output_dir = Path(output_dir) if output_dir is not None else None
        self.write_every_frame = write_every_frame
        self.last_frame: Frame | None = None
        self.frame_count = 0
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def present(self, canvas: Canvas) -> Frame:
        frame = Frame(canvas, self.frame_count)
        self.last_frame = frame
        self.frame_count += 1
        if self.output_dir is not None and (self.write_every_frame or self.frame_count == 1):
            (self.output_dir / f"frame_{frame.sequence:04d}.png").write_bytes(frame.to_png())
        return frame

    def close(self) -> None:
        self.last_frame = None
