"""Interactive UI host with browser events delivered to a `UIBuilder` queue.

This is a development host, not an authenticated multi-tenant service.  It uses
only the standard library and relative browser URLs.  Static `UIBuilder.to_html`
remains script-free; scripts are injected only by this explicit interactive host.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import urlsplit

from peacock.frontend.ui import UIBuilder, UIError


_SCRIPT = r"""
(() => {
  'use strict';
  const post = async (kind, element, extra = {}) => {
    if (!element || element.getAttribute('aria-disabled') === 'true') return;
    const node = Number(element.dataset.node);
    try {
      await fetch('/event', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({kind, node, x: 0, y: 0, key: '', text: '', ...extra})
      });
    } catch (_) { /* the host may have closed after the program finished */ }
  };
  document.addEventListener('click', event => {
    const element = event.target.closest('[data-node]');
    if (!element) return;
    if (element.tagName === 'A') event.preventDefault();
    post('click', element);
  });
  document.addEventListener('keydown', event => {
    const element = event.target.closest('[data-node]');
    if (element) post('key', element, {key: event.key});
  });
  document.addEventListener('focusin', event => {
    const element = event.target.closest('[data-node]');
    if (element) post('focus', element);
  });
  const refresh = async () => {
    if (document.hidden) return;
    try {
      const response = await fetch('/fragment', {cache: 'no-store'});
      if (!response.ok) return;
      const html = await response.text();
      const current = document.querySelector('.peacock-ui');
      if (current && current.outerHTML !== html) current.outerHTML = html;
    } catch (_) { /* host shutdown is normal */ }
  };
  setInterval(refresh, 400);
})();
""".strip()


class UIWebBackend:
    """Lazily start an HTTP host when a program first presents a UI."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, title: str = "PEACOCK UI"):
        self.host, self.port, self.title = host, port, title
        self.ui: UIBuilder | None = None
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.present_count = 0

    @property
    def url(self) -> str:
        port = self.server.server_address[1] if self.server is not None else self.port
        display_host = "127.0.0.1" if self.host in {"0.0.0.0", "::"} else self.host
        return f"http://{display_host}:{port}/"

    def present(self, ui: UIBuilder) -> None:
        if not isinstance(ui, UIBuilder):
            raise TypeError("UIWebBackend requires a UIBuilder")
        if self.server is None:
            self.ui = ui
            backend = self

            class Handler(_UIHandler):
                owner = backend

            self.server = ThreadingHTTPServer((self.host, self.port), Handler)
            self.server.daemon_threads = True
            self.thread = threading.Thread(target=self.server.serve_forever, name="peacock-ui", daemon=True)
            self.thread.start()
        elif self.ui is not ui:
            raise UIError("one UIWebBackend cannot present multiple UI documents")
        self.present_count += 1
        ui.present()

    def close(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None


class _UIHandler(BaseHTTPRequestHandler):
    owner: UIWebBackend
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *args) -> None:
        return

    def _send(self, status: int, content_type: str, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, value: dict) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(value, separators=(",", ":")).encode())

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        path = urlsplit(self.path).path
        ui = self.owner.ui
        if ui is None:
            self._json(503, {"ok": False, "error": "UI is not ready"})
            return
        if path == "/":
            html = ui.to_html().replace("</body>", f"<script>{_SCRIPT}</script></body>")
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
        elif path == "/fragment":
            self._send(200, "text/html; charset=utf-8", ui.to_fragment().encode("utf-8"))
        elif path == "/healthz":
            self._json(200, {"ok": True, "revision": ui.revision, "pending": ui.pending_events()})
        elif path == "/manifest.json":
            self._json(200, {"title": self.owner.title, "revision": ui.revision, "presents": self.owner.present_count})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if urlsplit(self.path).path != "/event":
            self._json(404, {"ok": False, "error": "not found"})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"ok": False, "error": "application/json required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16_384:
                raise ValueError("event body must be 1..16384 bytes")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict) or set(payload) - {"kind", "node", "x", "y", "key", "text"}:
                raise ValueError("unknown event fields")
            event_id = self.owner.ui.post_event(
                payload.get("kind"), payload.get("node", -1), payload.get("x", 0.0),
                payload.get("y", 0.0), payload.get("key", ""), payload.get("text", ""),
            )
            self._json(202, {"ok": True, "id": event_id})
        except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError, UIError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})
