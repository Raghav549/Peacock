"""A small stdlib HTTP host that serves the most recent frame.

Routes:
    GET /               HTML viewer
    GET /frame.png      latest PNG frame
    GET /manifest.json  frame metadata
    GET /healthz        liveness probe

The server is a host boundary, not part of the language. Bind to 127.0.0.1 by
default; pass host="0.0.0.0" when running inside a container preview.
"""

from __future__ import annotations

import json
import threading
from http import server as http_server
from typing import Optional

from peacock.frontend.canvas import Canvas

from .base import Backend, Frame
from .web import _HTML


class _Handler(http_server.BaseHTTPRequestHandler):
    server_version = "PeacockHost/0.1"

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        if getattr(self.server, "quiet", True):
            return
        super().log_message(format, *args)

    def _send(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802 - stdlib naming
        host: "ServerBackend" = self.server.peacock  # type: ignore[attr-defined]
        if self.path == "/healthz":
            self._send(200, "text/plain; charset=utf-8", b"ok\n")
        elif self.path == "/manifest.json":
            payload = json.dumps(host.manifest(), indent=2).encode("utf-8") + b"\n"
            self._send(200, "application/json", payload)
        elif self.path == "/frame.png":
            frame = host.last_frame
            if frame is None:
                self._send(404, "text/plain; charset=utf-8", b"no frame presented yet\n")
            else:
                self._send(200, "image/png", frame.to_png())
        elif self.path in ("/", "/index.html"):
            frame = host.last_frame
            if frame is None:
                self._send(503, "text/plain; charset=utf-8", b"no frame presented yet\n")
                return
            html = _HTML.format(
                title=host.title,
                width=frame.width,
                height=frame.height,
                sequence=frame.sequence,
            ).encode("utf-8")
            self._send(200, "text/html; charset=utf-8", html)
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found\n")


class ServerBackend(Backend):
    name = "server"

    def __init__(self, host: str = "127.0.0.1", port: int = 0, title: str = "PEACOCK host"):
        self.host = host
        self.port = port
        self.title = title
        self.last_frame: Optional[Frame] = None
        self.frame_count = 0
        self._httpd: http_server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def present(self, canvas: Canvas) -> Frame:
        frame = Frame(canvas, self.frame_count)
        self.frame_count += 1
        self.last_frame = frame
        return frame

    def manifest(self) -> dict:
        frame = self.last_frame
        return {
            "format": "peacock-server-frame",
            "version": 1,
            "frames_presented": self.frame_count,
            "latest": None
            if frame is None
            else {"sequence": frame.sequence, "width": frame.width, "height": frame.height},
        }

    @property
    def url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("server has not been started")
        return f"http://{self.host}:{self._httpd.server_address[1]}/"

    def start(self) -> "ServerBackend":
        if self._httpd is not None:
            return self
        self._httpd = http_server.ThreadingHTTPServer((self.host, self.port), _Handler)
        self._httpd.peacock = self  # type: ignore[attr-defined]
        self._httpd.quiet = True  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def close(self) -> None:
        self.stop()

    def __enter__(self) -> "ServerBackend":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
