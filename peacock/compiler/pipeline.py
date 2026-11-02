"""End-to-end compilation pipeline: source -> tokens -> AST -> types -> PIR -> bytecode.

The pipeline is pure with respect to the outside world (no file I/O) and returns
either a program image or structured diagnostics. Tooling and tests share it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bytecode import BytecodeError, BytecodeResult, compile_bytecode, verify_image
from .diagnostics import DiagnosticBag
from .ir import IRModule, IRVerificationError, build_ir, verify_ir
from .lexer import lex
from .optimizer import optimize
from .parser import parse
from .semantic import SemanticAnalyzer, TypedProgram
from peacock.sanskrit import SOURCE_EXTENSION


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
    semantic_mode: str = "python",
) -> CompileResult:
    if semantic_mode not in {"python", "shadow"}:
        raise ValueError("semantic_mode must be 'python' or 'shadow'")
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

    # Resolve user-file imports (उपयोग mylib;) before semantic analysis.
    # This keeps the Python bootstrap authoritative but enables genuine
    # multi-file PEACOCK programs and is the foundation for self-hosting
    # the compiler. Builtin namespaces (fs/net/ui etc.) are preserved;
    # file imports are merged flat (their top-level decls become available).
    try:
        _resolve_file_imports(module, path, result)
    except Exception as exc:
        raise InternalCompilerError(f"import resolution failed: {exc}") from exc
    if result.diagnostics.has_errors:
        result.stats["total_ms"] = (time.perf_counter() - start_total) * 1000.0
        return result

    t0 = time.perf_counter()
    file_mods = getattr(module, "file_modules", {})
    typed = SemanticAnalyzer(module, result.diagnostics, file_modules=file_mods).analyze()
    result.stats["semantic_ms"] = (time.perf_counter() - t0) * 1000.0
    result.typed = typed

    if semantic_mode == "shadow":
        # Run the PEACOCK-written semantic kernel against the annotations and
        # diagnostics produced by the bootstrap. It stays explicitly opt-in;
        # the Python analyser remains authoritative until broader parity gates
        # are met.
        from .selfhost_types import SelfHostTypeMismatch, shadow_check

        t0 = time.perf_counter()
        try:
            shadow_stats = shadow_check(module, typed)
            result.stats["selfhost_type_cases"] = shadow_stats["type_cases"]
            result.stats["selfhost_semantic_cases"] = shadow_stats["semantic_cases"]
            result.stats["selfhost_builtin_cases"] = shadow_stats["builtin_cases"]
        except SelfHostTypeMismatch as exc:
            raise InternalCompilerError(str(exc)) from exc
        result.stats["selfhost_shadow_ms"] = (time.perf_counter() - t0) * 1000.0
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


def _find_import_file(base_path: str, import_path: list[str]) -> Path | None:
    """Locate a file for `use a.b;` as a/b.सूत्र relative to base_path.

    Handles both internal (e.g. 'math') and surface (e.g. 'गणित') names
    for Devanagari file names, and supports dotted paths.
    """
    if base_path == "<source>" or not base_path:
        return None
    from peacock.sanskrit import surface as sans_surface

    base_dir = Path(base_path).parent
    # Build both internal and surface variants for robustness
    internal_rel = Path("/".join(import_path)).with_suffix(SOURCE_EXTENSION)
    # Surface variant: map each internal component to its Sanskrit surface if possible
    surface_parts = [sans_surface(p) for p in import_path]
    surface_rel = Path("/".join(surface_parts)).with_suffix(SOURCE_EXTENSION)
    candidates: list[Path | None] = [
        base_dir / internal_rel,
        base_dir / surface_rel,
        base_dir / (import_path[0] + SOURCE_EXTENSION) if len(import_path) == 1 else None,
        base_dir / (surface_parts[0] + SOURCE_EXTENSION) if len(import_path) == 1 else None,
        base_dir / "peacock_modules" / internal_rel,
        base_dir / "peacock_modules" / surface_rel,
        base_dir.parent / internal_rel if base_dir != Path(".") else None,
        base_dir.parent / surface_rel if base_dir != Path(".") else None,
    ]
    for cand in candidates:
        if cand is None:
            continue
        if cand.is_file():
            return cand
    return None


def _resolve_file_imports(module, base_path: str, result: CompileResult) -> None:
    """Merge file-based `use` imports into `module` in-place.

    Only `use` entries whose first component is not a known builtin namespace
    are considered file imports. For each such import we locate the .सूत्र file,
    lex/parse it, recursively resolve its own imports, and merge its top-level
    declarations. File imports are kept as valid uses for qualified
    `सहायक.वर्ग` calls, and also merged flat for unqualified calls.
    If the file cannot be found we keep the use so the existing diagnostic is
    preserved. Circular imports are detected via a visited set.
    """
    from . import builtins as B

    visited: set[str] = set()
    # file_modules maps short import name (e.g. 'सहायक' internal) -> imported Module
    if not hasattr(module, "file_modules"):
        module.file_modules = {}

    def _merge_import(imported_path: Path, parent_module, import_name: str) -> None:
        key = str(imported_path.resolve())
        if key in visited:
            result.diagnostics.error(
                "PE3001",
                f"circular import of '{imported_path}'",
                parent_module.span if hasattr(parent_module, "span") else None,
            )
            return
        visited.add(key)
        try:
            src = imported_path.read_text(encoding="utf-8")
        except OSError as exc:
            result.diagnostics.error("PE3006", f"cannot read import '{imported_path}': {exc}", parent_module.span if hasattr(parent_module, "span") else None)
            return
        toks, lex_diag = lex(src, str(imported_path))
        result.diagnostics.extend(lex_diag)
        if lex_diag.has_errors:
            return
        imported_mod, parse_diag = parse(toks, src, str(imported_path))
        result.diagnostics.extend(parse_diag)
        if parse_diag.has_errors:
            return
        # Recurse for nested imports first
        _resolve_file_imports_inner(imported_mod, str(imported_path), result, visited)
        # Record for qualified access (by short name, e.g. last component of dotted import)
        parent_module.file_modules[import_name] = imported_mod
        # Also propagate its file_modules for transitive qualified? (e.g. a imports b, b imports c)
        if hasattr(imported_mod, "file_modules"):
            for k, v in imported_mod.file_modules.items():
                if k not in parent_module.file_modules:
                    parent_module.file_modules[k] = v
        # Merge declarations flat for unqualified access, checking for collisions
        existing_funcs = {f.name for f in parent_module.functions}
        existing_structs = {s.name for s in parent_module.structs}
        existing_models = {m.name for m in parent_module.models}
        existing_trainings = {t.name for t in parent_module.trainings}
        for fn in imported_mod.functions:
            if fn.name in existing_funcs:
                result.diagnostics.error("PE3001", f"duplicate function '{fn.name}' from import '{imported_path}'", fn.name_span)
                continue
            parent_module.functions.append(fn)
            existing_funcs.add(fn.name)
        for st in imported_mod.structs:
            if st.name in existing_structs:
                result.diagnostics.error("PE3001", f"duplicate struct '{st.name}' from import '{imported_path}'", st.name_span)
                continue
            parent_module.structs.append(st)
            existing_structs.add(st.name)
        for m in imported_mod.models:
            if m.name in existing_models:
                result.diagnostics.error("PE3001", f"duplicate model '{m.name}' from import '{imported_path}'", m.name_span)
                continue
            parent_module.models.append(m)
        for tr in imported_mod.trainings:
            if tr.name in existing_trainings:
                result.diagnostics.error("PE3001", f"duplicate training '{tr.name}' from import '{imported_path}'", tr.name_span)
                continue
            parent_module.trainings.append(tr)
        # Merge builtin uses from imported module
        for u in imported_mod.uses:
            # Only propagate builtin uses; file uses are already resolved and kept as file_modules
            if u.path and u.path[0] in B.NAMESPACES and u not in parent_module.uses:
                parent_module.uses.append(u)

    def _resolve_file_imports_inner(mod, mod_path: str, res: CompileResult, seen: set[str]) -> None:
        if not hasattr(mod, "file_modules"):
            mod.file_modules = {}
        # Work on a snapshot so we can mutate mod.uses
        remaining = []
        for use in list(mod.uses):
            if not use.path:
                remaining.append(use)
                continue
            first = use.path[0]
            if first in B.NAMESPACES and len(use.path) == 1:
                remaining.append(use)
                continue
            # Attempt file import (handle dotted path, last component is short name)
            found = _find_import_file(mod_path, use.path)
            if found is None:
                # Keep for semantic error reporting (unknown module)
                remaining.append(use)
                continue
            # File found: keep the use as file-module namespace for qualified calls
            remaining.append(use)
            short_name = use.path[-1]
            _merge_import(found, mod, short_name)
            # Record successful file import for stats
            res.stats["modules_loaded"] = res.stats.get("modules_loaded", 0) + 1
        mod.uses = remaining

    _resolve_file_imports_inner(module, base_path, result, visited)


def parse_source(source: str, path: str = "<source>") -> tuple[Any, DiagnosticBag, list]:
    tokens, lex_diag = lex(source, path)
    if lex_diag.has_errors:
        return None, lex_diag, tokens
    module, parse_diag = parse(tokens, source, path)
    lex_diag.extend(parse_diag)
    return module, lex_diag, tokens
