# Repository audit (base snapshot, 2026-10-17)

> **Snapshot note:** the findings and branch/history metadata below describe an
> earlier audit snapshot. The current follow-on verification is recorded at the
> end of this file; `STATUS.md`, `ROADMAP.md` and `DEPENDENCIES.md` are the
> canonical up-to-date component status and migration plan.

## Executive finding

This checkout is substantially more than a proposal: it contains an original, executable PEACOCK language subset, a Python-hosted lexer/parser/type checker/IR/optimiser/bytecode compiler and VM, working CPU tensor/autodiff/training primitives, and a 2D software graphics stack. The `.सूत्र` examples are genuine PEACOCK syntax, not renamed Python. End-to-end execution and a bytecode artifact were verified during this audit. It is nevertheless **not an independently bootstrapped/self-hosting implementation**: the production toolchain and supporting engines remain Python. Native platform backends, 3D/GPU/UI framework and broad language features remain absent. Existing documentation is unusually detailed and mostly candid; this audit adds a point-in-time evidence index rather than replacing that documentation.

## Scope and method

Inspected tracked tree, manifests, executable wrappers, source and test layout, compiler/runtime package boundaries, examples, research and platform docs, `.gitattributes`, Linguist proposal, VS Code package, logo files, and available Git history. Ran the project test command, standard-library unittest discovery, and CLI smoke tests. At HEAD, history is a single **grafted** merge commit (`374a75b`); the available clone does not expose meaningful earlier project history or other development branches. The current working branch is `arena/3d38bd9d-peacock`; `main` and `origin/main` resolve to that same base commit. No local changes existed at audit start.

A tracked-file extension count is not a byte-weighted GitHub Linguist computation. The checkout has 80 tracked `.py`, 22 `.सूत्र`, 28 `.md`, one `.tex`-extension count absent (zero tracked TeX), plus small config/assets. The user-provided repository overview is approximately 93.6% Python / 6.4% TeX. The Python share is explained by the actual bootstrap/compiler/runtime/test implementation being Python; `.सूत्र` is genuine but presently a minority of source files. The reported TeX cannot be attributed to any tracked `.tex` file in this snapshot: re-check Linguist's current per-file output on GitHub and inspect any untracked/ignored or subsequently changed files. Neither language statistics nor current Linguist classification were queried from GitHub's repository API during this local audit. `.gitattributes` explicitly labels `.सूत्र` as Peacock and detectable; that repository-local hint is not upstream recognition.

## Subsystem findings

| Subsystem | Honest status | Evidence / limitation |
|---|---|---|
| `.सूत्र` language identity and examples | Working and tested (subset) | `SPECIFICATION.md`; eight `examples/*.सूत्र`; examples compile, several execute. `.pk` and `.peacock` are rejected as source suffixes. |
| Lexer, diagnostics, parser, AST | Working and tested (Python bootstrap) | `peacock/compiler/{lexer,tokens,parser,ast_nodes,diagnostics}.py`; lexical/parser tests; self-host tokenizer and parser parity fixtures. |
| Name resolution, scopes, types, semantic checks | Working and tested (subset) | `semantic.py`, `types.py`; unknown names, invalid types and capabilities have tests. No general generics, inference, modules/imports or advanced type features. |
| IR, optimisation, backend | Working and tested (limited) | Typed linear IR, verifier, optimisation passes, custom bytecode compiler and `.बीज` artifact. No native machine-code/WASM/GPU backend. |
| Runtime | Working and tested (Python VM) | Custom stack VM, checked arithmetic, errors, budgets, host natives; Python process owns memory; no PEACOCK GC. |
| CLI | Working and tested | `run`, `check`, `build`, `disasm`, `audit`, `tokens`, `ast`, `bench`, `fuzz`, `test`, `version`. Audit found `--version` was not accepted although a conventional flag is expected; added an alias and regression test in this change. |
| Module system / stdlib | Partial | Single-file programs, built-in namespaces, flat program value namespace. No user-file imports/package manager. |
| AI / numerical | Working and tested, CPU/small-scale | Pure-Python tensors, broadcasting, rank-2 matmul, reverse-mode autodiff, dense layers, losses/SGD/Adam, small datasets, training, metrics, serialization/quantisation. No GPU, attention/CNN, large-scale training, hardware kernels or training platform. |
| Frontend / graphics | Partial but real | Colour conversions and 2D software rasterizer/PNG, gradients, motion/layout/AABB physics; examples and tests. No interactive UI toolkit, text shaping/accessibility, 3D, GPU, live input/vsync. |
| Security | Partial / best-effort | Static declaration + VM checks + host grants/resource budgets and tests. Host path policy has documented TOCTOU limits; not an OS sandbox or formal guarantee. |
| Targets | Partial | Linux/headless, static web export and HTTP frame presentation adapters have tests. Desktop, Android, iOS and WASM builds absent. iOS requires macOS/Xcode/signing and is not verifiable here. |
| Self-hosting | Partial, not self-hosted | PEACOCK `.सूत्र` tokenizer and full grammar parser are tested for parity; type analysis, IR, bytecode, VM remain Python. No bootstrap compiler compiles itself. |
| Tests / CI | Working locally; CI presence unverified | 490 tests passed using both `./bin/peacock test` and `python -m unittest discover -v`. No workflow files occur in the inspected tree. `pytest` is not installed; project tests use `unittest`. |
| Dependencies | Python 3.11+ stdlib only at runtime | `pyproject.toml`: empty dependencies, setuptools build backend. No NumPy/PyTorch/TensorFlow/LLVM or UI framework. Packaging/build installation itself was not tested. |
| Research | Present; use with source verification | 162 bibliography entries, literature review, open questions, ADRs and benchmark methodology are documented. Research README itself says bibliography identifiers were not machine-verified and the survey is not comprehensive. |
| Logo | Present and locally verified | `assets/peacock.svg`, `assets/peacock-256.png`, editor icon; test decodes a 256×256 transparent PNG. SVG was not independently rendered in this audit. |
| VS Code tooling | Prepared, unpublished | TextMate grammar, file config and package metadata exist; no LSP, diagnostics integration, publication or editor integration test. |
| GitHub Linguist | Prepared only; not eligible/accepted | Proposed language entry, grammar, samples exist. No Linguist source checkout/official classifier tests or upstream PR. The current upstream contribution guide requires evidence of widespread usage (2,000 files/year for common extensions, 200 for one-per-repo files, across a reasonable distribution), so the new/hobby-language proposal currently lacks evident acceptance evidence. |

## Build and runtime evidence

Commands run from the repository root:

- `python -m pytest -q` — **not run**: environment has no `pytest` module (`No module named pytest`).
- `python -m unittest discover -v` — **PASS, 490 tests** in 39.924 s.
- `./bin/peacock test` — **PASS, 490 tests** in 40.248 s.
- `./bin/peacock version` — reports PEACOCK AI 0.1.0, `.सूत्र`, `.बीज`, Python 3.11.2 and explicitly “NOT self-hosting”.
- `./bin/peacock check examples/hello.सूत्र` — **PASS**, 1 function, 6 instructions.
- `./bin/peacock run examples/hello.सूत्र` — **PASS**, prints `Hello from PEACOCK`.
- `./bin/peacock build examples/hello.सूत्र -o <temporary .बीज>` followed by `run` of the artifact — **PASS**, 598-byte image, checksum printed, same expected output.
- `./bin/peacock --version` — **FAIL before fix** (`unknown command '--version'`). Fixed in this change and added a regression test; post-fix targeted verification is recorded in the session report.

The test suite includes lexer/parser/semantic/type/IR/VM cases; invalid syntax, unknown identifiers, runtime failures, security checks; examples; tensor gradients and training; graphics/colour/platform and documentation checks. The above is observed output, not a blanket security or production-readiness assertion.

## Project history and maintenance context

The available Git object graph is shallow/grafted at `374a75b`, so this audit cannot infer how features evolved or validate prior claims from earlier commits. Only `arena/3d38bd9d-peacock`, `main`, and `origin/main` were visible; this repository view shows no additional local feature branches. There is no `.github/workflows` directory in the inspected tracked file list. CI coverage, PR acceptance, real user uptake and hosted language statistics therefore remain unverified.

## Linguist investigation

The local metadata proposes `Peacock`, `.सूत्र`, `source.peacock`, programming type and an Ace `text` mode, with a TextMate-compatible grammar. The grammar and VS Code copy are JSON and have consistency tests; the samples compile through the real compiler. The current official [`github-linguist/linguist` contribution guide](https://github.com/github-linguist/linguist/blob/main/CONTRIBUTING.md), inspected 2026-10-17, describes language entry metadata, a licensed grammar added using Linguist's tooling, representative non-tutorial samples, and usage evidence. It currently calls for 2,000 indexed files/year for extensions expected to be used multiple times per repo, or 200 for one-per-repo names, excluding forks, plus reasonable distribution across unique user/repo combinations. `.सूत्र` is not demonstrated here to meet that bar. The upstream language database was not cloned to check all current extension conflicts, and the prepared sample files are project-authored examples, not evidence of independent in-the-wild usage. No remote submission was attempted; upstream recognition is not claimed.

## Files reviewed

Configuration/build: `pyproject.toml`, `.gitignore`, `.gitattributes`, `bin/peacock`, `bin/peacock.cmd`.
Language/implementation: all tracked `.सूत्र` examples/selfhost fixtures plus compiler, runtime, AI, frontend, platform and CLI packages.
Quality/docs: all test modules; README and specification/architecture/status/roadmap/security; docs tree; research review, questions, ADRs, methods and bibliography.
Identity/tooling: `assets/`, `editors/vscode/`, `linguist/`.

## Earlier follow-up migration increment (historical snapshot)

The type-algebra work is no longer only a standalone demonstration: the compiler
API supports opt-in `semantic_mode="shadow"`. After parsing actual source
function/struct declaration annotations, the adapter generates relation checks
and executes them in the `.सूत्र` kernel. Python computes expected assignability
and tensor broadcast outcomes; Python semantic analysis still decides compilation
and diagnostics. Tests compare diagnostics and accept/reject for a small corpus.
This remains experimental relation-level shadow validation, not full semantic
parity, a default CLI mode, or self-hosting. After the bridge and its regression
tests were added, `python -m compileall -q peacock tests` succeeded and
`./bin/peacock test` passed **495 tests** in 39.858 s on 2026-10-17. This is a
new observed result; the earlier 490-test baseline above describes the audit's
initial checkout state.

## Earlier engineering priorities (superseded by the current roadmap)

1. Extend the shadow protocol to compound types and real expression/assignment sites; implement name/scope semantics and typed-AST diagnostics in PEACOCK before considering promotion.
2. Add a lightweight CI matrix running `unittest`, examples, package install/entry point, syntax metadata and reproducible security/fuzz smoke tests.
3. Keep unsupported native/web/mobile/3D/GPU capabilities explicitly unclaimed; improve host boundaries and benchmark/visual test coverage before expanding their promises.

## Current follow-on verification (0.4, 2026-10-22)

This section supersedes the historical snapshots above for the current working
tree on `arena/e6263f04-peacock`, based on merged 0.3 commit
`e1157efaaa5af35d396f8bda91000ed7825059c4`. The complete suite passes **611
tests in 47.223 s, with two environment-dependent skips** (real OpenCL and real
X11). Documentation tests pass 7/7; deterministic fuzzing handles 1,000 lexer,
1,000 parser, 1,000 artifact and 666 model cases without a crash; `git diff
--check` is clean.

The 0.4 tree adds verified `अन्ते` cleanup unwinding and self-host syntax parity;
a deterministic native C executable/shared-library subset with recoverable
embedding faults; bounded LLM/tool agents; CPU and OpenCL tensor operations;
browser/X11 UI events; PEACOCK-owned bounded HTTP servers; and native desktop,
Android and iOS shell sources. The Linux native/desktop paths execute with
VM-identical output. Android/iOS and actual OpenCL/X11 hardware remain
unverified. Native AOT, OpenCL, UI and servers are documented subsets, not
whole-ecosystem completion or production multi-tenancy.

The grammar package still contains 3,983 sūtra texts but only four executable
sandhi rules. Bounded agents are not AGI. Python remains the authoritative
bootstrap; the compiler is not self-hosting. GitHub recognition remains local
preparation, not upstream Linguist acceptance. A pinned CPython inspection at
`ab2c947f435748d2b8e6d4ea550168a4cff473e5` and its remaining capability gaps are
recorded in `docs/CPYTHON_AUDIT.md`. See `STATUS.md` for the current measured
results and `ROADMAP.md` for remaining work.
