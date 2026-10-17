"""Shared helpers for the PEACOCK test suite."""

from __future__ import annotations

import io
from pathlib import Path

from peacock.compiler.diagnostics import DiagnosticBag
from peacock.compiler.pipeline import CompileResult, compile_source
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM

REPO_ROOT = Path(__file__).resolve().parent.parent


def compile_ok(source: str, path: str = "test.pac") -> CompileResult:
    result = compile_source(source, path)
    if not result.ok:
        raise AssertionError(
            "expected successful compilation but got:\n"
            + result.diagnostics.render_all(source)
        )
    return result


def compile_errors(source: str, path: str = "test.pac") -> list:
    result = compile_source(source, path)
    if result.ok:
        raise AssertionError("expected compilation to fail, but it succeeded")
    return result.diagnostics.errors()


def expect_diagnostic(source: str, code: str, contains: str | None = None):
    errors = compile_errors(source)
    matching = [d for d in errors if d.code == code]
    if not matching:
        rendered = "\n".join(f"{d.code}: {d.message}" for d in errors)
        raise AssertionError(f"expected diagnostic {code}, got:\n{rendered}")
    if contains is not None and not any(contains in d.message for d in matching):
        raise AssertionError(
            f"expected {code} containing {contains!r}, got "
            + "; ".join(d.message for d in matching)
        )
    return matching[0]


def run_source(
    source: str,
    grants: tuple[str, ...] = (),
    argv: tuple[str, ...] = (),
    root: str | Path | None = None,
    max_steps: int = 2_000_000,
) -> tuple[str, object, VM]:
    result = compile_ok(source)
    stdout = io.StringIO()
    policy = HostPolicy(
        grants=frozenset(grants),
        root=str(root if root is not None else REPO_ROOT),
        max_steps=max_steps,
    )
    vm = VM(result.image, policy, stdout=stdout, argv=list(argv))
    outcome = vm.run()
    return stdout.getvalue(), outcome, vm


def example_path(name: str) -> Path:
    return REPO_ROOT / "examples" / name


def read_example(name: str) -> str:
    return example_path(name).read_text(encoding="utf-8")


def run_example(
    name: str,
    grants: tuple[str, ...] = (),
    argv: tuple[str, ...] = (),
    max_steps: int = 2_000_000,
) -> tuple[str, object, VM, CompileResult]:
    source = read_example(name)
    result = compile_source(source, str(example_path(name)))
    if not result.ok:
        raise AssertionError(result.diagnostics.render_all(source))
    stdout = io.StringIO()
    policy = HostPolicy(grants=frozenset(grants), root=str(REPO_ROOT), max_steps=max_steps)
    vm = VM(result.image, policy, stdout=stdout, argv=list(argv))
    outcome = vm.run()
    return stdout.getvalue(), outcome, vm, result


def all_diagnostics(source: str) -> DiagnosticBag:
    result = compile_source(source, "test.pac")
    return result.diagnostics
