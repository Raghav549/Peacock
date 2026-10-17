"""PEACOCK model file format (``.pkm``) and int8 quantisation utilities.

Format v1 (little-endian):

    b"PEACOCKM"        8 bytes magic
    uint16             format version
    uint32             header length
    header JSON        canonical JSON, UTF-8
    parameter payload  concatenated float32 values
    digest             32-byte SHA-256 of (header JSON || payload)

The format is original. SHA-256 is used from the platform's cryptographic
library for integrity only; it is not a signature and provides no authenticity.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass

from .layers import Model, build_model
from .tensor import Tensor, TensorError

MODEL_MAGIC = b"PEACOCKM"
MODEL_VERSION = 1
MAX_HEADER_BYTES = 1_048_576
MAX_MODEL_BYTES = 256 * 1024 * 1024
MAX_PARAMETERS = 1_000_000


def _canonical_json(obj) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _collect_payload(model: Model) -> tuple[list[dict], bytes]:
    entries: list[dict] = []
    chunks: list[bytes] = []
    offset = 0
    named = model.named_parameters()
    if len(named) > MAX_PARAMETERS:
        raise TensorError("model has too many parameter tensors")
    for name, tensor in named:
        if tensor.dtype not in ("Float32", "Float64"):
            raise TensorError(f"cannot serialise non-float parameter '{name}'")
        count = tensor.size
        if count == 0:
            payload = b""
        else:
            payload = struct.pack(f"<{count}f", *[float(v) for v in tensor.data])
        entries.append(
            {
                "name": name,
                "shape": list(tensor.shape),
                "count": count,
                "offset": offset,
                "dtype": "Float32",
            }
        )
        chunks.append(payload)
        offset += len(payload)
    return entries, b"".join(chunks)


def model_to_bytes(model: Model, metadata: dict | None = None) -> bytes:
    if not isinstance(model, Model):
        raise TensorError("model_to_bytes expects a Model")
    entries, payload = _collect_payload(model)
    if len(payload) > MAX_MODEL_BYTES:
        raise TensorError("model payload exceeds the format limit")
    header = {
        "format": "peacock-model",
        "format_version": MODEL_VERSION,
        "language_version": "0.1",
        "architecture": model.architecture(),
        "parameters": entries,
        "payload_bytes": len(payload),
        "metadata": metadata or {},
    }
    header_bytes = _canonical_json(header)
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise TensorError("model header exceeds the format limit")
    digest = hashlib.sha256(header_bytes + payload).digest()
    return (
        MODEL_MAGIC
        + struct.pack("<H", MODEL_VERSION)
        + struct.pack("<I", len(header_bytes))
        + header_bytes
        + payload
        + digest
    )


def model_from_bytes(data: bytes) -> tuple[Model, dict]:
    if not isinstance(data, (bytes, bytearray)):
        raise TensorError("model data must be bytes")
    if len(data) > MAX_MODEL_BYTES + MAX_HEADER_BYTES + 64:
        raise TensorError("model file exceeds the format limit")
    if len(data) < 8 + 2 + 4 + 32:
        raise TensorError("file is too short to be a PEACOCK model")
    if data[:8] != MODEL_MAGIC:
        raise TensorError("not a PEACOCK model file (bad magic)")
    version = struct.unpack_from("<H", data, 8)[0]
    if version != MODEL_VERSION:
        raise TensorError(f"unsupported model format version {version}")
    header_len = struct.unpack_from("<I", data, 10)[0]
    if header_len <= 0 or header_len > MAX_HEADER_BYTES:
        raise TensorError("invalid model header length")
    start = 14
    header_end = start + header_len
    if header_end + 32 > len(data):
        raise TensorError("truncated model file")
    header_bytes = bytes(data[start:header_end])
    payload_end = len(data) - 32
    payload = bytes(data[header_end:payload_end])
    digest = bytes(data[payload_end:])
    if hashlib.sha256(header_bytes + payload).digest() != digest:
        raise TensorError("model integrity check failed (SHA-256 mismatch)")
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TensorError(f"invalid model header JSON: {exc}") from exc
    if not isinstance(header, dict) or header.get("format") != "peacock-model":
        raise TensorError("not a PEACOCK model header")
    if header.get("format_version") != MODEL_VERSION:
        raise TensorError("model header version mismatch")
    if header.get("payload_bytes") != len(payload):
        raise TensorError("model payload length does not match header")
    architecture = header.get("architecture")
    entries = header.get("parameters")
    if not isinstance(architecture, dict) or not isinstance(entries, list):
        raise TensorError("model header is missing architecture or parameters")
    try:
        model = build_model(
            architecture["input_shape"],
            architecture["output_shape"],
            architecture["layers"],
            seed=0,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TensorError(f"invalid model architecture: {exc}") from exc
    named = model.named_parameters()
    if len(named) != len(entries):
        raise TensorError("model parameter count does not match header")
    for (name, tensor), entry in zip(named, entries):
        if not isinstance(entry, dict):
            raise TensorError("malformed parameter entry")
        if entry.get("name") != name:
            raise TensorError(f"parameter name mismatch: expected '{name}'")
        if entry.get("shape") != list(tensor.shape) or entry.get("count") != tensor.size:
            raise TensorError(f"shape mismatch for parameter '{name}'")
        offset = entry.get("offset")
        count = entry.get("count")
        dtype = entry.get("dtype")
        if dtype != "Float32":
            raise TensorError(f"unsupported payload dtype for '{name}'")
        if not isinstance(offset, int) or not isinstance(count, int) or offset < 0 or count < 0:
            raise TensorError(f"invalid payload offset for '{name}'")
        if offset + count * 4 > len(payload):
            raise TensorError(f"parameter '{name}' exceeds payload bounds")
        values = struct.unpack_from(f"<{count}f", payload, offset)
        tensor.data = [float(v) for v in values]
        tensor.grad = None
        tensor.requires_grad = True
    return model, header.get("metadata", {})


def save_model(model: Model, path: str, metadata: dict | None = None) -> int:
    data = model_to_bytes(model, metadata)
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def load_model(path: str) -> Model:
    model, _ = load_model_with_metadata(path)
    return model


def load_model_with_metadata(path: str) -> tuple[Model, dict]:
    with open(path, "rb") as fh:
        data = fh.read(MAX_MODEL_BYTES + MAX_HEADER_BYTES + 64 + 1)
    if len(data) > MAX_MODEL_BYTES + MAX_HEADER_BYTES + 64:
        raise TensorError("model file exceeds the format limit")
    return model_from_bytes(data)


def model_fingerprint(model: Model, metadata: dict | None = None) -> str:
    data = model_to_bytes(model, metadata)
    return hashlib.sha256(data).hexdigest()


@dataclass
class QuantizedTensor:
    values: list[int]
    scale: float
    shape: tuple[int, ...]


def quantize_tensor(tensor: Tensor) -> QuantizedTensor:
    if tensor.size == 0:
        return QuantizedTensor([], 1.0, tensor.shape)
    max_abs = max(abs(v) for v in tensor.data)
    scale = (max_abs / 127.0) if max_abs > 0 else 1.0
    values = []
    for v in tensor.data:
        q = int(round(v / scale))
        values.append(max(-127, min(127, q)))
    return QuantizedTensor(values, scale, tensor.shape)


def dequantize_tensor(q: QuantizedTensor) -> Tensor:
    return Tensor([v * q.scale for v in q.values], q.shape, "Float32")


def quantization_report(model: Model) -> dict:
    original_bytes = 0
    quantized_bytes = 0
    max_abs_error = 0.0
    total_abs_error = 0.0
    count = 0
    per_parameter = {}
    for name, tensor in model.named_parameters():
        q = quantize_tensor(tensor)
        deq = dequantize_tensor(q)
        original_bytes += tensor.size * 4
        quantized_bytes += tensor.size + 8  # int8 values + scale/header allowance
        errors = [abs(tensor.data[i] - deq.data[i]) for i in range(tensor.size)]
        if errors:
            label = name.replace(".", "/")
            per_parameter[label] = {
                "scale": q.scale,
                "max_abs_error": max(errors),
                "mean_abs_error": sum(errors) / len(errors),
            }
            max_abs_error = max(max_abs_error, max(errors))
            total_abs_error += sum(errors)
            count += len(errors)
    return {
        "original_bytes": original_bytes,
        "quantized_bytes": quantized_bytes,
        "compression_ratio": (original_bytes / quantized_bytes) if quantized_bytes else 0.0,
        "max_abs_error": max_abs_error,
        "mean_abs_error": (total_abs_error / count) if count else 0.0,
        "per_parameter": per_parameter,
        "scheme": "symmetric per-tensor int8",
        "note": "Quantisation is implemented and measured; it is not yet wired into VM inference.",
    }
