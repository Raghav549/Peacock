"""Command-line interface for the PEACOCK bootstrap toolchain.

Canonical source extension: ``.सूत्र``. Compiled program artifact: ``.बीज``.

Exit codes:
    0  success
    1  compilation diagnostics (errors)
    2  usage error
    3  runtime error
    4  internal compiler error (a bug)
    5  fuzzing found a crash
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import sys
import time
from pathlib import Path

from peacock import LANGUAGE_VERSION, __version__
from peacock.sanskrit import (
    ARTIFACT_EXTENSION,
    SOURCE_EXTENSION,
    internalise,
    surface,
)
from peacock.compiler.diagnostics import DiagnosticBag, PeacockError
from peacock.compiler.lexer import lex
from peacock.compiler.parser import parse
from peacock.compiler.tokens import SOURCE_CAPABILITIES
from peacock.compiler.pipeline import InternalCompilerError, compile_source
from peacock.compiler import builtins as B
from peacock.runtime.artifact import ArtifactFormatError, artifact_fingerprint, load_image, save_image
from peacock.runtime.disasm import disassemble
from peacock.runtime.errors import format_error
from peacock.runtime.host import HostPolicy
from peacock.runtime.native import method_capability, native_capability
from peacock.runtime.vm import VM

REPO_ROOT = Path(__file__).resolve().parent.parent

EXIT_OK = 0
EXIT_DIAGNOSTICS = 1
EXIT_USAGE = 2
EXIT_RUNTIME = 3
EXIT_INTERNAL = 4
EXIT_FUZZ = 5


class CLIError(Exception):
    def __init__(self, message: str, code: int = EXIT_USAGE):
        super().__init__(message)
        self.code = code


def _color_enabled(stream) -> bool:
    return stream.isatty() and os.environ.get("NO_COLOR") is None


def _read_source(path: Path, require_extension: bool = True) -> str:
    if require_extension and path.suffix != SOURCE_EXTENSION:
        raise CLIError(
            f"'{path}' does not use the canonical PEACOCK source extension '{SOURCE_EXTENSION}'. "
            f"Rename the file (for example, hello{SOURCE_EXTENSION}). Only canonical Sanskrit source files are accepted."
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CLIError(f"cannot read '{path}': {exc}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CLIError(f"'{path}' is not valid UTF-8: {exc}")


def _compile(path: Path, optimize: bool = True, semantic_mode: str = "python"):
    source = _read_source(path)
    try:
        return compile_source(
            source, str(path), optimize_ir=optimize, semantic_mode=semantic_mode
        ), source
    except InternalCompilerError as exc:
        print(f"internal compiler error: {exc}", file=sys.stderr)
        print("This is a compiler bug, not a user error. Please report it.", file=sys.stderr)
        raise CLIError("internal compiler error", EXIT_INTERNAL)


def _print_diagnostics(result, source: str) -> None:
    color = _color_enabled(sys.stderr)
    if result.diagnostics:
        print(result.diagnostics.render_all(source, color), file=sys.stderr)
    errors = len(result.diagnostics.errors())
    warnings = len(result.diagnostics) - errors
    if errors:
        print(f"{errors} error(s), {warnings} warning(s)", file=sys.stderr)
    elif warnings:
        print(f"{warnings} warning(s)", file=sys.stderr)


def _load_image(path: Path) -> dict:
    if path.suffix != ARTIFACT_EXTENSION:
        raise CLIError(f"'{path}' is not a PEACOCK bytecode artifact ('{ARTIFACT_EXTENSION}')")
    try:
        return load_image(str(path))
    except ArtifactFormatError as exc:
        raise CLIError(f"invalid artifact '{path}': {exc}", EXIT_RUNTIME)


def _grant_set(values: list[str]) -> frozenset[str]:
    grants: set[str] = set()
    unknown: set[str] = set()
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item:
                if item not in SOURCE_CAPABILITIES:
                    unknown.add(item)
                else:
                    grants.add(internalise(item))
    if unknown:
        known = ", ".join(SOURCE_CAPABILITIES)
        raise CLIError(
            f"unknown grant(s): {', '.join(sorted(unknown))}; known Sanskrit grants: {known}"
        )
    return frozenset(grants)


def _split_program_args(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1 :]
    return argv, []


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_version(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock version")
    parser.parse_args(argv)
    print(f"PEACOCK AI {__version__} (bootstrap toolchain)")
    print(f"language version: {LANGUAGE_VERSION}")
    print(f"source extension: {SOURCE_EXTENSION}")
    print(f"artifact extension: {ARTIFACT_EXTENSION}")
    print(f"python: {platform.python_version()} on {platform.platform()}")
    print(f"machine: {platform.machine()}, cpus: {os.cpu_count()}")
    print(
        "implementation status: working 0.4 subsets; phases 5-9 and 11 partial; "
        "NOT self-hosting; NOT complete; see STATUS.md"
    )
    return EXIT_OK


def cmd_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock check")
    parser.add_argument("file", type=Path)
    parser.add_argument("--no-opt", action="store_true")
    parser.add_argument(
        "--semantic-shadow",
        action="store_true",
        help="differentially execute the PEACOCK-written semantic kernel (experimental)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    result, source = _compile(
        args.file,
        optimize=not args.no_opt,
        semantic_mode="shadow" if args.semantic_shadow else "python",
    )
    if args.json:
        payload = {
            "ok": result.ok,
            "diagnostics": [
                {
                    "code": d.code,
                    "severity": d.severity.value,
                    "message": d.message,
                    "line": d.span.line,
                    "column": d.span.column,
                }
                for d in result.diagnostics
            ],
            "stats": result.stats,
        }
        print(json.dumps(payload, indent=2))
    else:
        _print_diagnostics(result, source)
        if result.ok and not args.quiet:
            print(
                f"OK {args.file} ({result.stats.get('functions')} function(s), "
                f"{result.stats.get('instructions')} instructions, "
                f"{result.stats.get('total_ms', 0.0):.2f} ms)"
            )
    return EXIT_OK if result.ok else EXIT_DIAGNOSTICS


def cmd_run(argv: list[str]) -> int:
    main_argv, program_args = _split_program_args(argv)
    parser = argparse.ArgumentParser(prog="peacock run")
    parser.add_argument("file", type=Path, help=".सूत्र source or .बीज artifact")
    parser.add_argument("--grant", action="append", default=[], help="Sanskrit host capability grants (सञ्चय, गणना, दृश्य, सञ्जाल)")
    parser.add_argument("--root", default=".", help="filesystem sandbox root (default: cwd)")
    parser.add_argument("--no-opt", action="store_true")
    parser.add_argument("--max-steps", type=int, default=2_000_000)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", type=Path, default=None, help="write a training report JSON if one was produced")
    parser.add_argument("--llm-url", default=None, help="host-configured OpenAI-compatible /v1 endpoint for अभिकर्तृ.स्वायत्त")
    parser.add_argument("--llm-model", default=None, help="model name for the host-configured LLM provider")
    parser.add_argument("--llm-key-env", default=None, help="environment variable containing the provider key (never a source argument)")
    parser.add_argument(
        "--present",
        type=Path,
        default=None,
        help="attach a static-web presentation backend writing frames to DIR (requires --grant दृश्य)",
    )
    parser.add_argument(
        "--serve",
        type=int,
        default=None,
        metavar="PORT",
        help="serve presented frames over HTTP on PORT while the program runs (requires --grant दृश्य)",
    )
    parser.add_argument(
        "--ui-serve",
        type=int,
        default=None,
        metavar="PORT",
        help="serve an interactive retained UI on PORT after दृश्य.प्रदर्शय (requires --grant दृश्य)",
    )
    parser.add_argument(
        "--window", action="store_true", default=None,
        help="present दृश्य in a native X11 window (requires X11 and DISPLAY)",
    )
    parser.add_argument(
        "--serve-host",
        default="127.0.0.1",
        help="HTTP bind address for --serve/--ui-serve (use 0.0.0.0 for a container preview)",
    )
    parser.add_argument(
        "--linger",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="keep the HTTP host alive after the program ends; -1 serves until interrupted",
    )
    args = parser.parse_args(main_argv)
    if sum(option is not None for option in (args.present, args.serve, args.ui_serve, args.window)) > 1:
        raise CLIError("--present, --serve, --ui-serve and --window are mutually exclusive; choose one backend")
    if (args.llm_url is None) != (args.llm_model is None):
        raise CLIError("--llm-url and --llm-model must be supplied together")
    if args.llm_key_env is not None and args.llm_url is None:
        raise CLIError("--llm-key-env requires --llm-url and --llm-model")
    llm_runner = None
    if args.llm_url is not None:
        api_key = None
        if args.llm_key_env is not None:
            if args.llm_key_env not in os.environ:
                raise CLIError(f"LLM key environment variable {args.llm_key_env!r} is not set")
            api_key = os.environ[args.llm_key_env]
        from peacock.intelligence.default_agent import build_llm_runner
        from peacock.intelligence.llm import LLMError

        try:
            llm_runner = build_llm_runner(args.llm_url, args.llm_model, api_key)
        except LLMError as exc:
            raise CLIError(str(exc)) from exc

    grants = _grant_set(args.grant)
    source = None
    if args.file.suffix == ARTIFACT_EXTENSION:
        image = _load_image(args.file)
        stats = {}
    else:
        result, source = _compile(args.file, optimize=not args.no_opt)
        _print_diagnostics(result, source)
        if not result.ok:
            return EXIT_DIAGNOSTICS
        image = result.image
        stats = result.stats

    backend = None
    ui_backend = None
    if args.present is not None:
        from peacock.platforms import WebBackend

        backend = WebBackend(args.present, title=f"{args.file.stem} — PEACOCK")
    elif args.serve is not None:
        from peacock.platforms import ServerBackend

        backend = ServerBackend(
            host=args.serve_host, port=args.serve, title=f"{args.file.stem} — PEACOCK"
        )
        try:
            backend.start()
        except OSError as exc:
            raise CLIError(f"cannot serve on {args.serve_host}:{args.serve}: {exc}") from exc
        print(f"serving at {backend.url}", file=sys.stderr, flush=True)
    elif args.ui_serve is not None:
        from peacock.platforms import UIWebBackend

        ui_backend = UIWebBackend(
            host=args.serve_host, port=args.ui_serve, title=f"{args.file.stem} — PEACOCK UI"
        )
        print(f"interactive UI will serve at {ui_backend.url} on first दृश्य.प्रदर्शय", file=sys.stderr, flush=True)
    elif args.window is not None:
        from peacock.platforms import NativeWindowBackend

        ui_backend = NativeWindowBackend(title=f"{args.file.stem} — PEACOCK")
        print("native X11 window will open on first दृश्य.प्रदर्शय", file=sys.stderr, flush=True)

    host = HostPolicy(
        grants=grants,
        root=args.root,
        max_steps=args.max_steps,
        presenter=backend.present if backend is not None else None,
        ui_presenter=ui_backend.present if ui_backend is not None else None,
        llm_runner=llm_runner,
    )
    capture = io.StringIO() if args.json else None
    stdout = capture if capture is not None else sys.stdout
    vm = VM(image, host, stdout=stdout, argv=program_args)
    exit_code = EXIT_OK
    outcome = None
    try:
        outcome = vm.run()
    except PeacockError as exc:
        if capture is not None and capture.getvalue():
            sys.stderr.write(capture.getvalue())
        print(format_error(exc), file=sys.stderr)
        exit_code = EXIT_RUNTIME
    except ArtifactFormatError as exc:
        print(f"invalid program image: {exc}", file=sys.stderr)
        exit_code = EXIT_RUNTIME
    for active_backend in (backend, ui_backend):
        if active_backend is None:
            continue
        if exit_code == EXIT_OK and args.linger != 0.0:
            if args.linger < 0:
                try:
                    while True:
                        time.sleep(0.5)
                except KeyboardInterrupt:
                    pass
            else:
                time.sleep(args.linger)
        active_backend.close()
    host.close()
    if exit_code != EXIT_OK:
        return exit_code
    if args.report is not None:
        if vm.last_training_report is None:
            print("warning: --report requested but the program produced no training report", file=sys.stderr)
        else:
            payload = vm.last_training_report.to_dict()
            payload["environment"] = {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "cpus": os.cpu_count(),
            }
            args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "output": capture.getvalue(),
                    "steps": outcome.steps,
                    "calls": outcome.calls,
                    "elapsed_seconds": outcome.elapsed_seconds,
                    "compiler": stats,
                    "grants": sorted(grants),
                    "frames_presented": backend.frame_count if backend is not None else 0,
                    "ui_presented": ui_backend.present_count if ui_backend is not None else 0,
                },
                indent=2,
            )
        )
    return EXIT_OK


def cmd_build(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock build")
    parser.add_argument("file", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--no-opt", action="store_true")
    parser.add_argument(
        "--semantic-shadow",
        action="store_true",
        help="require the experimental PEACOCK semantic shadow checks before emitting bytecode",
    )
    args = parser.parse_args(argv)
    result, source = _compile(
        args.file,
        optimize=not args.no_opt,
        semantic_mode="shadow" if args.semantic_shadow else "python",
    )
    _print_diagnostics(result, source)
    if not result.ok:
        return EXIT_DIAGNOSTICS
    output = args.output or args.file.with_suffix(ARTIFACT_EXTENSION)
    size = save_image(result.image, str(output))
    digest = artifact_fingerprint(result.image)
    print(f"built {output} ({size} bytes)")
    print(f"sha256 {digest}")
    print(
        f"module {result.image.get('module')!r}: {result.stats.get('functions')} function(s), "
        f"{result.stats.get('instructions')} instructions, language {result.image['language_version']}"
    )
    return EXIT_OK


def cmd_native(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock native")
    parser.add_argument("file", type=Path, help=".सूत्र source in the documented native AOT subset")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--cc", default="cc", help="C11 compiler used for the final native link")
    parser.add_argument("--keep-c", type=Path, default=None, help="retain generated C and runtime for audit")
    parser.add_argument("--library", action="store_true", help="build an embeddable shared library with peacock_run instead of an executable")
    parser.add_argument("--max-steps", type=int, default=2_000_000)
    parser.add_argument("--no-opt", action="store_true")
    args = parser.parse_args(argv)
    result, source = _compile(args.file, optimize=not args.no_opt)
    _print_diagnostics(result, source)
    if not result.ok:
        return EXIT_DIAGNOSTICS
    from peacock.native import NativeBuildError, NativeCodegenError, build_native, build_native_library

    try:
        if args.library:
            output = build_native_library(result.image, args.output, compiler=args.cc, keep_c=args.keep_c)
        else:
            output = build_native(
                result.image, args.output, compiler=args.cc,
                keep_c=args.keep_c, max_steps=args.max_steps,
            )
    except (NativeBuildError, NativeCodegenError) as exc:
        raise CLIError(str(exc), EXIT_DIAGNOSTICS) from exc
    print(f"built native {'shared library' if args.library else 'executable'} {output}")
    print("runtime: PEACOCK C runtime + system C/math libraries; no Python dependency")
    return EXIT_OK


def cmd_disasm(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock disasm")
    parser.add_argument("file", type=Path)
    parser.add_argument("--no-opt", action="store_true")
    args = parser.parse_args(argv)
    if args.file.suffix == ARTIFACT_EXTENSION:
        image = _load_image(args.file)
    else:
        result, source = _compile(args.file, optimize=not args.no_opt)
        _print_diagnostics(result, source)
        if not result.ok:
            return EXIT_DIAGNOSTICS
        image = result.image
    print(disassemble(image))
    return EXIT_OK


def cmd_audit(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock audit")
    parser.add_argument("file", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result, source = _compile(args.file)
    _print_diagnostics(result, source)
    if not result.ok:
        return EXIT_DIAGNOSTICS
    image = result.image
    functions = {}
    natives = set()
    methods = set()
    for name, fn in image["functions"].items():
        calls = []
        for instr in fn["code"]:
            if instr[0] == "CALL_NATIVE":
                natives.add(instr[1])
                cap = native_capability(instr[1])
                calls.append({"kind": "native", "name": instr[1], "capability": cap})
            elif instr[0] == "METHOD":
                methods.add(instr[1])
                cap = method_capability(instr[1])
                calls.append({"kind": "method", "name": instr[1], "capability": cap})
            elif instr[0] == "MODEL_INIT":
                calls.append({"kind": "model_init", "name": instr[1], "capability": "compute"})
            elif instr[0] == "TRAINING_METHOD":
                calls.append({"kind": "training", "name": f"{instr[1]}.{instr[2]}", "capability": "compute"})
        functions[name] = {
            "declared_capabilities": list(fn["caps"]),
            "capability_calls": [c for c in calls if c["capability"]],
            "slots": fn["slots"],
        }
    payload = {
        "module": image.get("module"),
        "uses": image.get("uses", []),
        "functions": functions,
        "capabilities_used": sorted(
            {cap for fn in functions.values() for cap in fn["declared_capabilities"]}
        ),
        "natives": sorted(natives),
        "methods": sorted(methods),
        "models": sorted(image.get("models", {})),
        "trainings": sorted(image.get("trainings", {})),
        "note": "Static audit only. The host must separately grant capabilities at run time.",
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"capability audit for {args.file}")
        print(f"declared capabilities: {', '.join(surface(c) for c in payload['capabilities_used']) or 'none'}")
        print(f"imports: {', '.join(surface(u) for u in payload['uses']) or 'none'}")
        for name, info in functions.items():
            caps = ", ".join(surface(c) for c in info["declared_capabilities"]) or "none"
            calls = ", ".join(
                f"{surface(c['name'])}({surface(c['capability'])})"
                for c in info["capability_calls"]
            ) or "none"
            print(f"  कार्य {surface(name)}: declared={caps}; privileged calls={calls}")
        if payload["models"]:
            print(f"models: {', '.join(surface(m) for m in payload['models'])}")
        if payload["trainings"]:
            print(f"training declarations: {', '.join(surface(t) for t in payload['trainings'])}")
    return EXIT_OK


def cmd_bench(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock bench")
    parser.add_argument("--json", type=Path, default=None, help="write full results to this path")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    from peacock.benchmarks import format_report, run_benchmarks

    report = run_benchmarks(quick=args.quick)
    print(format_report(report))
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json}")
    return EXIT_OK


def cmd_fuzz(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock fuzz")
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    from peacock.fuzzing import run_all

    reports = run_all(args.iterations, args.seed)
    payload = [r.to_dict() for r in reports]
    for report in reports:
        status = "OK" if report.ok else "CRASHES"
        print(f"{report.target:10s} {status:8s} handled={report.handled:5d} crashes={len(report.crashes)}")
        for crash in report.crashes[:10]:
            print(f"  - {crash}")
    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return EXIT_OK if all(r.ok for r in reports) else EXIT_FUZZ


def cmd_test(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock test")
    parser.add_argument("-p", "--pattern", default="test_*.py")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(str(REPO_ROOT / "tests"), pattern=args.pattern, top_level_dir=str(REPO_ROOT))
    verbosity = 1 if args.quiet else 2
    runner = unittest.TextTestRunner(verbosity=verbosity)
    outcome = runner.run(suite)
    return EXIT_OK if outcome.wasSuccessful() else EXIT_DIAGNOSTICS


def cmd_tokens(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock tokens")
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    source = _read_source(args.file)
    tokens, diag = lex(source, str(args.file))
    for token in tokens:
        print(f"{token.span.line:4d}:{token.span.column:<4d} {token.kind.name:12s} {token.text!r}")
    if diag:
        print(diag.render_all(source), file=sys.stderr)
    return EXIT_OK if not diag.has_errors else EXIT_DIAGNOSTICS


def cmd_ast(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peacock ast")
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    source = _read_source(args.file)
    tokens, lex_diag = lex(source, str(args.file))
    if lex_diag.has_errors:
        print(lex_diag.render_all(source), file=sys.stderr)
        return EXIT_DIAGNOSTICS
    module, parse_diag = parse(tokens, source, str(args.file))
    combined = DiagnosticBag()
    combined.extend(lex_diag)
    combined.extend(parse_diag)
    if combined.has_errors:
        print(combined.render_all(source), file=sys.stderr)
        return EXIT_DIAGNOSTICS
    import pprint

    pprint.pprint(module, width=110, compact=True)
    return EXIT_OK


def cmd_vyakarana(argv: list[str]) -> int:
    """Use the native Sanskrit corpus and executable grammar tools."""

    from peacock.vyakarana import (
        EXPECTED_SUTRAS, EXECUTABLE_RULE_IDS, CorpusError, PratyaharaError,
        SandhiError, ShabdaError, DhatuError, SamasaError, KarakaError,
        expand, get_sutra, join, literature, search,
        vibhakti_rupa, declension_table, guess_pratipadika,
        dhatu_rupa, conjugation_table, list_dhatus, tinanta_analyze,
        samasa_analyze, karaka_info, list_karakas, vyutpatti, prakriti_pratyaya_vibhaga,
        validate_word, validate_sentence, rule_detail, get_engine, viccheda, validate_sandhi,
        classify_varna,
    )

    parser = argparse.ArgumentParser(prog="peacock व्याकरण")
    operations = parser.add_subparsers(dest="operation", required=True)
    operations.add_parser("सूत्र").add_argument("id")
    p_lookup = operations.add_parser("अन्वेषय")
    p_lookup.add_argument("query")
    p_lookup.add_argument("--अवधि", type=int, default=50)
    operations.add_parser("प्रत्याहार").add_argument("name")
    p_sandhi = operations.add_parser("संधि")
    p_sandhi.add_argument("left")
    p_sandhi.add_argument("right")
    operations.add_parser("साहित्य")
    operations.add_parser("आच्छादन")
    p_vib = operations.add_parser("विभक्तिरूप")
    p_vib.add_argument("pratipadika")
    p_vib.add_argument("vibhakti")
    p_vib.add_argument("vachana")
    operations.add_parser("रूपावली").add_argument("pratipadika")
    operations.add_parser("शब्दनिर्णय").add_argument("pada")
    p_dhatu = operations.add_parser("धातुरूप")
    p_dhatu.add_argument("dhatu")
    p_dhatu.add_argument("lakara")
    p_dhatu.add_argument("purusha")
    p_dhatu.add_argument("vachana")
    p_dt = operations.add_parser("धातुरूपावली")
    p_dt.add_argument("dhatu")
    p_dt.add_argument("lakara", nargs="?", default="लट्")
    operations.add_parser("धातुसूची")
    operations.add_parser("तिङ्विश्लेषण").add_argument("pada")
    operations.add_parser("समास").add_argument("pada")
    operations.add_parser("विग्रह").add_argument("pada")
    operations.add_parser("समासप्रकार").add_argument("pada")
    operations.add_parser("कारक").add_argument("sentence")
    operations.add_parser("कारकविवरण").add_argument("karaka")
    operations.add_parser("कारकसूची")
    operations.add_parser("व्युत्पत्ति").add_argument("shabda")
    operations.add_parser("प्रकृतिविभाग").add_argument("shabda")
    operations.add_parser("शब्दसाधुत्व").add_argument("word")
    operations.add_parser("वाक्यसाधुत्व").add_argument("sentence")
    operations.add_parser("सूत्रविवरण").add_argument("id")
    p_rule = operations.add_parser("नियमप्रयोग")
    p_rule.add_argument("input")
    p_rule.add_argument("rules")
    operations.add_parser("अधिकारविस्तार").add_argument("term")
    operations.add_parser("वर्णभेद").add_argument("varna")
    operations.add_parser("संधिविच्छेद").add_argument("word")
    p_sv = operations.add_parser("संधिसत्यापन")
    p_sv.add_argument("left")
    p_sv.add_argument("right")
    p_sv.add_argument("combined")
    args = parser.parse_args(argv)
    try:
        if args.operation == "सूत्र":
            print(get_sutra(args.id).display())
        elif args.operation == "अन्वेषय":
            for result in search(args.query, args.अवधि):
                print(result.display())
        elif args.operation == "प्रत्याहार":
            print(" ".join(expand(args.name)))
        elif args.operation == "संधि":
            result = join(args.left, args.right)
            print(f"{result.text} — {result.rule_id} {result.rule_name}")
        elif args.operation == "साहित्य":
            for row in literature():
                print(row)
        elif args.operation == "आच्छादन":
            print(f"sūtra texts: {EXPECTED_SUTRAS}")
            print(f"executable rules: {len(EXECUTABLE_RULE_IDS)} ({', '.join(sorted(EXECUTABLE_RULE_IDS))})")
            eng = get_engine()
            cov = eng.coverage_report()
            print(f"engine: total {cov['total']} executable {cov['executable_transformations']} kinds {cov['by_kind']} paribhasha {cov['paribhasha_defined']} sapada {cov['sapada']} tripadi {cov['tripadi']}")
        elif args.operation == "विभक्तिरूप":
            print(vibhakti_rupa(args.pratipadika, args.vibhakti, args.vachana).rupa)
        elif args.operation == "रूपावली":
            table = declension_table(args.pratipadika)
            for i, row in enumerate(table):
                print(f"{['प्रथमा','द्वितीया','तृतीया','चतुर्थी','पञ्चमी','षष्ठी','सप्तमी','संबोधन'][i]}: {' | '.join(row)}")
        elif args.operation == "शब्दनिर्णय":
            for c in guess_pratipadika(args.pada):
                print(f"{c['pratipadika']} — {c['vibhakti']} {c['vachana']} ({c['sutra']})")
        elif args.operation == "धातुरूप":
            print(dhatu_rupa(args.dhatu, args.lakara, args.purusha, args.vachana).rupa)
        elif args.operation == "धातुरूपावली":
            table = conjugation_table(args.dhatu, args.lakara)
            for i, row in enumerate(table):
                print(f"{['प्रथम','मध्यम','उत्तम'][i]}: {' | '.join(row)}")
        elif args.operation == "धातुसूची":
            for d in list_dhatus():
                print(f"{d['dhatu']} ({d['artha']}, {d['gana']})")
        elif args.operation == "तिङ्विश्लेषण":
            for c in tinanta_analyze(args.pada):
                print(f"{c['dhatu']} {c['lakara']} {c['purusha']} {c['vachana']} ({c['sutra']})")
        elif args.operation == "समास":
            a = samasa_analyze(args.pada)
            print(f"{a.samasta_pada} → {a.samasa_type} | {a.vigraha} | {a.sutra} — {a.description}")
        elif args.operation == "विग्रह":
            from peacock.vyakarana.samasa import vigraha as vg
            print(vg(args.pada))
        elif args.operation == "समासप्रकार":
            from peacock.vyakarana.samasa import samasa_type as st
            print(st(args.pada))
        elif args.operation == "कारक":
            from peacock.vyakarana.karaka import analyze_sentence as ka
            for l in ka(args.sentence):
                print(f"{l.pada} → {l.karaka} ({l.vibhakti}) [{l.sutra}]")
        elif args.operation == "कारकविवरण":
            info = karaka_info(args.karaka)
            print(f"{info['karaka']} — {info['sutra']} : {info['desc']}")
        elif args.operation == "कारकसूची":
            for k in list_karakas():
                print(f"{k['karaka']} — {k['sutra']}")
        elif args.operation == "व्युत्पत्ति":
            print(vyutpatti(args.shabda).trace())
        elif args.operation == "प्रकृतिविभाग":
            info = prakriti_pratyaya_vibhaga(args.shabda)
            print(f"{info['prakriti']} + {info['pratyaya']} → {info['siddha']}")
        elif args.operation == "शब्दसाधुत्व":
            print(validate_word(args.word).report())
        elif args.operation == "वाक्यसाधुत्व":
            print(validate_sentence(args.sentence).report())
        elif args.operation == "सूत्रविवरण":
            print(str(rule_detail(args.id)))
        elif args.operation == "नियमप्रयोग":
            from peacock.vyakarana.sutra_engine import apply_rules as ar
            der = ar(args.input, [r.strip() for r in args.rules.split(",")])
            print(der.trace_text())
            if der.conflicts:
                print("conflicts:", der.conflicts)
        elif args.operation == "अधिकारविस्तार":
            from peacock.vyakarana.sutra_engine import adhikara_info as ai
            for line in ai(args.term):
                print(line)
        elif args.operation == "वर्णभेद":
            print(classify_varna(args.varna))
        elif args.operation == "संधिविच्छेद":
            for c in viccheda(args.word):
                print(c)
        elif args.operation == "संधिसत्यापन":
            print(validate_sandhi(args.left, args.right, args.combined))
        else:
            print(f"unknown operation {args.operation}")
    except (CorpusError, PratyaharaError, SandhiError, ShabdaError, DhatuError, SamasaError, KarakaError) as exc:
        raise CLIError(str(exc), EXIT_DIAGNOSTICS) from exc
    return EXIT_OK


COMMANDS = {
    "version": cmd_version,
    "व्याकरण": cmd_vyakarana,
    "check": cmd_check,
    "run": cmd_run,
    "build": cmd_build,
    "native": cmd_native,
    "disasm": cmd_disasm,
    "audit": cmd_audit,
    "bench": cmd_bench,
    "fuzz": cmd_fuzz,
    "test": cmd_test,
    "tokens": cmd_tokens,
    "ast": cmd_ast,
}

USAGE = """PEACOCK AI bootstrap toolchain

usage: peacock <command> [options]

commands:
  run <file.सूत्र|file.बीज>   compile (if needed) and execute
  check <file.सूत्र>          lex, parse, type check, lower and verify
  build <file.सूत्र>          write a .बीज bytecode artifact
  native <file.सूत्र> -o BIN  AOT-compile the supported subset to an executable/library
  disasm <file>             disassemble a source file or artifact
  audit <file.सूत्र>          static capability audit
  व्याकरण <operation>        sūtra lookup, search, pratyāhāra and sandhi
  tokens <file.सूत्र>         dump the token stream (debugging)
  ast <file.सूत्र>            dump the syntax tree (debugging)
  bench                     run the reproducible benchmark suite
  fuzz                      run deterministic fuzzers
  test                      run the unit/integration test suite
  version                   print versions and status

Run options: --grant सञ्चय,गणना,दृश्य,सञ्जाल  --root DIR  --max-steps N  --json  --report FILE
             [--llm-url URL --llm-model NAME [--llm-key-env VAR]]
             --present DIR | --serve PORT | --ui-serve PORT | --window
             [--serve-host ADDR] [--linger SECONDS]
Program arguments: peacock run app.सूत्र --grant सञ्चय -- arg1 arg2
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return EXIT_OK
    # Conventional version flag alongside the explicit `version` subcommand.
    if argv[0] in ("--version", "-V"):
        return cmd_version(argv[1:])
    command = argv[0]
    if command not in COMMANDS:
        print(f"unknown command '{command}'\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return EXIT_USAGE
    try:
        return COMMANDS[command](argv[1:])
    except CLIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
