"""Static web backend: writes PNG frames plus a dependency-free HTML viewer.

The browser is used strictly as a documented presentation boundary. No
JavaScript runtime, framework or asset is required: the viewer is a static HTML
document that displays the latest frame.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from peacock.frontend.canvas import Canvas

from .base import Backend, Frame

_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; background: #0b1020; color: #e8ecf8;
         font: 16px/1.5 system-ui, sans-serif; display: grid; place-items: center; min-height: 100vh; }}
  main {{ padding: 24px; text-align: center; }}
  img {{ max-width: 92vw; border-radius: 16px; box-shadow: 0 20px 60px #0009; image-rendering: auto; }}
  p {{ opacity: 0.7; margin: 12px 0 0; }}
</style>
</head>
<body>
<main>
  <img src="latest.png" width="{width}" height="{height}" alt="PEACOCK rendered frame">
  <p>{title} — frame {sequence} — {width}x{height} — PEACOCK reference renderer</p>
</main>
</body>
</html>
"""


class WebBackend(Backend):
    name = "web"

    def __init__(self, output_dir: str | os.PathLike, title: str = "PEACOCK preview"):
        self.output_dir = Path(output_dir)
        self.title = title
        self.frames_dir = self.output_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.frames: list[dict] = []
        self.frame_count = 0
        self.index_path = self.output_dir / "index.html"

    def present(self, canvas: Canvas) -> Frame:
        frame = Frame(canvas, self.frame_count)
        self.frame_count += 1
        png = frame.to_png()
        name = f"frame_{frame.sequence:04d}.png"
        (self.frames_dir / name).write_bytes(png)
        (self.output_dir / "latest.png").write_bytes(png)
        self.frames.append(
            {"sequence": frame.sequence, "width": frame.width, "height": frame.height, "file": f"frames/{name}"}
        )
        self.index_path.write_text(
            _HTML.format(
                title=self.title,
                width=frame.width,
                height=frame.height,
                sequence=frame.sequence,
            ),
            encoding="utf-8",
        )
        return frame

    def manifest(self) -> dict:
        return {
            "format": "peacock-web-frames",
            "version": 1,
            "title": self.title,
            "frames": list(self.frames),
        }

    def close(self) -> None:
        (self.output_dir / "manifest.json").write_text(
            json.dumps(self.manifest(), indent=2) + "\n", encoding="utf-8"
        )
