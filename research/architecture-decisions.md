# Architecture decisions

Format: **Context → Decision → Alternatives → Consequences → Reversal trigger.**
Accepted ADRs are not rewritten; a later ADR supersedes an earlier one. Status at
the 2026-10-17 checkpoint is stated per decision.

---

## ADR-0001 — Build the first toolchain in Python, behind a strict boundary

**Status:** Accepted, active. Superseded only by the self-hosting fixed point.

**Context.** A self-hosted compiler cannot exist before the language and runtime.
The project starts from an empty repository with no native compiler toolchain
available (no LLVM, no clang/rustc in the build environment) and a zero budget.

**Decision.** Implement the first lexer, parser, analyser, IR, emitter and VM in
Python 3.11 using only the standard library. Confine Python to the language
implementation and host services; never translate `.सूत्र` to Python; define
language semantics independently (e.g., integer division is specified, not
inherited). Document the staged replacement of each compiler stage in
`docs/compiler/bootstrap.md`.

**Alternatives.** (a) Write the compiler in C or Rust: no toolchain and far
slower iteration. (b) Implement an interpreter in another language first: the
same bootstrap problem. (c) Transpile to an existing language: explicitly
forbidden by the project constraints and dishonest as a language claim.

**Consequences.** Rapid iteration and testability; slow execution; Python
semantics/limits leak into diagnostics and performance. Mitigated by
specification, differential tests and a documented self-hosting plan.

**Reversal trigger.** Stage 6 fixed point (two PEACOCK-built compiler generations
produce identical images and pass the suite). Then Python leaves the build path.

---

## ADR-0002 — `.सूत्र` is the only canonical source extension

**Status:** Accepted.

**Context.** Early drafts considered `.pk` and `.peacock`. The user requires a
single canonical extension and explicit rejection of the others.

**Decision.** `.सूत्र` is canonical. `.बीज` is compiled bytecode; `.ज्ञान` is a
serialised model. The CLI rejects `.pk` and `.peacock` with exit 2 and a message
naming `.सूत्र`. Linguist metadata maps only `.सूत्र`.

**Alternatives.** Accept aliases for convenience — rejected: ambiguous language
detection and dishonest file-extension claims.

**Consequences.** One extension to document; `.सूत्र` collides with unrelated
formats/tools (proxy auto-config, other languages), which is noted in the
Linguist submission risks.

**Reversal trigger.** Only a user decision; would require updating the spec, CLI,
tests, docs and Linguist metadata together.

---

## ADR-0003 — Linear typed PIR, stack-machine bytecode in a JSON container

**Status:** Accepted.

**Context.** The first VM must be simple to verify, inspect and implement in
PEACOCK later. Optimisation ambitions are modest.

**Decision.** Use a linear, typed IR with numbered slots and temporaries.
Emit a stack-machine bytecode. Store the image as canonical JSON inside a `.बीज`
container with a format version and SHA-256 digest. Verify the image structurally
before execution, independently of the emitter.

**Alternatives.** (a) SSA-based IR with phi nodes: more optimisation power, much
more machinery. (b) Binary encoding: smaller/faster to load but harder to inspect
and version at this stage. (c) Register bytecode: faster dispatch, harder
verification and codegen.

**Consequences.** Human-inspectable artifacts, easy disassembly, deterministic
emission; larger files and slower parsing; no register allocation.

**Reversal trigger.** A native backend or a > 10× artifact-size complaint, with a
versioned format and migration tool.

---

## ADR-0004 — Checked 64-bit integers and binary64 floats

**Status:** Accepted.

**Context.** Silent wraparound and host-language arithmetic are common sources of
non-portable language semantics.

**Decision.** Integers are signed 64-bit with checked addition, subtraction,
multiplication, division, remainder and negation; overflow raises a catchable
fault. Division truncates toward zero; remainder takes the dividend's sign.
Floats are IEEE-754 binary64; no implicit int/float coercion in operators.

**Alternatives.** Wrapping arithmetic (fast, surprising); arbitrary precision
(safe, slow, hard to implement in PEACOCK later); host semantics (non-portable).

**Consequences.** Predictable cross-platform behaviour and clear diagnostics;
slower arithmetic; explicit conversions.

**Reversal trigger.** A portable arbitrary-precision integer design with a
measured acceptable cost, or a native backend that preserves checked semantics.

---

## ADR-0005 — Three-layer capability enforcement with two capabilities

**Status:** Accepted.

**Context.** The language executes untrusted programs and must not grant ambient
authority. A single check is easy to bypass or misconfigure.

**Decision.** Require (1) a `capability` declaration in the calling function,
(2) a VM check against the frame's declaration and the host grant, and (3) a
host policy that resolves paths and enforces budgets. v0.1 exposes `compute` and
`fs`. Denials are catchable but grant nothing; panics and resource-limit failures
are not catchable.

**Alternatives.** Grants only (ambient authority); declarations only (no host
authority check); full object-capability system (too large for 0.1); OS sandbox
only (unavailable portably).

**Consequences.** Defence in depth and explicit authority; coarse granularity
(see OQ-004); capability declarations are not inherited by callees.

**Reversal trigger.** A real application corpus demonstrates over-granting, or a
kernel/CHERI-style host makes a finer model enforceable.

---

## ADR-0006 — Rely on host memory management; no language GC in 0.1

**Status:** Accepted.

**Context.** Writing a collector before the value model and native ABI are stable
would freeze the wrong design.

**Decision.** Python owns memory. Document that cycles are not collected and that
memory is bounded by host/process limits and tensor/canvas budgets. Do not claim
RAII, deterministic destruction or leak-freedom.

**Alternatives.** Reference counting with cycles (still needs a cycle collector);
a tracing GC now (large, premature); arena allocation (restrictive for lists).

**Consequences.** Simple implementation; unbounded memory for cyclic structures;
a native runtime will need a real design (see [wilson1992gc], [jones2011gc]).

**Reversal trigger.** Native backend or a measured memory failure within resource
budgets; then specify a GC with roots, write barriers and finalisation rules.

---

## ADR-0007 — Pure-Python tensor engine with flat storage

**Status:** Accepted.

**Context.** NumPy/PyTorch are forbidden as core dependencies; a zero-budget
machine without GPU must still train small models.

**Decision.** Implement tensors as a flat Python list plus a shape tuple, with
explicit broadcasting, checked shapes, Float32/Float64/Int32/Bool dtypes, and
rank-2 matmul. No external numerical library.

**Alternatives.** `array`/`memoryview` (faster, deferred — OQ-006); C extension
(no toolchain, violates the dependency rule for the core); vendoring a numerical
library (forbidden).

**Consequences.** Correct and inspectable but slow; 48×48 matmul is ~27 MFLOP/s;
memory per element is high. This is the main performance bottleneck.

**Reversal trigger.** OQ-006 shows an API-compatible flat-buffer variant with
≥ 1.5× matmul improvement and no semantic change.

---

## ADR-0008 — Tape-based reverse-mode autodiff

**Status:** Accepted.

**Context.** Training requires gradients; forward-mode is inefficient for the
many-input/one-output case typical of loss minimisation.

**Decision.** Record a backward closure per differentiable op, topologically sort
on `backward()`, accumulate gradients, require an explicit seed for non-scalar
outputs. No forward mode, checkpointing or higher-order derivatives.

**Alternatives.** Source transformation (needs a differentiable IR, not yet);
operator overloading with a static graph (harder debugging); forward mode only
(wrong complexity for training).

**Consequences.** Simple, debuggable, eager; activation memory grows with graph
size (OQ-002); slower than fused kernels.

**Reversal trigger.** Memory measurement exceeds budget at target model size, or
a differentiable-IR backend replaces the tape.

---

## ADR-0009 — Float32 storage, binary64 arithmetic

**Status:** Accepted.

**Context.** Users expect Float32 tensors; implementing Float32 arithmetic in
Python requires either rounding every intermediate (slow, inaccurate) or using
`struct`/`array` tricks.

**Decision.** Quantise stored values to Float32; perform elementwise and matmul
accumulation in binary64, then round results on storage. Document that this is
not bit-identical to native Float32 kernels.

**Alternatives.** True Float32 intermediates (simulated; much slower); Float64
storage only (more memory, surprising for ML users); no rounding (dtype becomes
decorative).

**Consequences.** Stable gradients and simple code; deviation from native
libraries; gradient-check tolerances are chosen accordingly. See OQ-003.

**Reversal trigger.** A native kernel path with genuine Float32 semantics, or a
demonstrated accuracy problem in a real workload.

---

## ADR-0010 — Linear-light colour with Oklab interpolation

**Status:** Accepted.

**Context.** Naive sRGB interpolation produces dark, muddy gradients; accessibility
requires luminance-aware contrast.

**Decision.** Store linear-light RGB and alpha; convert to sRGB/XYZ/Lab/Oklab/
Oklch on demand; interpolate gradients in Oklab by default; use WCAG 2.x relative
luminance for contrast; clip out-of-gamut values only at the boundary.

**Alternatives.** Gamma-space interpolation (bad midpoint); CIELAB (less uniform
for blues, slower); HSL (not perceptual); Oklch interpolation (better hue control,
planned).

**Consequences.** Better gradients and contrast reasoning; conversion cost;
gamut clipping is not a full colour-management solution. No ICC profiles.

**Reversal trigger.** A colour-appearance requirement that Oklab cannot satisfy, or
user evidence that default Oklab gradients are undesirable.

---

## ADR-0011 — Custom PNG codec over stdlib zlib

**Status:** Accepted.

**Context.** The project needs image output without third-party libraries.

**Decision.** Implement RGBA8 non-interlaced PNG encoding/decoding with filter 0,
explicit IHDR/IDAT/IEND framing, CRC validation and expected-size checks.
Use `zlib` for the DEFLATE stream.

**Alternatives.** BMP/PPM (trivial but poor ecosystem support); pure-Python
DEFLATE (slow, error-prone); Pillow (forbidden dependency).

**Consequences.** Small, auditable, portable; no palette/grayscale/interlace;
encode time dominated by zlib and the Python loop.

**Reversal trigger.** A need for lossy formats or ICC profiles, which would be a
different codec and a spec change.

---

## ADR-0012 — Hand-written lexer and recursive-descent parser

**Status:** Accepted.

**Context.** The project must own its language definition and produce excellent
diagnostics; parser generators add a dependency and obscure recovery.

**Decision.** Hand-written lexer (no regular expressions) and recursive-descent
parser with precedence climbing, explicit spans, synchronisation-based recovery
and stable diagnostic codes.

**Alternatives.** PLY/ANTLR/lark (third-party), PEG generator (dependency,
indirect control over diagnostics), Pratt parser for everything (equivalent for
expressions; current approach is precedence climbing).

**Consequences.** Full control, testable recovery; more code to maintain; parser
must be ported to PEACOCK later.

**Reversal trigger.** Grammar growth makes maintenance pathological; even then,
prefer a hand-written parser in PEACOCK.

---

## ADR-0013 — Zero third-party runtime dependencies

**Status:** Accepted.

**Context.** Reproducibility, licensing clarity, security auditability and the
zero-budget constraint all favour a small dependency surface.

**Decision.** The bootstrap uses only the CPython standard library. No NumPy,
PyTorch, TensorFlow, JAX, LLVM, MLIR, Node, Rust crates or UI frameworks in the
core. External code is not vendored.

**Alternatives.** Use NumPy for speed (forbidden as core and undermines the
independent-engine claim); use a parser generator; use a web framework.

**Consequences.** Slower performance and more code; easy installation; clear
provenance. `zlib`, `hashlib`, `json`, `http.server` are host capabilities, not
PEACOCK implementations.

**Reversal trigger.** None for the core. Optional developer tooling may use
dependencies if clearly separated and documented.

---

## ADR-0014 — Platform presentation as host libraries, not VM natives

**Status:** Superseded in part by ADR-0021 (the frame-push native now exists);
the "backends are host objects" part still stands.

**Context.** The VM must not depend on a window system, and mobile/web hosts do
not exist yet Synchronous native calls from the VM would freeze an ABI before the
frame model is stable.

**Decision.** Implement headless, web and server backends as Python host
libraries that accept a `Canvas` frame. Do not expose a `graphics.present` native
yet. Document that programs write PNGs directly and do not stream frames.

**Alternatives.** Add a `present` native now (premature ABI, untestable on
mobile); embed a browser (forbidden / impractical); ignore presentation (fails
the deliverable).

**Consequences.** Tested adapters and an honest limitation; no live interactive
demo from `.सूत्र`; frame loop is roadmap phase 7.

**Reversal trigger.** A stable frame/present ABI designed with at least two hosts
(desktop + web), after which a native can be added.

---

## ADR-0015 — Benchmarks characterise this implementation only

**Status:** Accepted.

**Context.** Benchmark tables invite misleading comparisons, especially for a
Python bootstrap.

**Decision.** The harness records environment and medians, and every report must
state that results describe this reference implementation. No comparison with
other languages/frameworks; no marketing claims from microbenchmarks. Methodology
is documented in `research/benchmark-methodology.md`.

**Alternatives.** Comparative benchmarking (requires equivalent workloads,
hardware and statistical rigour — out of scope); no benchmarks (loses regression
signal).

**Consequences.** Honest but less impressive numbers; benchmarks remain useful for
regressions and bottleneck finding.

**Reversal trigger.** A dedicated, pre-registered comparison study with identical
workloads and hardware, reviewed independently.

---

## ADR-0016 — Prepare Linguist support, do not claim recognition

**Status:** Accepted.

**Context.** GitHub language recognition requires an upstream contribution and
real-world usage; it cannot be granted locally.

**Decision.** Prepare the language entry, TextMate grammar, samples and logo in
`linguist/`, document the submission checklist, and state in README/STATUS that
recognition is **not** granted.

**Alternatives.** Submit immediately (premature, likely rejected); skip Linguist
(loses tooling support).

**Consequences.** Editor highlighting locally; no GitHub language bar. `.सूत्र`
ambiguity remains.

**Reversal trigger.** Upstream PR merged; then update claims and verify
highlighting on a real repository.

---

## ADR-0017 — Versioned `.ज्ञान` model format; quantisation is analysis-only

**Status:** Accepted.

**Context.** Models must be saved without pickle (unsafe, non-portable) and
quantisation is often claimed without executable support.

**Decision.** Store a JSON header (format, version, architecture, shapes, dtype,
metadata, digest) plus a raw Float32 payload. Loading validates sizes and digest.
Provide int8 quantisation and a size/error report, but do not claim quantised
models are executable.

**Alternatives.** Pickle (unsafe); NumPy `.npz` (dependency); ONNX (large external
spec and no exporter); no persistence (fails training/reporting workflow).

**Consequences.** Safe, inspectable, portable; large files; no quantised inference;
format is project-specific.

**Reversal trigger.** A quantised runtime or interoperability requirement, which
would need a new format version and migration.

---

## ADR-0018 — Deterministic fuzzing with recorded seeds

**Status:** Accepted.

**Context.** Crash-freedom claims are easy to make and hard to support. Random
fuzzing without seeds is not reproducible.

**Decision.** Ship four deterministic fuzzers (lexer, parser, artifact, model)
driven by a seeded PRNG; record seed, iterations, handled/failed counts in JSON;
exit 5 on a crash. Describe results as smoke testing, not coverage.

**Alternatives.** Hypothesis/Atheris (third-party dependency, better coverage);
coverage-guided libFuzzer (no native toolchain); no fuzzing.

**Consequences.** Reproducible smoke tests; unknown coverage (OQ-017); no
minimisation or corpus evolution.

**Reversal trigger.** A defect escaped the deterministic corpus, or coverage
measurement shows a critical gap; then add mutation-based generation first.

---

## ADR-0019 — Uncatchable panic and resource-limit failures

**Status:** Accepted.

**Context.** If a program can catch a resource-limit or panic signal, it can
swallow the condition and continue with corrupted assumptions (e.g., an
out-of-memory state). Catching capability denial is different: denial is a normal
authorisation outcome and must not grant authority.

**Decision.** `panic` raises `PanicError` (PE4011) and resource-limit violations
raise `ResourceLimitError` (PE4003); both bypass `try/catch`. Capability denial
(PE4001) and ordinary faults (PE4002/PE4004) are catchable, but a caught denial
does not perform the operation. The VM unwinds past handlers for uncatchable
errors.

**Alternatives.** Catchable panics (familiar but unsafe); process abort (not
testable in-process); distinct syntax (larger language change).

**Consequences.** Clear failure semantics; tests pin the behaviour; programs
cannot gracefully clean up host state after a limit error (there is no finaliser
mechanism yet).

**Reversal trigger.** A resource-management model with guaranteed cleanup that
does not allow swallowing the condition.

---

## ADR-0020 — No concurrency, async or parallelism in 0.1

**Status:** Accepted.

**Context.** Data races and scheduling semantics multiply implementation and
verification cost. The target machine has 2 vCPUs and no GPU.

**Decision.** The VM is single-threaded and deterministic. No threads, async
functions, promises or parallel loops. Training and rendering run synchronously.

**Alternatives.** Green threads (large runtime work); OS threads (races, non-
determinism); process-level parallelism (host-specific).

**Consequences.** Simple semantics and reproducible results; no use of the second
vCPU; long renders block.

**Reversal trigger.** A specified concurrency model with memory ordering, or
process-based parallelism exposed as a host capability with no shared state.

---

## ADR-0021 — Presentation is a capability-gated frame push to a host-attached backend

**Status:** Accepted.

**Context.** ADR-0014 deliberately deferred a presentation native until the frame
contract was stable and at least two hosts existed. The headless, static-web and
HTTP backends now share a `Frame`/`Backend` contract, and a language-level
presentation path is needed so `.सूत्र` programs can display output without
importing host code. Input, frame clocks and windowing remain unimplemented, so
the ABI must not presuppose them.

**Decision.**

1. Add `graphics.present(canvas) -> Unit` with a new capability `ui`.
2. The VM passes the canvas to `HostPolicy.present`, which requires the `ui`
   grant and forwards it to an optional `presenter` callable. The VM does not
   import `peacock/platforms`.
3. A granted capability with no attached backend is `PE4006`, distinct from a
   capability denial (`PE4001`). Backend exceptions are wrapped as `PE5003`
   host errors.
4. The CLI exposes `--present DIR`, attaching a `WebBackend`. Embedding hosts may
   attach any object with `present(canvas)` (including `ServerBackend`).
5. The canvas is not consumed or mutated; a program may present repeatedly.
   There is no input, vsync or frame clock in this version.

**Alternatives.** (a) Keep presentation as Python-only library use — fails the
deliverable and hides the contract from the language. (b) Reuse the `fs`
capability because a backend writes files — wrong for server/window hosts and
would over-grant file authority. (c) Pass a function pointer or host object into
the language — no first-class functions, and it would leak host structure.
(d) Add a full UI toolkit and window system now — far beyond the verified scope.

**Consequences.** A real, testable program-to-host frame path; three backends can
share one native; presentation authority is explicit and separate from file
authority. The ABI is push-only, so animation is a program loop and the CLI
cannot serve live frames during a run (only after each present call writes a
file). A future event/clock ABI will need a versioned extension, not a breaking
change to this native.

**Reversal trigger.** A richer host protocol (events, resize, multiple windows)
that cannot be expressed by an attached backend, or evidence that `ui` should be
split into finer capabilities.

---

## ADR-0022 — One canonical Sanskrit source surface over stable internal IDs

**Status:** Accepted; supersedes the English source spellings shown in earlier
ADRs, but not their bytecode, host-policy, or capability-security decisions.

**Context.** Renaming only the source extension would leave an English language
with Sanskrit filenames. Conversely, renaming every serialized key and opcode
would break verified artifacts and entangle a source-language decision with the
VM/container ABI. Accepting both English and Sanskrit reserved words would create
two dialects, ambiguous documentation, and permanent compatibility pressure.
Unicode Sanskrit also requires combining-mark-aware identifiers and a deliberate
numeric-literal policy.

**Decision.**

1. `peacock/sanskrit.py` is the single auditable inventory for reserved source
   words, native types/functions, capabilities, model/training options, and
   algorithm enumeration values. Sanskrit source is canonicalised once in the
   lexer to stable internal identifiers.
2. Source identifiers use NFC and Unicode letters, decimal digits, and combining
   marks. Decimal literals accept Unicode decimal digits, including Devanagari;
   punctuation and radix prefixes stay explicit and deterministic.
3. Withdrawn English reserved words are rejected with PE1007 and a native
   replacement hint. Arbitrary non-reserved user identifiers are not translated.
4. Native source displays, semantic/runtime diagnostics, stack traces, human
   audit, and disassembly render through the reverse vocabulary. Bytecode
   opcodes, artifact keys, model parameter keys, host checks, and explicitly
   documented tooling JSON may retain stable internal IDs.
5. `.सूत्र`, `.बीज`, and `.ज्ञान` are the canonical source, bytecode, and model
   extensions. Their container formats remain version 1; newly produced metadata
   identifies language 0.2. The package/toolchain version is 0.2.0.
6. Editor/Linguist grammars are generated from compiler vocabulary and checked
   for freshness. The normative EBNF, native literature document, examples,
   self-host sources, website, and tests migrate together.
7. Pāṇinian sources inspire exact vocabulary, scoped rules, ordered
   correspondence, and explicit conflict resolution. They do not add natural-
   language sandhi, probabilistic tokenisation, morphology, or an AGI capability.

**Alternatives.** (a) A superficial extension rename — rejected as incomplete.
(b) Rewrite all internal names and artifact keys — unnecessary ABI breakage.
(c) Accept English aliases indefinitely — rejected as a second source dialect.
(d) Translate prose or identifiers with an AI model — non-deterministic and
unnecessary. (e) Add Sanskrit NLP to the lexer — conflicts with reproducible,
offline compilation and evidence that sandhi splitting can be non-unique.

**Consequences.** Existing English source requires a real migration, while the
compiler IR, VM, verifier, and storage formats remain substantially stable.
Every reserved-word change now has one review point and must update generated
grammars and documentation. Programmers see one native vocabulary across source,
errors, and native values. The repository has stronger Unicode and documentation
regressions. Local Linguist metadata still cannot guarantee upstream GitHub
recognition, and the native AI engine remains a small tested substrate rather
than AGI.

**Reversal trigger.** A versioned language proposal demonstrating a concrete
need for multilingual reserved aliases or a different canonical lexical policy,
with corresponding artifact, editor, diagnostic, and compatibility tests. No
alias should be introduced ad hoc.
