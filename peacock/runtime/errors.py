"""Runtime error types with source traces."""

from __future__ import annotations

from peacock.compiler.diagnostics import (
    CapabilityError,
    HostError,
    PeacockError,
    ResourceLimitError,
    RuntimeError_,
)

__all__ = [
    "RuntimeError_",
    "CapabilityError",
    "HostError",
    "ResourceLimitError",
    "VMFault",
    "PeacockError",
]


class VMFault(RuntimeError_):
    """A catchable PEACOCK runtime fault."""

    code = "PE4000"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message, code)
        self.trace: list[tuple[str, int, int]] = []


def add_trace(exc: PeacockError, function: str, line: int, column: int) -> None:
    if not hasattr(exc, "trace"):
        try:
            exc.trace = []  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - exotic exception types
            return
    trace = getattr(exc, "trace")
    trace.append((function, line, column))


def format_error(exc: PeacockError) -> str:
    lines = [f"{exc.code}: {exc.message}"]
    trace = getattr(exc, "trace", ())
    if trace:
        lines.append("stack trace (most recent call last):")
        for function, line, column in reversed(trace):
            lines.append(f"  at {function} (line {line}, column {column})")
    return "\n".join(lines)
