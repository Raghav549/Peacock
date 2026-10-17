# PEACOCK Roadmap

This roadmap is ordered by dependency, not by excitement. A phase is complete
only when its acceptance criteria are backed by tests in this repository. Phase
statuses are updated in [STATUS.md](STATUS.md); this file defines the plan.

Legend: **done**, **partial**, **planned**, **blocked** (external prerequisite).

---

## Phase 0 — Foundations — **done**

Deliverables: repository structure, MIT licence, README with honest status,
specification skeleton, architecture, contributing/security policies, CLI entry
point, test harness.

Acceptance criteria:

* a clean checkout runs `./bin/peacock version` without third-party packages;
* documentation identifies unimplemented areas and the bootstrap boundary;
* tests can be run with one documented command.

## Phase 1 — Language core — **done** (subset)

Deliverables: hand-written lexer, recursive-descent parser, AST, diagnostic
system, static type model, semantic analyser with scopes and definite-return
checks, capability checking, positive/negative tests for every accepted
construct.

Acceptance criteria:

* every grammar construct in `SPECIFICATION.md` has a positive test and at least
  one negative/diagnostic test;
* malformed input never crashes the lexer/parser (fuzzer, 1,000+ inputs);
* spans and caret diagnostics are correct on multiline input;
* reserved keywords fail with targeted messages.

Remaining for a future language version: user modules, generics, enums, pattern
matching, closures, traits, concurrency.

## Phase 2 — Compiler and bytecode — **done**

Deliverables: typed PIR, verifier, constant folding/branch folding/DCE/peephole
optimiser, bytecode emitter, image verifier, `.pkb` container with SHA-256,
disassembler.

Acceptance criteria:

* optimised and unoptimised programs produce identical observable behaviour;
* the verifier rejects bad registers, jump targets, arities, unknown natives and
  unknown capabilities;
* artifact round-trips are byte-identical and tampering is detected;
* compilation is deterministic.

## Phase 3 — Runtime and security — **done** (subset)

Deliverables: stack VM, checked arithmetic, list/string/tensor operations, struct
values, try/catch, capability gate, resource budgets, sandboxed filesystem
(including grant-gated `fs.create_dir`), fuzzers and security regression suite.

Acceptance criteria:

* every `try/catch` path is tested, including rethrow and uncatchable panics;
* `..`, absolute paths, symlinks, NUL bytes and oversized files are rejected;
* the host can deny declared capabilities and the denial grants nothing;
* step/depth/output/tensor/dataset/epoch limits are enforced;
* fuzzers find no crash in lexer/parser/artifact/model loaders across seeds.

Remaining: process-level sandbox hardening (seccomp/landlock or WASM isolation),
memory accounting and collection, deterministic scheduling.

## Phase 4 — Intelligence engine — **done** (small models)

Deliverables: tensor engine with broadcasting and reverse-mode autodiff, Dense
layers, SGD/Adam, cross-entropy/MSE, XOR and spiral datasets, training reports,
evaluation metrics, `.pkm` serialisation and int8 quantisation.

Acceptance criteria:

* finite-difference gradient checks pass for representative graphs;
* XOR reaches accuracy 1.0 and loss < 0.01 with a recorded configuration;
* model round-trips preserve predictions;
* corrupt/truncated models are rejected.

Planned: convolution/attention layers, embedding/sequence APIs, data loading,
mixed precision, larger models, CPU performance work, GPU backends (blocked on
interface design and hardware availability).

## Phase 5 — Frontend, colour and UI — **partial**

Delivered: perceptual colour pipeline (sRGB/XYZ/CIELAB/Oklab/Oklch, WCAG,
palettes, mixing), software RGBA canvas with anti-aliasing, gradients, glow,
aurora, PNG encode/decode and flex layout. A separate app-specific static
website (`website/site.pac`) now defines twelve routes/components and exports
semantic HTML, responsive CSS and SVG through the actual CLI/compiler/VM; it is
covered by route/link/structure/source/CSS integration checks. It is not a
reusable UI toolkit or the frame `WebBackend`.

Acceptance criteria met: colour reference values, palette determinism, PNG
round-trip and CRC rejection, canvas size limits, layout arithmetic, and the
website export's tested static routes and structural properties.

Still required before "UI toolkit": a reusable general-purpose widget system,
text measurement/shaping, interactive input/event routing, integration with
native accessibility APIs, theming and image decoding beyond our PNG. Browser
layout uses HTML/CSS; there is no general PEACOCK browser event/runtime.

## Phase 6 — Motion and physics — **partial**

Delivered: named easings, cubic Bézier solver, damped springs, keyframe
timelines with numeric/colour interpolation, row/column layout, deterministic
2-D AABB physics.

Still required: animation composition/cancellation, gesture-driven motion,
constraint solver, 3-D rigid bodies, collision broadphase, particles, and
integration with a real frame scheduler.

## Phase 7 — Platform hosts — **partial**

Delivered: platform-neutral `Frame`/`Backend` contract; headless PNG host;
static web viewer; stdlib HTTP frame server; and `graphics.present(canvas)` with
the `ui` capability, which drives an attached backend from a real `.pac` program
(`--present DIR` attaches `WebBackend`; `--serve PORT` attaches `ServerBackend`
with a `--linger` window). Frames are written per present call, `latest.png`/
`index.html` are updated, and `manifest.json` is written on close.

Acceptance criteria met: PNG frames served over HTTP, viewer contains no script,
health route works, malformed routes fail cleanly; a program presents four frames
through the real VM and the manifest records all four. The independently
PEACOCK-authored `website/site.pac` exporter also builds twelve static HTML/CSS
routes, but is not a platform runtime or an interactive UI system (see
[website/README.md](website/README.md)).

Still planned:

| Host | Status | Prerequisite |
|---|---|---|
| Headless/server (Linux) | working; reachable from `.pac` via `--serve` | — |
| Static web viewer | working and reachable from `.pac` via `--present` | — |
| Desktop window shell | planned | windowing toolkit or OS API bindings |
| Android | not implemented | Android SDK/NDK, JNI bridge, packaging |
| iOS | **blocked** | macOS + Xcode toolchain (unavailable here) |
| WASM runtime | planned | bytecode/WASM backend and browser ABI |

No mobile target may be claimed until it builds, installs and runs on a device or
emulator and the result is recorded.

## Phase 8 — Native performance backend — **planned**

Deliverables: typed value representation, register or closure IR, native codegen
for a verifiable subset, ABI for host calls, benchmarks against the interpreter
on identical workloads.

Acceptance criteria:

* generated code passes the same semantic test suite as the VM;
* the performance report states hardware, compiler, flags and input sizes;
* no benchmark claim is made without a checked-in reproduction command;
* security properties (bounds, capabilities, limits) are preserved.

Blocked on: a compiler toolchain available in the development environment. There
is no `rustc`/`clang`/LLVM here, and PEACOCK does not wrap LLVM for its core.
Writing a small native backend or a WASM emitter from scratch is the intended
path.

## Phase 9 — Self-hosting — **partial**

Delivered: `selfhost/tokenizer.pac` with token parity, and
`selfhost/parser.pac` (1,085 lines) covering the full 0.1 grammar, including
model/training declarations. The parser produces a canonical AST digest that is
byte-identical to the bootstrap parser on its 14-file core corpus (seven
examples, six Linguist samples and a syntax fixture), plus self-parse. This
increment expands `selfhost/type_model.pac` into an executable PEACOCK kernel for recursive type
relations, expression result rules, lexical bindings, declarations, assignments,
user-function signatures/calls, conditions, returns and iterable checks.
`compile_source(..., semantic_mode="shadow")` and opt-in CLI `--semantic-shadow`
flags translate supported typed-AST facts into generated PEACOCK probes, execute
them in the VM, and compare against the Python oracle. Regressions cover valid
and invalid inputs, selected diagnostic equality, the `.pac` corpus and
ErrorType iterable recovery. Python semantic analysis remains authoritative;
the kernel does not generate diagnostics, misses several semantic domains and
is not a replacement analyser.

Stages:

1. tokenizer — **done**;
2. parser + AST — **partial**: full-grammar syntax and AST-digest parity are
   done; error recovery, `PE2xxx` diagnostic/span parity and a typed AST are not;
3. semantic analyser/type checker — **shadow prototype**: selected types,
   expressions, scope/name/assignment/call/return/condition/iterable rules plus
   structs, struct fields, built-in properties, methods and diagnostic code
   mappings are probed (74 built-in assertions); native overloads, model/training
   declarations and full diagnostic emission remain Python;
4. IR and bytecode emitter — **verification kernel prototype** (`selfhost/ir_model.pac`,
   15 assertions covering PIR register def-before-use, slot bounds, duplicate
   labels, jump targets, balanced `try_begin`/`try_end` scopes, constant folding
   and bytecode jump bounds); full AST→IR lowering in `.pac` remains planned;
5. VM in PEACOCK with a minimal host ABI — planned;
6. fixed point: the PEACOCK compiler compiles itself, and the resulting image
   passes the full suite.

Acceptance criteria for "self-hosting": a reproducible build where stage 1 is
produced by the bootstrap compiler, stage 2 by stage 1, and stage 1/stage 2 agree
on output; the bootstrap is not required to run the tests. Until then, every
document says **not self-hosting**.

## Phase 10 — Ecosystem and research tooling — **planned**

Deliverables: package/module system, formatter, linter, language server, editor
plugins, documentation generator, reproducible experiment runner, dataset and
model registries with licence checks, publication-quality evaluation harness.

AGI research tooling is scoped as infrastructure for experiments (tensor
programs, deterministic runs, evaluation, provenance), **not** as a claim that
PEACOCK is an AGI or that AGI has been achieved. Safety, interpretability and
evaluation work must be documented with negative results and limitations.

Acceptance criteria:

* package installation is deterministic and capability-audited;
* every experiment records seeds, data provenance, code revision and environment;
* no benchmark or capability claim is made without a reproducible artifact.

---

## Cross-cutting dependencies

```
Phase 0 ─► Phase 1 ─► Phase 2 ─► Phase 3 ─┬─► Phase 4 ─► Phase 10
                                     ├─► Phase 5 ─► Phase 6
                                     ├─► Phase 7
                                     ├─► Phase 8 ─► Phase 9
                                     └─► Phase 9
```

Phase 9 depends on a stable language and bytecode format (Phases 1–3). Phase 8
can proceed in parallel with Phase 9 but must not fork semantics. Phase 10 waits
for the packaging and experiment infrastructure that Phases 3–4 make possible.

## Next three priorities

1. **Complete parser-stage parity**: error recovery, bootstrap `PE2xxx`
   diagnostic/span parity on a fixed negative corpus, and a typed AST
   representation; keep the existing parser oracle tests intact.
2. **Close the semantic shadow gap incrementally**: broaden differential edge
   cases and diagnostics while Python remains authoritative, then port the next
   supported semantic domains only behind measured parity gates. Do not promote
   the shadow kernel to production.
3. **Specify the next compiler representation** (AST → typed IR → bytecode) and
   define deterministic differential fixtures before implementing stage 4; the
   existing VM/platform presentation path already works, and native/WASM targets
   remain planned rather than claimed.
