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
optimiser, bytecode emitter, image verifier, `.बीज` container with SHA-256,
disassembler.

Acceptance criteria:

* optimised and unoptimised programs produce identical observable behaviour;
* the verifier rejects bad registers, jump targets, arities, unknown natives and
  unknown capabilities;
* artifact round-trips are byte-identical and tampering is detected;
* compilation is deterministic.

## Phase 3 — Runtime and security — **done** (subset)

Deliverables: stack VM, checked arithmetic, list/string/tensor operations, struct
values, try/catch/`अन्ते`, capability gate, resource budgets, sandboxed filesystem
(including grant-gated `सञ्चय.निधिरचना`), fuzzers and security regression suite.

Acceptance criteria:

* every `try/catch` path is tested, including rethrow and uncatchable panics;
* `अन्ते` is tested for normal/error/return/break/continue completion, nesting,
  cleanup supersession and optimised/unoptimised parity;
* `..`, absolute paths, symlinks, NUL bytes and oversized files are rejected;
* the host can deny declared capabilities and the denial grants nothing;
* step/depth/output/tensor/dataset/epoch limits are enforced;
* fuzzers find no crash in lexer/parser/artifact/model loaders across seeds.

Remaining: process-level sandbox hardening (seccomp/landlock or WASM isolation),
memory accounting and collection, deterministic scheduling.

## Phase 4 — Intelligence engine — **done** (small models)

Deliverables: tensor engine with broadcasting and reverse-mode autodiff, Dense
layers, SGD/Adam, cross-entropy/MSE, XOR and spiral datasets, training reports,
evaluation metrics, `.ज्ञान` serialisation and int8 quantisation. Phase 4 also
has a bounded symbolic-agent library: string blackboards, condition/action/
effect rules, positive-cost Dijkstra planning, salience tie-breaking, execution
and traces, gated by `गणना`. A separate bounded LLM/tool loop adds host-configured
providers, JSON schemas, capability checks, redirects disabled and aggregate
budgets, gated by `सञ्जाल`; its default tools are offline grammar/calculator
operations. `gpu.py` adds tested CPU operations and an OpenCL 1.2 implementation
for add/multiply/ReLU/matmul, with no actual-device result in this environment.

Acceptance criteria:

* finite-difference gradient checks pass for representative graphs;
* XOR reaches accuracy 1.0 and loss < 0.01 with a recorded configuration;
* model round-trips preserve predictions;
* corrupt/truncated models are rejected.

Planned: convolution/attention layers, embedding/sequence APIs, data loading,
mixed precision, larger models, CPU performance, device-resident/autodiff GPU
graphs and actual OpenCL hardware CI. Agent follow-up requires cancellable tool
execution, richer host tools, persistent blackboards, plan monitoring and model
quality/safety evaluation; none of that is an AGI claim.

## Phase 5 — Frontend, colour and UI — **partial**

Delivered: perceptual colour pipeline (sRGB/XYZ/CIELAB/Oklab/Oklch, WCAG,
CIEDE2000, weighted/perceptual/polar/approximate-subtractive mixing, gamut
mapping), software RGBA canvas, PNG, flex layout, and a reusable retained UI
library with panels/text/buttons/links, flow/grid layout, hit testing,
accessibility audits and escaped responsive HTML. It now includes bounded event
bindings/queues, bubbling, text/enabled/focus mutation, an interactive browser
host and a native X11 window/event host. A separate app-specific static
website still exports twelve routes through the real toolchain. Phase 5 also
includes CPU 3-D cube/UV-sphere meshes, Euler transforms, perspective,
back-face culling, reciprocal-depth buffering and coloured point lights.

Acceptance criteria met: colour reference values, CIEDE2000 vectors, mixing and
gamut tests, UI layout/hit-test/audit/HTML tests, real browser POST/event
dispatch and headless X11 event-model tests, 3-D geometry/depth/light tests,
real `.सूत्र` UI/3-D exports, PNG round-trip/CRC rejection and website routes.
An actual X11 display was not available, so native-window execution is not yet
recorded as verified.

Still required before a complete interactive UI/3-D platform: text measurement
and complex-script shaping, native accessibility APIs, text-input widgets,
theming, image decoding beyond PNG, smooth mesh normals, textures and GPU 3-D.
Browser layout uses HTML/CSS with a small explicit event/refresh script, not a
general browser PEACOCK runtime. The subtractive colour mode is an approximation,
not spectral paint simulation.

## Phase 6 — Motion and physics — **partial**

Delivered: named easings, cubic Bézier solver, damped springs, keyframe
timelines with numeric/colour interpolation, row/column layout, deterministic
2-D AABB physics.

Still required: animation composition/cancellation, gesture-driven motion,
constraint solver, 3-D rigid bodies, collision broadphase, particles, and
integration with a real frame scheduler.

## Phase 7 — Platform hosts — **partial**

Delivered: platform-neutral `Frame`/`Backend` contract; headless PNG host;
static web viewer; stdlib HTTP frame server; interactive retained-UI browser
host; native X11 window host; PEACOCK-owned bounded synchronous HTTP servers;
and `चित्र.प्रदर्शय`/`दृश्य.प्रदर्शय` with the `दृश्य` capability. Native C
shared-library generation is embedded by an executed Linux desktop shell.
Android Activity/JNI and iOS SwiftUI/Objective-C shell sources are present, but
have not been built on their platform toolchains here.

Acceptance criteria met: PNG frames served over HTTP, viewer contains no script,
health route works, malformed routes fail cleanly; a program presents four frames
through the real VM and the manifest records all four. Real browser/UI POST and
PEACOCK HTTP request/response tests pass; native desktop output matches the VM
byte-for-byte and uses the generated C library without a Python runtime. The independently
PEACOCK-authored `website/site.सूत्र` exporter also builds twelve static HTML/CSS
routes, but is not a platform runtime or an interactive UI system (see
[website/README.md](website/README.md)).

Still planned:

| Host | Status | Prerequisite |
|---|---|---|
| Headless/server (Linux) | working; reachable from `.सूत्र` via `--serve` | — |
| Static web viewer | working and reachable from `.सूत्र` via `--present` | — |
| Interactive UI browser | working; real POST/event test | production auth/TLS if exposed |
| Native X11 window | source and event model tested; display run pending | X11 + `DISPLAY` |
| Native C desktop shell | working on Linux x86-64; VM-identical output | wider AOT opcode coverage |
| Android | Activity/JNI/C sources only here | SDK/NDK build, APK and emulator/device tests |
| iOS | SwiftUI/Objective-C/C sources only here | macOS + Xcode simulator/device/signing tests |
| WASM runtime | planned | bytecode/WASM backend and browser ABI |

No mobile target may be claimed until it builds, installs and runs on a device or
emulator and the result is recorded.

## Phase 8 — Native performance backend — **partial**

Delivered: checked native value representation, deterministic C11 control-flow
codegen for a verified bytecode subset, standalone executables, an embeddable
`peacock_run` shared-library ABI with output callbacks/recoverable faults, and
an executed Linux desktop host. Strict warning builds and eight native AOT tests
cover VM-identical output, deterministic generation, unsupported-opcode rejection
and embedding failures. This is not whole-language AOT or a stable plugin ABI.

Still required: `अन्ते`/general objects/modules and wider native-library parity;
thread-safe/reentrant runtime state; independent memory-management design;
cross-platform builds; and reproducible interpreter/native benchmarks recording
hardware, compiler, flags and input sizes. No performance advantage is claimed
without those measurements.

Acceptance criteria for completion:

* every opcode declared supported passes the same semantic fixtures on VM and
  native backends, optimised and unoptimised;
* the performance report states hardware, compiler, flags and input sizes;
* no benchmark claim is made without a checked-in reproduction command;
* bounds, capabilities and resource limits are preserved, with unsupported
  privileged operations rejected before C compilation.

## Phase 9 — Self-hosting — **partial**

Delivered: `selfhost/tokenizer.सूत्र` with token parity, and
`selfhost/parser.सूत्र` covering the full 0.4 grammar, including
model/training declarations and `अन्ते`. The parser produces a canonical AST digest that is
byte-identical to the bootstrap parser on its 15-file core corpus (seven
examples, six Linguist samples and two syntax fixtures), plus self-parse. This
increment expands `selfhost/type_model.सूत्र` into an executable PEACOCK kernel for recursive type
relations, expression result rules, lexical bindings, declarations, assignments,
user-function signatures/calls, conditions, returns and iterable checks.
`compile_source(..., semantic_mode="shadow")` and opt-in CLI `--semantic-shadow`
flags translate supported typed-AST facts into generated PEACOCK probes, execute
them in the VM, and compare against the Python oracle. Regressions cover valid
and invalid inputs, selected diagnostic equality, the `.सूत्र` corpus and
ErrorType iterable recovery. Python semantic analysis remains authoritative;
the kernel does not generate diagnostics, misses several semantic domains and
is not a replacement analyser.

Stages:

1. tokenizer — **done**;
2. parser + AST — **partial**: full-grammar syntax and AST-digest parity are
   done; error recovery, `PE2xxx` diagnostic/span parity and a typed AST are not;
3. semantic analyser/type checker — **shadow prototype**: selected types,
   expressions, scope/name/assignment/call/return/condition/iterable rules are
   probed; diagnostics, fields/methods, native overloads and model/training
   analysis are not ported; Python remains authoritative;
4. IR and bytecode emitter — planned;
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

## Phase 11 — Sanskrit grammar and connected literature — **partial**

Delivered: an attributed, offline package of all 3,983 Aṣṭādhyāyī sūtra texts;
validated lookup/search, inheritance references and anuvṛtti display; generic
Māheśvara pratyāhāra expansion; four executable vowel-sandhi rules with rule
IDs; coverage reporting; native `.सूत्र` calls and a Sanskrit CLI. Provenance and
the distinction between textual and executable coverage are recorded in
`peacock/vyakarana/data/` and `docs/language/vyakarana.md`.

Still required: a rule representation for environments, transformations and
anuvṛtti; ordered interaction and conflict resolution; derivation traces;
declension, conjugation, samāsa and kāraka; broader sandhi including consonants
and visarga; segmentation with explicit ambiguity; and independently licensed,
validated connected-literature corpora. Catalogue entries for the Mahābhāṣya,
Kāśikāvṛtti, Dhātupāṭha, Gaṇapāṭha, Vākyapadīya and related works are not full
texts or executable semantics.

Acceptance criteria for broader coverage: each rule family cites its source,
has positive and negative derivation tests, reports ambiguity rather than
inventing certainty, and has a published coverage denominator. “Complete
Pāṇini” requires the whole ordered rule system and regression corpus—not merely
3,983 searchable strings.

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
Phase 11 builds on the stable Sanskrit lexer and native-call/capability boundary
from Phases 1–3; it does not wait for self-hosting or native code generation.

## Next priorities

1. **Deepen executable grammar coverage**: design cited rule environments,
   transformations, inheritance and ordered interaction; keep textual and
   executable coverage metrics separate and add derivation regressions first.
2. **Harden interactive UI**: thread-safe tree snapshots, complex-script text
   measurement/shaping, native accessibility and real-display tests without
   weakening static HTML export.
3. **Expand native semantic coverage**: finalization, objects/modules and wider
   natives behind VM/native differential fixtures; make embedded runtime state
   thread-safe before advertising concurrent use, then measure native/VM workloads.
4. **Verify real platforms and accelerators**: Android SDK/emulator, iOS
   simulator/device, X11 display and OpenCL hardware CI; keep source-only and
   skipped results distinct from execution.
5. **Complete parser-stage parity**: error recovery, bootstrap `PE2xxx`
   diagnostic/span parity on a fixed negative corpus, and a typed AST
   representation; keep the existing parser oracle tests intact.
6. **Close the semantic shadow gap incrementally**: broaden differential edge
   cases and diagnostics while Python remains authoritative, then port the next
   supported semantic domains only behind measured parity gates. Do not promote
   the shadow kernel to production.
7. **Build independent packaging/module infrastructure**: deterministic user
   modules, distribution packages and reproducible stage-4 compiler fixtures;
   retain bounded server/agent interfaces rather than claiming production
   multi-tenancy or AGI.
