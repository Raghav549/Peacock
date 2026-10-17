"""Source locations, diagnostics and diagnostic rendering.

Diagnostic codes are stable identifiers. The allocation is:

* ``PE1xxx`` — lexical analysis
* ``PE2xxx`` — syntax analysis
* ``PE3xxx`` — name resolution, types, static semantics (including capabilities)
* ``PE4xxx`` — runtime: type errors, capability denials, resource limits
* ``PE5xxx`` — artifacts, serialization, host I/O
* ``PE6xxx`` — intelligence engine (tensor shapes, data, training)
* ``PE7xxx`` — frontend engine (colour, rendering, layout)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"

    @property
    def is_error(self) -> bool:
        return self is Severity.ERROR


@dataclass(frozen=True, slots=True)
class Span:
    """A half-open byte range in a source file, with 1-based line/column start."""

    start: int
    end: int
    line: int
    column: int

    def merge(self, other: "Span") -> "Span":
        if other is None:
            return self
        start = min(self.start, other.start)
        end = max(self.end, other.end)
        # Keep the leading position.
        if other.start < self.start:
            return Span(start, end, other.line, other.column)
        return Span(start, end, self.line, self.column)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.line}:{self.column}"


NO_SPAN = Span(0, 0, 1, 1)


@dataclass(slots=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    span: Span = NO_SPAN
    hint: str | None = None
    notes: tuple[str, ...] = ()

    def render(self, source: str | None = None, color: bool = False) -> str:
        """Render a human-readable diagnostic, optionally with a source snippet."""
        tag = f"{self.code}: {self.severity.value}"
        if color:
            tag = f"\x1b[1;31m{tag}\x1b[0m" if self.severity is Severity.ERROR else (
                f"\x1b[1;33m{tag}\x1b[0m"
            )
        head = f"{tag}: {self.message}"
        lines = [head]
        if source is not None and self.span is not NO_SPAN:
            src_line = _source_line(source, self.span.line)
            if src_line is not None:
                gutter = str(self.span.line)
                lines.append(f"  --> line {gutter}, column {self.span.column}")
                lines.append(f"   | {src_line}")
                caret_pad = " " * max(0, self.span.column - 1)
                width = max(1, min(self.span.end - self.span.start, max(1, len(src_line) - self.span.column + 1)))
                lines.append(f"   | {caret_pad}{'^' * width}")
        if self.hint:
            lines.append(f"   = hint: {self.hint}")
        for note in self.notes:
            lines.append(f"   = note: {note}")
        return "\n".join(lines)


def _source_line(source: str, line_no: int) -> str | None:
    lines = source.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1]
    return None


@dataclass(slots=True)
class DiagnosticBag:
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def error(
        self,
        code: str,
        message: str,
        span: Span = NO_SPAN,
        hint: str | None = None,
        notes: Iterable[str] = (),
    ) -> Diagnostic:
        d = Diagnostic(code, Severity.ERROR, message, span, hint, tuple(notes))
        self.diagnostics.append(d)
        return d

    def warning(
        self,
        code: str,
        message: str,
        span: Span = NO_SPAN,
        hint: str | None = None,
    ) -> Diagnostic:
        d = Diagnostic(code, Severity.WARNING, message, span, hint)
        self.diagnostics.append(d)
        return d

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.diagnostics)

    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity is Severity.ERROR]

    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity is Severity.WARNING]

    def extend(self, other: "DiagnosticBag") -> None:
        self.diagnostics.extend(other.diagnostics)

    def __len__(self) -> int:
        return len(self.diagnostics)

    def __iter__(self):
        return iter(self.diagnostics)

    def render_all(self, source: str | None = None, color: bool = False) -> str:
        return "\n".join(d.render(source, color) for d in self.diagnostics)


class PeacockError(Exception):
    """Base class for all errors raised by PEACOCK tooling."""

    code = "PE0000"

    def __init__(self, message: str, code: str | None = None, span: Span = NO_SPAN):
        super().__init__(message)
        self.message = message
        self.code = code or type(self).code
        self.span = span

    def as_diagnostic(self) -> Diagnostic:
        return Diagnostic(self.code, Severity.ERROR, self.message, self.span)


class LexError(PeacockError):
    code = "PE1000"


class ParseError(PeacockError):
    code = "PE2000"


class SemanticError(PeacockError):
    code = "PE3000"


class RuntimeError_(PeacockError):
    """Runtime error that can be raised by the VM and caught by PEACOCK code."""

    code = "PE4000"


class CapabilityError(RuntimeError_):
    code = "PE4001"


class ResourceLimitError(RuntimeError_):
    code = "PE4003"


class PanicError(RuntimeError_):
    """An explicit panic. Unlike VMFault it cannot be caught by PEACOCK code."""

    code = "PE4011"


class ArtifactError(PeacockError):
    code = "PE5000"


class HostError(PeacockError):
    code = "PE5001"
