"""Small blocking HTTP/1.1 servers controlled synchronously by PEACOCK code."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import ipaddress
import json
import socket


MAX_HEADER_BYTES = 16_384
MAX_BODY_BYTES = 1_048_576


class ServerError(RuntimeError):
    pass


@dataclass(slots=True)
class PendingRequest:
    id: int
    method: str
    target: str
    headers: dict[str, str]
    body: str
    connection: socket.socket

    def record(self) -> list[str]:
        return [
            str(self.id), self.method, self.target,
            json.dumps(self.headers, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            self.body,
        ]


class BoundedHTTPServer:
    """One listening socket and at most one outstanding request.

    `accept()` is called by the VM and returns a text request record.  The VM
    must call `respond()` before accepting another request.  Connections are
    HTTP/1.1-close, which avoids async callbacks into a running VM frame.
    """

    def __init__(self, host: str, port: int):
        if host == "localhost":
            host = "127.0.0.1"
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ServerError("HTTP listen host must be a numeric IP address or localhost") from exc
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ServerError("HTTP listen port must be an integer from 0 to 65535")
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        self.socket = None
        self.pending: PendingRequest | None = None
        self._next_id = 1
        self.closed = False
        try:
            self.socket = socket.socket(family, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((host, port))
            self.socket.listen(16)
        except OSError as exc:
            self.close()
            raise ServerError(f"cannot listen on {host}:{port}: {exc}") from exc
        self.host, self.port = self.socket.getsockname()[:2]

    def _receive(self, connection: socket.socket, size: int) -> bytes:
        try:
            data = connection.recv(size)
        except socket.timeout as exc:
            raise ServerError("HTTP request read timed out") from exc
        except OSError as exc:
            raise ServerError(f"HTTP request read failed: {exc}") from exc
        if not data:
            raise ServerError("HTTP client closed before a complete request")
        return data

    def _read_request(self, connection: socket.socket) -> PendingRequest:
        connection.settimeout(5.0)
        data = bytearray()
        while b"\r\n\r\n" not in data:
            if len(data) >= MAX_HEADER_BYTES:
                raise ServerError("HTTP request headers exceed 16384 bytes")
            data.extend(self._receive(connection, min(4096, MAX_HEADER_BYTES + 4 - len(data))))
            if len(data) > MAX_HEADER_BYTES + 3:
                raise ServerError("HTTP request headers exceed 16384 bytes")
        header_data, body = bytes(data).split(b"\r\n\r\n", 1)
        if len(header_data) > MAX_HEADER_BYTES:
            raise ServerError("HTTP request headers exceed 16384 bytes")
        try:
            lines = header_data.decode("iso-8859-1").split("\r\n")
            method, target, version = lines[0].split(" ")
        except (ValueError, UnicodeError) as exc:
            raise ServerError("malformed HTTP request line") from exc
        if version != "HTTP/1.1" or method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            raise ServerError("only bounded HTTP/1.1 GET/HEAD/POST/PUT/PATCH/DELETE/OPTIONS requests are supported")
        if not target.startswith("/") or len(target) > 4096 or any(ord(character) < 32 for character in target):
            raise ServerError("HTTP request target must be an origin-form path of at most 4096 characters")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line or line[0] in " \t" or ":" not in line:
                raise ServerError("malformed or folded HTTP header")
            name, value = line.split(":", 1)
            name = name.lower()
            if not name or any(character not in "!#$%&'*+-.^_`|~0123456789abcdefghijklmnopqrstuvwxyz" for character in name):
                raise ServerError("invalid HTTP header name")
            value = value.strip(" \t")
            if len(value) > 8192:
                raise ServerError("HTTP header value exceeds 8192 characters")
            headers[name] = f"{headers[name]}, {value}" if name in headers else value
        if "transfer-encoding" in headers or "expect" in headers:
            raise ServerError("transfer-encoding and expect are not supported; use content-length")
        raw_length = headers.get("content-length", "0")
        if not raw_length or any(character not in "0123456789" for character in raw_length):
            raise ServerError("invalid HTTP content-length")
        length = int(raw_length)
        if not 0 <= length <= MAX_BODY_BYTES:
            raise ServerError("HTTP body length must be from 0 to 1048576 bytes")
        while len(body) < length:
            body += self._receive(connection, min(65536, length - len(body)))
        if len(body) != length:
            raise ServerError("HTTP request contained bytes beyond content-length; pipeline requests separately")
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ServerError("PEACOCK text HTTP requests require a UTF-8 body") from exc
        request = PendingRequest(self._next_id, method, target, headers, text, connection)
        self._next_id += 1
        return request

    def accept(self, timeout_ms: int) -> list[str] | None:
        if self.closed:
            raise ServerError("HTTP server is closed")
        if self.pending is not None:
            raise ServerError("respond to the outstanding HTTP request before accepting another")
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 0 <= timeout_ms <= 60_000:
            raise ServerError("HTTP accept timeout must be from 0 to 60000 ms")
        self.socket.settimeout(timeout_ms / 1000.0)
        try:
            connection, _address = self.socket.accept()
        except (socket.timeout, BlockingIOError):
            return None
        except OSError as exc:
            raise ServerError(f"HTTP accept failed: {exc}") from exc
        try:
            self.pending = self._read_request(connection)
            return self.pending.record()
        except Exception:
            connection.close()
            raise

    def respond(self, request_id: str, status: int, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
        request = self.pending
        if request is None or str(request.id) != request_id:
            raise ServerError("unknown or non-outstanding HTTP request id")
        if isinstance(status, bool) or not isinstance(status, int) or not 200 <= status <= 599:
            raise ServerError("HTTP response status must be an integer from 200 to 599")
        if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY_BYTES:
            raise ServerError("HTTP response body must be UTF-8 text of at most 1048576 bytes")
        if not isinstance(content_type, str) or not 1 <= len(content_type) <= 256 or any(character in "\r\n" for character in content_type):
            raise ServerError("invalid HTTP response content-type")
        payload = body.encode("utf-8")
        try:
            reason = HTTPStatus(status).phrase
        except ValueError:
            reason = "PEACOCK"
        headers = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(payload)}\r\n"
            "Cache-Control: no-store\r\n"
            "X-Content-Type-Options: nosniff\r\n"
            "Connection: close\r\n\r\n"
        ).encode("iso-8859-1")
        try:
            request.connection.sendall(headers + (b"" if request.method == "HEAD" else payload))
        except OSError as exc:
            raise ServerError(f"HTTP response failed: {exc}") from exc
        finally:
            request.connection.close()
            self.pending = None

    def close(self) -> None:
        self.closed = True
        if self.pending is not None:
            self.pending.connection.close()
            self.pending = None
        socket_object = getattr(self, "socket", None)
        if socket_object is not None:
            try:
                socket_object.close()
            finally:
                self.socket = None

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in str(self.host) else self.host
        return f"http://{host}:{self.port}/"


__all__ = ["BoundedHTTPServer", "MAX_BODY_BYTES", "MAX_HEADER_BYTES", "ServerError"]
