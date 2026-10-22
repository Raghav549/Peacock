# Dependencies and bootstrap boundary

Status audited 2026-10-22. This file distinguishes dependencies needed to build
or run the current implementation from tools required only for optional
platform work. No external service or paid compute is required for the current
core workflow.

## Core implementation today

| Dependency | Required? | Purpose / policy |
|---|---|---|
| Python 3.11+ | Yes, current toolchain | Temporary bootstrap compiler, CLI, VM, standard library natives, tensor/agent engines, grammar library, frontend and tests. This is a genuine language implementation written in Python, not `.सूत्र` source. |
| Python standard library | Yes | `argparse`, `json`, `hashlib`, `struct`, `zlib`, `http.server`, `unittest`, `math`, `random`, `pathlib`, and related modules. No third-party runtime package is declared. |
| setuptools >= 61 | Build backend | `pyproject.toml` build-system requirement, used when installing a Python package. Running `./bin/peacock` itself uses Python directly. |
| pytest | No | Not declared; the test suite uses `unittest`. The audit environment did not have pytest installed. |

`pyproject.toml` has `dependencies = []`. No NumPy, PyTorch, TensorFlow, LLVM,
React, Flutter, downloaded model or external training dataset is required by the
current core. The attributed Aṣṭādhyāyī sūtra corpus is vendored package data,
not a runtime download; its provenance is recorded under `peacock/vyakarana/data/`.

## Current migration state

`selfhost/tokenizer.सूत्र` and `selfhost/parser.सूत्र` are executed by the Python
compiler/VM and have parity tests. `selfhost/type_model.सूत्र` adds an executable
PEACOCK-written kernel for type relations, expression result rules and lexical
bindings. The opt-in `compile_source(..., semantic_mode="shadow")` adapter and
`--semantic-shadow` CLI flags derive probes from typed ASTs and compare outcomes
with Python on supported expressions, declarations, scopes, assignments,
user-function signatures/calls, conditions and returns. This is experimental:
Python remains authoritative and there is no switch-over. Diagnostic recovery
parity and several semantic domains remain unimplemented.

`website/site.सूत्र` is a PEACOCK-authored static website exporter verified through
the actual CLI and compiler/VM. It generates twelve HTML routes, CSS and an SVG
asset from one `.सूत्र` compilation unit (there is no user module system yet). Its
browser output uses no JavaScript or external UI framework. The export command
needs a 10,000,000-step VM budget; generated `website/dist/` is ignored. Tests
check routes, links, semantic/accessibility markers, source examples and CSS;
there is no browser screenshot suite. The following remain Python bootstrap
implementations:

- production lexer/parser/AST/diagnostics and parser recovery;
- semantic analysis, name resolution and the production type model;
- IR construction, verification, optimization, bytecode emission and artifact handling;
- VM, host policy, native dispatch and standard-library implementation;
- tensor/autodiff/training/serialization, bounded-agent and grammar libraries;
- colour, 2-D/CPU-3-D, retained-UI and platform libraries;
- CLI, packaging and test runner.

Migration policy: add a `.सूत्र` implementation behind a stable contract, build a
corpus of positive/negative cases, compare against the Python oracle, add runtime
and resource-limit coverage, then switch callers only after parity is measured.
Retain the Python implementation as an oracle until reproducible bootstrap/fixed
point criteria are met. Do not label components self-hosted merely because a
`.सूत्र` prototype exists.

## Optional platform/tooling dependencies

No native platform target is currently claimed. Future requirements are
conditional and must be separately documented and version-pinned before use:

| Target/workflow | Likely external tooling | Current status |
|---|---|---|
| Static website export | Browser for viewing; optional Python standard-library static HTTP server | Implemented by `website/site.सूत्र` as HTML/CSS/SVG export, with actual CLI integration tests. No browser automation or visual-regression tooling is installed. Not the same as the frame `WebBackend`; no JS or general interactive UI runtime. |
| WebAssembly | WASM assembler/runtime or a PEACOCK-authored emitter and browser ABI | No backend currently exists. Prefer specifying ABI and validating generated artifacts before choosing a tool. |
| Desktop | OS window/input APIs and platform toolchains | No desktop shell currently exists. |
| Android | Android SDK/NDK, Java/Kotlin or JNI boundary, signing/package tools | No Android build validated. |
| iOS | macOS, Xcode, Apple SDKs, signing credentials | No iOS build validated; unavailable in this Linux environment. |
| Accelerated AI/rendering | Vendor GPU SDKs/drivers or documented portable APIs | No GPU kernel/backend currently exists. CPU implementation only. |
| VS Code extension | VS Code runtime for manual integration testing; no npm runtime dependency currently required by the grammar files | Package is prepared, not published or editor-integration tested. |
| Linguist contribution | Ruby/Bundler and Linguist's own grammar/sample tools in an upstream checkout | Not run; proposed contribution is not submitted and usage evidence is presently inadequate. |

## Installation and reproducibility

Current direct run: Python 3.11+ and `./bin/peacock <command>`. For package
installation, use `python -m pip install .` in an isolated environment. On
2026-10-22, `pip wheel . --no-deps --no-build-isolation` produced
`peacock_ai-0.3.0-py3-none-any.whl` (287,956 bytes); its 66 members included the
native engines, 1,321,310-byte sūtra corpus, literature catalogue and provenance.
A temporary `--target` installation outside the checkout passed `version`,
3,983/4 coverage and `रामेन्द्रः` sandhi smoke tests. This validates the local
wheel path, not a published release or every platform. No lockfile is applicable
while runtime dependencies are empty. Platform-specific dependencies must not be
added to the core requirement set unless the implementation genuinely imports
them and has tests/build coverage.

## Dependency reduction milestones

1. Port semantic/type primitives and diagnostics into `.सूत्र`, parity-test, and
   wire them into a compiler path while retaining Python as oracle.
2. Port IR/verification and deterministic bytecode generation; compare artifact
   bytes.
3. Port VM and host ABI with resource/capability parity.
4. Retire Python only after a reproducible fixed-point build and full regression
   suite; keep Python optional as a reference oracle for at least one release.
