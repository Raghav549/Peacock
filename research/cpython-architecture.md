# CPython Repository Architectural Research and PEACOCK Design Synthesis

Inspected repository: <https://github.com/python/cpython> (live tree verified via GitHub API on 2026-10-17).

> **Independence policy:** CPython is studied strictly for compiler, runtime, standard-library and tooling architecture lessons. PEACOCK does not copy CPython source code, does not adopt Python's dynamic semantics, and does not treat Python files as PEACOCK programs. All PEACOCK language components in `selfhost/*.pac`, `examples/*.pac` and `website/site.pac` are original `.pac` implementations.

---

## 1. Verified Top-Level Layout of `python/cpython`

Direct inspection of `python/cpython` at `HEAD` confirms the following top-level directories and files:

- **Grammar and parsing:** `Grammar/` (`python.gram`, `Tokens`), `Parser/` (`Python.asdl`, `pegen.c`, `pegen.h`, `pegen_errors.c`, `action_helpers.c`, `asdl_c.py`, `lexer/`, `tokenizer/`).
- **Compiler and interpreter core:** `Python/` (`compile.c`, `codegen.c`, `symtable.c`, `flowgraph.c`, `intrinsics.c`, `assemble.c`, `bytecodes.c`, `ceval.c`, `ceval_macros.h`, `bltinmodule.c`, `import.c`, `marshal.c`).
- **Headers and ABI contracts:** `Include/` (`Python.h`, `abstract.h`, `object.h`, `ceval.h`, `compile.h`, `frameobject.h`, `cpython/`, `internal/`).
- **Object model:** `Objects/` (`object.c`, `typeobject.c`, `longobject.c`, `floatobject.c`, `unicodeobject.c`, `listobject.c`, `dictobject.c`, `codeobject.c`, `frameobject.c`, `funcobject.c`, `exceptions.c`).
- **Native extension modules:** `Modules/` (`Setup`, `Setup.bootstrap.in`, `Setup.stdlib.in`, `_collectionsmodule.c`, `_json.c`, `_io/`, `_hashopenssl.c`, `_hacl/`, `_ctypes/`, `_sqlite/`).
- **Executable entry points:** `Programs/` (`python.c`, `_bootstrap_python.c`, `_freeze_module.c`, `_testembed.c`).
- **Standard library and regression suite:** `Lib/` (191 top-level entries) and `Lib/test/` (520 entries managed by `Lib/test/regrtest`).
- **Build, code-generation and developer tools:** `Tools/` (`cases_generator/`, `peg_generator/`, `clinic/`, `jit/`, `c-analyzer/`, `freeze/`, `build/`).
- **Platform-specific trees:** `PC/` and `PCbuild/` (Windows entry points, `WinMain.c`, MSBuild `.vcxproj` project graph), `Mac/` (macOS framework build, `PythonLauncher`, packaging), `Platforms/` (mobile/embedded support).
- **Maintenance and internal documentation:** `Misc/` (`NEWS.d`, `sbom.spdx.json`, `stable_abi.toml`, `python-config.in`), `InternalDocs/` (`structure.md`, `compiler.md`, `interpreter.md`, `parser.md`, `frames.md`, `code_objects.md`, `exception_handling.md`, `garbage_collector.md`).
- **CI and development containers:** `.github/workflows/` (`build.yml`, `lint.yml`, `jit.yml`, `reusable-ubuntu.yml`, `reusable-windows.yml`, `reusable-macos.yml`, `reusable-wasi.yml`), `.azure-pipelines/`, `.devcontainer/`.

---

## 2. Subsystem-by-Subsystem Analysis (7-Point Evaluation)

### 2.1 `Grammar/` and `Parser/` (`python.gram`, `Tokens`, `Python.asdl`, `pegen`)

1. **Responsibility in CPython:** Defines the concrete syntax in `Grammar/python.gram` and token kinds in `Grammar/Tokens`, specifies the abstract syntax tree schema in `Parser/Python.asdl`, and implements the PEG parser runtime and lexer/tokenizer under `Parser/`.
2. **Architectural principle worth learning:** Separating the declarative grammar and AST node schema from hand-written semantic passes keeps syntax evolution auditable and allows tooling (pretty-printers, AST digests, linters) to share one canonical tree structure.
3. **Application to PEACOCK:** PEACOCK mirrors this separation via `peacock/compiler/tokens.py`, `peacock/compiler/ast_nodes.py`, `SPECIFICATION.md` §3, and the structural S-expression oracle in `tests/integration/ast_digest.py`.
4. **What must be redesigned for PEACOCK:** Unlike Python's indentation-sensitive PEG grammar (`INDENT`/`DEDENT` tokens), PEACOCK uses explicit brace-delimited blocks (`{ ... }`), semicolon-terminated statements, static type annotations (`Tensor<Float32, [2, 3]>`), capability declarations (`capability fs;`), and first-class `model` and `training` blocks.
5. **What is independently implemented:** `peacock/compiler/lexer.py`, `peacock/compiler/parser.py`, `selfhost/tokenizer.pac`, and `selfhost/parser.pac` are 100% original implementations with zero code shared with `pegen`.
6. **Necessary OS/platform interfaces:** Only UTF-8 source buffer reading when invoked from the CLI.
7. **Verification tests:** `tests/compiler/test_lexer.py`, `tests/compiler/test_parser.py`, `tests/integration/test_selfhost_parser.py` (verifying AST-digest parity across 18 `.pac` files including self-parse of `selfhost/parser.pac`, `selfhost/type_model.pac`, and `selfhost/ir_model.pac`).

### 2.2 `Python/` Compiler Pipeline (`symtable.c`, `codegen.c`, `flowgraph.c`, `assemble.c`)

1. **Responsibility in CPython:** Resolves lexical scopes (`symtable.c`), lowers AST nodes into control-flow instruction graphs (`codegen.c`), performs control-flow and peephole optimisations (`flowgraph.c`), and assembles final `PyCodeObject` bytecode and exception tables (`assemble.c`).
2. **Architectural principle worth learning:** Multi-stage lowering (AST → symbol/type resolution → explicit IR with basic-block/label verification → optimised IR → verified bytecode image) isolates front-end diagnostics from back-end code generation bugs.
3. **Application to PEACOCK:** PEACOCK implements `semantic.py` (declaration collection, lexical scopes, static type & capability checking) → `ir.py` (`IRBuilder` + `IRVerifier`) → `optimizer.py` (constant folding, branch folding, dead-temp elimination) → `bytecode.py` (`compile_to_image` + `verify_image`), plus the self-hosted semantic and IR verification kernels in `selfhost/type_model.pac` and `selfhost/ir_model.pac`.
4. **What must be redesigned for PEACOCK:** CPython compiles untyped dynamic operations (`BINARY_OP` with runtime specialization) and implicit variable creation on assignment. PEACOCK requires explicit `let` / `let mut` declarations, static type resolution before IR construction, static tensor shape/dtype checking, and compile-time capability verification.
5. **What is independently implemented:** All of `peacock/compiler/{semantic,types,ir,optimizer,bytecode}.py` and `selfhost/{type_model,ir_model}.pac`.
6. **Necessary OS/platform interfaces:** `hashlib.sha256` for `.pkb` bytecode artifact fingerprinting.
7. **Verification tests:** `tests/compiler/test_semantic.py`, `tests/compiler/test_types.py`, `tests/compiler/test_ir.py`, `tests/compiler/test_pipeline.py`, and `tests/integration/test_selfhost_type_model.py`.

### 2.3 `Python/` Interpreter & Evaluation Loop (`bytecodes.c`, `ceval.c`)

1. **Responsibility in CPython:** Defines the bytecode instruction set (`bytecodes.c`) and executes frames in the evaluation loop (`ceval.c`) with zero-cost exception table lookup and stack management.
2. **Architectural principle worth learning:** Defining instruction semantics cleanly, verifying bytecode jump/slot invariants prior to dispatch, and maintaining explicit call-frame state with structured exception handler ranges.
3. **Application to PEACOCK:** `peacock/runtime/vm.py` verifies every bytecode image via `verify_image` before execution, tracks per-frame local slots, operand stacks and `try/catch` handler ranges, and enforces deterministic step (`max_steps`) and call-depth (`max_call_depth`) budgets.
4. **What must be redesigned for PEACOCK:** PEACOCK's VM enforces mandatory runtime capability gates (`compute`, `fs`, `ui`) on every protected native and method call, checked 64-bit integer arithmetic (`PE4004`), and deterministic resource budgets (`PE4003`), whereas CPython allows unrestricted host process access from any bytecode frame.
5. **What is independently implemented:** `peacock/runtime/{vm,artifact,disasm,errors,values}.py`.
6. **Necessary OS/platform interfaces:** Standard output stream and host policy callbacks.
7. **Verification tests:** `tests/compiler/test_vm.py` and `tests/security/test_capabilities.py`.

### 2.4 `Include/` and `Objects/` (Public Headers & Core Object Representations)

1. **Responsibility in CPython:** `Include/` exposes the public C API (`Python.h`), limited Stable ABI (`cpython/`), and internal headers (`internal/`), while `Objects/` implements the concrete memory layouts and type tables for `int`, `float`, `str`, `list`, `dict`, `code`, and `frame`.
2. **Architectural principle worth learning:** Separating the language's value semantics and type descriptors from host-specific memory representations allows the compiler and runtime to evolve toward native code generation without changing source-level semantics.
3. **Application to PEACOCK:** `peacock/compiler/types.py`, `selfhost/type_model.pac`, and `peacock/runtime/values.py` define PEACOCK's value categories (`Int`, `Float`, `Bool`, `String`, `Unit`, `List<T>`, `Tensor<D, S>`, nominal `StructInstance`, `RangeValue`, `Color`, `Canvas`, `Model`, `Dataset`).
4. **What must be redesigned for PEACOCK:** CPython's `PyObject` header carries reference counts and dynamic type pointers on every scalar. PEACOCK's static type system knows primitive, struct, list and tensor types at compile time, and its tensors (`peacock/intelligence/tensor.py`) carry explicit shape, dtype and reverse-mode autodiff graph links.
5. **What is independently implemented:** `peacock/runtime/values.py`, `peacock/intelligence/tensor.py`, `peacock/frontend/colour.py`, `peacock/frontend/canvas.py`.
6. **Necessary OS/platform interfaces:** IEEE-754 floating-point conversions (`struct.pack`/`unpack` for binary32 rounding and `.pkm` serialization).
7. **Verification tests:** `tests/compiler/test_types.py`, `tests/ai/test_tensor.py`, `tests/frontend/test_colour.py`.

### 2.5 `Modules/` and `Lib/` (Native Accelerators & Standard Library Dual Architecture)

1. **Responsibility in CPython:** As documented in `InternalDocs/structure.md`, CPython pairs pure-language library modules in `Lib/<module>.py` with C accelerators in `Modules/_<module>.c` (for example, `json` + `_json.c`, `collections` + `_collectionsmodule.c`, `hashlib` + `_hashopenssl.c` / `_hacl`).
2. **Architectural principle worth learning:** A clean contract between language-level APIs (`builtins.py` signatures and docs) and host/native kernel implementations (`runtime/native.py`) lets core algorithms migrate progressively into `.pac` while keeping well-defined OS/cryptographic/I/O boundaries in native host code.
3. **Application to PEACOCK:** PEACOCK's standard library is declared in `peacock/compiler/builtins.py` (`NATIVES`, `METHODS`, `PROPERTIES`, `NATIVE_DOCS`) and dispatched through `peacock/runtime/native.py` across `math`, `text`, `fs`, `process`, `colour`, `graphics`, `motion`, and `nn`.
4. **What must be redesigned for PEACOCK:** Every effectful standard-library entry in PEACOCK carries static and runtime capability metadata (`fs`, `compute`, `ui`) and sandbox confinement (`HostPolicy`), unlike Python's ambient-authority `os`/`io` modules.
5. **What is independently implemented:** All tensor kernels, reverse-mode autodiff, Dense/Sequential layers, SGD/Adam optimisers, Oklab/Oklch/CIELAB/sRGB colour math, thin-film iridescence, WCAG contrast, 2D software rasteriser, 3D analytic GGX/Schlick sphere shader, PNG encoder/decoder, spring physics, and AABB collision solver.
6. **Necessary OS/platform interfaces:** `zlib` (DEFLATE stream inside PNG), `hashlib` (SHA-256), `json` (RFC 8259 string/document parsing), and OS filesystem operations confined behind `HostPolicy`.
7. **Verification tests:** `tests/unit/test_version.py`, `tests/security/test_capabilities.py`, `tests/ai/test_training.py`, `tests/frontend/test_canvas_png.py`, `tests/frontend/test_motion.py`.

### 2.6 `Programs/` and `Tools/` (Bootstrap Binaries & Developer Tooling)

1. **Responsibility in CPython:** `Programs/` provides `python.c` and bootstrap tools (`_bootstrap_python.c`, `_freeze_module.c`) used during staged compilation; `Tools/` provides `peg_generator`, `cases_generator`, `clinic`, `jit` and static analysis utilities.
2. **Architectural principle worth learning:** Staged bootstrapping—where a minimal bootstrap compiler compiles or freezes language-authored modules (`_freeze_module`)—is the disciplined path toward self-hosting. Furthermore, shipping first-party developer tools (`fmt`, `lint`, `doc`, `init`, `bench`, `fuzz`, `test`) inside the main toolchain prevents ecosystem fragmentation.
3. **Application to PEACOCK:** `bin/peacock` and `peacock/cli.py` provide a single unified entry point supporting `version`, `check`, `run`, `build`, `disasm`, `audit`, `tokens`, `ast`, `fmt`, `lint`, `doc`, `init`, `bench`, `fuzz`, and `test`, while `selfhost/{tokenizer,parser,type_model,ir_model}.pac` form the staged self-hosting progression.
4. **What must be redesigned for PEACOCK:** PEACOCK's `lint` and `audit` subcommands inspect static capability declarations (`PE3105` unused capability warnings and capability call graphs), and `check --semantic-shadow` runs differential probes comparing Python's typed AST against `.pac` kernels in the VM.
5. **What is independently implemented:** `peacock/cli.py`, `peacock/fuzzing.py`, `peacock/benchmarks.py`, and all `selfhost/*.pac` modules.
6. **Necessary OS/platform interfaces:** Process argument vector (`sys.argv`), standard streams, and exit codes (`0`–`5`).
7. **Verification tests:** `tests/integration/test_cli.py`, `tests/integration/test_fuzzing.py`, `tests/benchmarks/test_benchmarks.py`.

### 2.7 `PC/`, `PCbuild/`, `Mac/`, `Platforms/`, and `Misc/` (Platform Targets & Release Metadata)

1. **Responsibility in CPython:** `PC/` and `PCbuild/` isolate Windows-specific C sources and Visual Studio `.vcxproj` build graphs; `Mac/` isolates macOS framework bundles; `Platforms/` houses mobile/embedded target notes; `Misc/` tracks SBOMs (`sbom.spdx.json`), ABI manifests (`stable_abi.toml`), and release notes.
2. **Architectural principle worth learning:** Platform-specific hosts belong behind explicit adapter boundaries (`peacock/platforms/`) rather than polluting the compiler or VM with platform conditionals. Unsupported or unverified platform targets must be documented with their exact SDK/hardware prerequisites rather than stubbed with fake claims.
3. **Application to PEACOCK:** `peacock/platforms/{base,headless,web,server}.py` implement the `Frame`/`Backend` presentation contract driven by `graphics.present(canvas)`, while `website/site.pac` and `vercel.json` provide the static web application pipeline.
4. **What must be redesigned for PEACOCK:** Frame presentation from `.pac` requires the explicit `ui` capability and an attached host backend (`--present DIR` or `--serve PORT`), failing cleanly with `PE4006` when no host backend is attached.
5. **What is independently implemented:** `peacock/platforms/{base,headless,web,server}.py` and `website/site.pac`.
6. **Necessary OS/platform interfaces:** `http.server` / TCP sockets for `ServerBackend`, browser HTML/CSS/PNG rendering for `WebBackend` and `website/site.pac`. Android (SDK/NDK), iOS (macOS/Xcode), desktop windowing, and GPU/WASM backends remain unimplemented and honestly documented in [docs/platforms/README.md](../docs/platforms/README.md).
7. **Verification tests:** `tests/frontend/test_platforms.py`, `tests/integration/test_presentation.py`, `tests/integration/test_website.py`.

### 2.8 `Lib/test/` and `.github/workflows/` (Regression Testing & Continuous Integration)

1. **Responsibility in CPython:** `Lib/test/` contains 520 regression test modules run via `regrtest`, gated by `.github/workflows/build.yml`, `lint.yml`, and sanitizer/fuzz workflows.
2. **Architectural principle worth learning:** Every language feature, bug fix, security boundary, documentation link and self-hosting increment must be gated by automated positive and negative tests in CI.
3. **Application to PEACOCK:** `tests/` organises 512+ `unittest` cases across `compiler/`, `ai/`, `frontend/`, `security/`, `integration/`, `unit/`, and `benchmarks/`, automated in `.github/workflows/python-package.yml`.
4. **What must be redesigned for PEACOCK:** In addition to unit tests, PEACOCK runs differential parser AST-digest parity tests, differential semantic-shadow VM probes, deterministic fuzz smoke gates, documentation citation/link verification, and full `.pac` website export verification in CI.
5. **What is independently implemented:** All test suites under `tests/` and the deterministic fuzzers in `peacock/fuzzing.py`.
6. **Necessary OS/platform interfaces:** GitHub Actions runner (`ubuntu-latest`, Python 3.11).
7. **Verification tests:** `./bin/peacock test` and `.github/workflows/python-package.yml`.
