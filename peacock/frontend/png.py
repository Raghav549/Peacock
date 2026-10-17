"""PNG encoding and a small decoder for PEACOCK's test fixtures.

The PNG container, scanline filtering, chunk framing and CRC handling are
implemented here. DEFLATE compression is delegated to the platform's ``zlib``
(RFC 1950/1951); that dependency is documented in STATUS.md.

Determinism: pixel output is deterministic; compressed bytes may differ across
zlib versions.
"""

from __future__ import annotations

import struct
import zlib

from .canvas import Canvas
from .colour import Color, linear_to_srgb

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PNGError(ValueError):
    pass


def _clip01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _tone_map(v: float, mode: str) -> float:
    if mode == "clip":
        return _clip01(v)
    if mode == "reinhard":
        if v <= 0:
            return 0.0
        return _clip01(v / (1.0 + v))
    if mode == "aces":
        if v <= 0:
            return 0.0
        # Narkowicz 2015 ACES filmic approximation (documented approximation).
        x = v
        mapped = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)
        return _clip01(mapped)
    raise PNGError(f"unknown tone mapping mode '{mode}'")


def canvas_to_rgba8(canvas: Canvas, tone_map: str = "clip") -> bytes:
    out = bytearray(canvas.width * canvas.height * 4)
    data = canvas.data
    j = 0
    for i in range(0, len(data), 4):
        r, g, b, a = data[i], data[i + 1], data[i + 2], data[i + 3]
        if a > 1e-9:
            r /= a
            g /= a
            b /= a
        r = _tone_map(r, tone_map)
        g = _tone_map(g, tone_map)
        b = _tone_map(b, tone_map)
        out[j] = int(_clip01(linear_to_srgb(r)) * 255.0 + 0.5)
        out[j + 1] = int(_clip01(linear_to_srgb(g)) * 255.0 + 0.5)
        out[j + 2] = int(_clip01(linear_to_srgb(b)) * 255.0 + 0.5)
        out[j + 3] = int(_clip01(a) * 255.0 + 0.5)
        j += 4
    return bytes(out)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_png(canvas: Canvas, tone_map: str = "clip", compress_level: int = 6) -> bytes:
    rgba = canvas_to_rgba8(canvas, tone_map)
    width, height = canvas.width, canvas.height
    stride = width * 4
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)  # filter type 0 (None)
        scanlines.extend(rgba[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(scanlines), compress_level)
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )


def write_png(canvas: Canvas, path: str, tone_map: str = "clip") -> int:
    data = encode_png(canvas, tone_map)
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def decode_png(data: bytes) -> tuple[int, int, bytes]:
    """Decode PNGs produced by :func:`encode_png` (RGBA8, filter 0)."""
    if not isinstance(data, (bytes, bytearray)) or not data.startswith(PNG_SIGNATURE):
        raise PNGError("not a PNG file")
    pos = len(PNG_SIGNATURE)
    width = height = None
    idat = bytearray()
    saw_iend = False
    while pos + 8 <= len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        kind = bytes(data[pos + 4 : pos + 8])
        start = pos + 8
        end = start + length
        if end + 4 > len(data):
            raise PNGError("truncated PNG chunk")
        payload = bytes(data[start:end])
        crc = struct.unpack_from(">I", data, end)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise PNGError(f"CRC mismatch in {kind!r} chunk")
        pos = end + 4
        if kind == b"IHDR":
            if length != 13:
                raise PNGError("invalid IHDR length")
            width, height, depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if depth != 8 or color_type != 6 or compression != 0 or filter_method != 0 or interlace != 0:
                raise PNGError("only RGBA8 non-interlaced PNGs are supported")
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            saw_iend = True
            break
    if not saw_iend:
        raise PNGError("PNG is missing its IEND chunk (truncated file?)")
    if width is None or height is None:
        raise PNGError("PNG missing IHDR")
    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    expected = (stride + 1) * height
    if len(raw) != expected:
        raise PNGError(f"unexpected decompressed size {len(raw)} != {expected}")
    out = bytearray(width * height * 4)
    for y in range(height):
        row_start = y * (stride + 1)
        if raw[row_start] != 0:
            raise PNGError("only filter type 0 is supported")
        out[y * stride : (y + 1) * stride] = raw[row_start + 1 : row_start + 1 + stride]
    return width, height, bytes(out)
