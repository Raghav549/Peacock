"""End-to-end compilation pipeline: source -> tokens -> AST -> types -> PIR -> bytecode.

The pipeline is pure with respect to the outside world (no file I/O) and returns
either a program image or structured diagnostics. Tooling and tests share it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .bytecode import BytecodeError, BytecodeResult, compile_bytecode, verify_image
from .diagnostics import DiagnosticBag
from .ir import IRModule, IRVerificationError, build_ir, verify_ir
from .lexer import lex
from .optimizer import optimize
from .parser import parse
from .semantic import SemanticAnalyzer, TypedProgram


class InternalCompilerError(Exception):
    """Raised when a compiler invariant is violated. This is a bug, not a user error."""


@dataclass
class CompileResult:
    source: str
    path: str
    diagnostics: DiagnosticBag = field(default_factory=DiagnosticBag)
    tokens: list | None = None
    module: Any = None
    typed: TypedProgram | None = None
    ir: IRModule | None = None
    image: dict[str, Any] | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    optimize: bool = True

    @property
    def ok(self) -> bool:
        return not self.diagnostics.has_errors and self.image is not None


def compile_source(
    source: str,
    path: str = "<source>",
    *,
    optimize_ir: bool = True,
) -> CompileResult:
    result = CompileResult(source=source, path=path, optimize=optimize_ir)
    start_total = time.perf_counter()

    t0 = time.perf_counter()
    tokens, lex_diag = lex(source, path)
    result.stats["tokens"] = len(tokens) - 1
    result.stats["lex_ms"] = (time.perf_counter() - t0) * 1000.0
    result.diagnostics.extend(lex_diag)
    result.tokens = tokens
    if lex_diag.has_errors:
        result.stats["total_ms"] = (time.perf_counter() - start_total) * 1000.0
        return result

    t0 = time.perf_counter()
    module, parse_diag = parse(tokens, source, path)
    result.stats["parse_ms"] = (time.perf_counter() - t0) * 1000.0
    result.diagnostics.extend(parse_diag)
    result.module = module
    if parse_diag.has_errors:
        result.stats["total_ms"] = (time.perf_counter() - start_total) * 1000.0
        return result

    t0 = time.perf_counter()
    typed = SemanticAnalyzer(module, result.diagnostics).analyze()
    result.stats["semantic_ms"] = (time.perf_counter() - t0) * 1000.0
    result.typed = typed
    if result.diagnostics.has_errors:
        result.stats["total_ms"] = (time.perf_counter() - start_total) * 1000.0
        return result

    t0 = time.perf_counter()
    ir = build_ir(typed, source, path)
    result.stats["ir_ms"] = (time.perf_counter() - t0) * 1000.0
    try:
        verify_ir(ir)
        if optimize_ir:
            ir, opt_stats = optimize(ir)
            verify_ir(ir)
            result.stats["optimizer"] = opt_stats
        t0 = time.perf_counter()
        bc: BytecodeResult = compile_bytecode(ir)
        result.stats["bytecode_ms"] = (time.perf_counter() - t0) * 1000.0
        verify_image(bc.image)
    except (IRVerificationError, BytecodeError) as exc:
        raise InternalCompilerError(str(exc)) from exc
    result.ir = ir
    result.image = bc.image
    result.stats["instructions"] = bc.instruction_count
    result.stats["functions"] = len(ir.functions)
    result.stats["total_ms"] = (time.perf_counter() - start_total) * 1000.0
    return result


def parse_source(source: str, path: str = "<source>") -> tuple[Any, DiagnosticBag, list]:
    tokens, lex_diag = lex(source, path)
    if lex_diag.has_errors:
        return None, lex_diag, tokens
    module, parse_diag = parse(tokens, source, path)
    lex_diag.extend(parse_diag)
    return module, lex_diag, tokens
