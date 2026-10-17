"""Deterministic binary container for PEACOCK bytecode program images.

Layout (little-endian):

    b"PEACOCK\\x1a"     8 bytes
    uint16              format version (1)
    uint16              flags (0)
    uint32              payload length
    payload             canonical JSON bytecode image
    digest              32-byte SHA-256 of the payload

The format is original. SHA-256 provides integrity, not authenticity.
"""

from __future__ import annotations

import hashlib
import json
import struct

from peacock.compiler.bytecode import verify_image

ARTIFACT_MAGIC = b"PEACOCK\x1a"
ARTIFACT_VERSION = 1
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


class ArtifactFormatError(ValueError):
    pass


def _canonical(image: dict) -> bytes:
    return json.dumps(
        image, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def image_to_bytes(image: dict) -> bytes:
    payload = _canonical(image)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ArtifactFormatError("bytecode image exceeds the artifact size limit")
    digest = hashlib.sha256(payload).digest()
    return (
        ARTIFACT_MAGIC
        + struct.pack("<HHI", ARTIFACT_VERSION, 0, len(payload))
        + payload
        + digest
    )


def image_from_bytes(data: bytes) -> dict:
    if not isinstance(data, (bytes, bytearray)):
        raise ArtifactFormatError("artifact data must be bytes")
    if len(data) > MAX_ARTIFACT_BYTES + 64:
        raise ArtifactFormatError("artifact exceeds the size limit")
    if len(data) < 16 + 32 or bytes(data[:8]) != ARTIFACT_MAGIC:
        raise ArtifactFormatError("not a PEACOCK bytecode artifact")
    version, flags, length = struct.unpack_from("<HHI", data, 8)
    if version != ARTIFACT_VERSION:
        raise ArtifactFormatError(f"unsupported artifact version {version}")
    if flags != 0:
        raise ArtifactFormatError("unsupported artifact flags")
    start = 16
    end = start + length
    if end + 32 != len(data):
        raise ArtifactFormatError("artifact length does not match header")
    payload = bytes(data[start:end])
    digest = bytes(data[end:])
    if hashlib.sha256(payload).digest() != digest:
        raise ArtifactFormatError("artifact integrity check failed (SHA-256 mismatch)")
    try:
        image = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactFormatError(f"invalid artifact JSON: {exc}") from exc
    if not isinstance(image, dict):
        raise ArtifactFormatError("artifact payload is not an object")
    verify_image(image)
    return image


def save_image(image: dict, path: str) -> int:
    data = image_to_bytes(image)
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def load_image(path: str) -> dict:
    with open(path, "rb") as fh:
        data = fh.read(MAX_ARTIFACT_BYTES + 65)
    return image_from_bytes(data)


def artifact_fingerprint(image: dict) -> str:
    return hashlib.sha256(image_to_bytes(image)).hexdigest()
