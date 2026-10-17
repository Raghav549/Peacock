# Open questions

These are research questions for this project, not rhetorical prompts. Each has a
hypothesis, an experiment that can be run on the reference machine (2 vCPU,
3.8 GiB RAM, no GPU), a metric, and a decision rule. Status reflects the
2026-10-17 checkpoint.

Legend: **Open** (no data), **Partial** (data exists but is insufficient),
**Answered** (decision recorded, ADR linked), **Blocked** (needs hardware or a
dependency that is not available).

---

## OQ-001 — Can tensor shapes be checked statically without making the language unusable?

**Why.** `Tensor` types carry a dtype and an optional static shape, and
elementwise/matmul expressions propagate shapes when both operands are known.
Coverage is uneven: many native calls and user-function results degrade to
`Tensor<dtype>` with unknown shape, so rank errors can reach runtime. A language
that claims to be AI-native should extend static coverage without forcing
annotations everywhere.

**Hypothesis.** Inferring shapes through user-function returns, container
operations and the common `nn.*` surface, while keeping unknown-shape as a
fallback, catches a useful class of errors with less than 15 % added compile time
and without dependent types.

**Experiment.** Implement shapes as an optional type parameter on a branch;
compile the 200-function synthetic corpus and the tensor examples; count rejected
valid programs, accepted invalid programs on a hand-written mutation set, and
compile-time delta.

**Metric.** False-positive rate on valid programs, detection rate on a 50-case
mutation corpus, median compile-time change.

**Decision rule.** Adopt only if false positives are zero on the repository
corpus and detection ≥ 60 % at < 15 % compile-time cost; otherwise keep runtime
checks and improve messages.

**Status:** Open. Type-system extension is phase 4 work.

---

## OQ-002 — What is the cost of reverse-mode autodiff for realistic small models?

**Why.** The tape retains activations for every operation. The 3.8 GiB machine
may not fit the planned examples once sequence or conv layers exist.

**Hypothesis.** For ≤ 1 M parameters and batch ≤ 64, activation memory dominates
parameter memory by less than 8×; gradient checkpointing is unnecessary until
models exceed that scale.

**Experiment.** Instrument the tensor engine to count live intermediate elements
per training step for MLPs of 2/3/5 layers and batch sizes 8–128; compare measured
tracemalloc peaks with analytic estimates.

**Metric.** Peak live bytes, ratio to parameter bytes, per-step time.

**Decision rule.** If the ratio exceeds 8× at the target scale, design
checkpointing before adding conv/attention; otherwise defer.

**Status:** Partial. The bench records training time and final loss but not
activation-memory ratios.

---

## OQ-003 — Should Float32 tensors compute in Float32 or Float64?

**Why.** Current storage is Float32 but arithmetic uses binary64
(ADR-0009). This is simple and stable but slower and not bit-comparable with
native Float32 kernels.

**Hypothesis.** Computing in Float32 halves memory traffic and improves matmul
throughput by ≥ 25 % in pure Python only marginally (Python float objects dominate),
while increasing divergence from reference gradients.

**Experiment.** Dual implementation of matmul/softmax; measure time, peak memory
and gradient-check error on the existing numeric suite over 10 seeds.

**Metric.** Median time, memory, max relative gradient error.

**Decision rule.** Keep binary64 unless Float32 gives ≥ 20 % speed and gradient
error stays within the documented tolerance; document either choice in an ADR.

**Status:** Open. Touches OQ-006 and ADR-0009.

---

## OQ-004 — What capability granularity is usable?

**Why.** v0.1 has two coarse capabilities (`compute`, `fs`). A program that reads
one file receives authority over all files under the root.

**Hypothesis.** Five capabilities (`fs.read`, `fs.write`, `compute`, `net`,
`ui`) cover > 90 % of example programs without requiring delegation, at the cost
of more declarations.

**Experiment.** Classify privileged calls in the corpus; propose a finer set;
measure declaration churn and count programs that would need capability passing.

**Metric.** Declarations per program, uncovered calls, number of examples needing
delegation.

**Decision rule.** Adopt a split only when an example cannot be expressed safely
with the coarse model, or when a security review identifies a concrete over-grant.

**Status:** Open. Requires a real application corpus, not just demos.

---

## OQ-005 — Is the 3-layer capability check worth its complexity?

**Why.** Static declaration + VM check + host policy is redundant by design, but
redundancy costs implementation effort and can produce confusing errors.

**Hypothesis.** Removing the static layer would let at least one class of
authority misuse compile; keeping it costs < 5 % compile time.

**Experiment.** Build a variant without static checking; run the security suite
and a mutation set of programs that call `fs.*` without declaration; compare
accept/reject behaviour and compile time.

**Metric.** Escaped misuse cases, compile-time delta, diagnostic clarity.

**Decision rule.** Keep all three layers unless the static layer detects nothing
the VM does not and users report systematic confusion.

**Status:** Answered by design review and tests: the static layer produces PE3005
before execution and is cheap. Revisit if diagnostics become noisy. See ADR-0005.

---

## OQ-006 — Where does the pure-Python engine actually spend time?

**Why.** Optimisation without profiles is guessing. The roadmap needs to know
whether to invest in native kernels, better algorithms or a different memory
layout.

**Hypothesis.** ≥ 50 % of matmul time is Python-level loop and object overhead,
not arithmetic; a flat `array('d')` storage with blocked loops improves throughput
by ≥ 1.5× without changing semantics.

**Experiment.** `cProfile` the bench; implement an `array`-backed variant of
matmul only; compare on 48×48, 128×128 and a 2-layer MLP training step.

**Metric.** Profiled time by function, matmul MFLOP/s, training-step time, memory.

**Decision rule.** Adopt array storage if it preserves the API and improves
matmul ≥ 1.5× with no gradient-test regression.

**Status:** Open. This is the highest-value performance question for phase 5.

---

## OQ-007 — Can training be made bit-reproducible across machines?

**Why.** Reports claim determinism. Current determinism is within one Python
build and platform; Float32 rounding and iteration order may differ elsewhere.

**Hypothesis.** With fixed seeds, sorted iteration and binary64 accumulation,
identical results hold across CPython 3.11 on x86-64 Linux and macOS for the
current ops, but not across Python versions.

**Experiment.** Run the XOR and spiral trainings on at least two OS/CPU
combinations (requires hardware not available in this sandbox; document as
blocked), compare losses bitwise.

**Metric.** Bitwise equality of final parameters and loss traces.

**Decision rule.** If not bitwise, publish tolerance and stop claiming
bit-reproducibility; state "same-machine reproducible" instead.

**Status:** Blocked (single machine). Current claim in STATUS is limited to
same-machine determinism.

---

## OQ-008 — Does Oklab interpolation measurably improve gradient quality?

**Why.** Perceptual gradients are a headline frontend feature. It is easy to
assert they look better; that is not evidence.

**Hypothesis.** Oklab interpolation produces lower maximum lightness/chroma
discontinuity along a gradient than sRGB interpolation for a set of colour pairs,
at similar cost.

**Experiment.** Generate 100 random colour pairs; sample gradients in sRGB and
Oklab; compute ΔE2000 step variance, max step, and banding proxy (quantised
8-bit unique runs); run a small blinded preference study if participants are
available.

**Metric.** ΔE step statistics, unique-run count, preference rate.

**Decision rule.** Keep Oklab as default if discontinuity metrics improve and no
pathological hue behaviour appears; keep sRGB as an option.

**Status:** Partial. Tests verify reference values and monotonic lightness, not
perceptual superiority.

---

## OQ-009 — What anti-aliasing quality is achievable without a GPU?

**Why.** 4×4 coverage is cheap but limited for thin lines and small circles.

**Hypothesis.** Analytic coverage for circles/lines plus 4×4 supersampling for
general shapes improves edge error (vs. 64× reference) by ≥ 2× at < 2× cost.

**Experiment.** Render a test chart at 1×, compare to a 64× supersampled
reference; compute RMSE and max channel error; time both.

**Metric.** RMSE, max error, ms/frame.

**Decision rule.** Adopt analytic coverage if RMSE halves and frame time stays
within the UI budget target (16 ms for 512×512 on the reference machine is not
currently met; see bench).

**Status:** Open. Current `ui_frame_512x512` is ~30 ms, already above 16 ms.

---

## OQ-010 — Does one-pass flex layout cover real interfaces?

**Why.** The layout engine is not a constraint solver; it may fail on nested
overflow and baseline alignment.

**Hypothesis.** ≥ 80 % of a 20-screen mock UI corpus can be expressed with
row/column, grow, min-size, padding and gap without manual absolute positioning.

**Experiment.** Encode 20 screens from public design examples (no copied assets);
record which require hacks; add features only for recurring needs.

**Metric.** Screens expressible without hacks, layout passes per frame.

**Decision rule.** Add baseline alignment or wrapping only if ≥ 3 screens need it;
do not build a general constraint solver.

**Status:** Open. No corpus yet.

---

## OQ-011 — Is the fixed-substep spring stable for all parameter ranges?

**Why.** Large stiffness with a fixed 1/240 s substep can diverge. The API accepts
arbitrary `stiffness`/`damping`.

**Hypothesis.** The current integrator is stable when `stiffness ≤ 10000` and
substep ≤ 1/240; beyond that, energy grows.

**Experiment.** Sweep stiffness 10–10^5, damping 0–100, initial displacement
100; detect divergence/NaN and compare with the analytic solution.

**Metric.** Max absolute error vs. analytic, divergence count.

**Decision rule.** Clamp parameters or adapt substeps when the stability limit is
exceeded; document the bound in the specification.

**Status:** Partial. Tests cover representable parameter sets; the bound is not
derived or enforced.

---

## OQ-012 — Is AABB-only physics sufficient for the planned UI demos?

**Why.** Rotation and joints are expensive to implement correctly. If demos need
them, the design must change early.

**Hypothesis.** The planned motion demos (cards, sheets, particles) need no
rotation or joints; circles can be approximated by AABBs for collision only.

**Experiment.** Prototype three interactions from the roadmap with the current
engine; record failures and workarounds.

**Metric.** Number of demos blocked by missing features.

**Decision rule.** Add rotation only when a demo cannot be expressed; do not add
a full rigid-body engine speculatively.

**Status:** Open.

---

## OQ-013 — Is the tokenizer port a reliable predictor of full self-hosting cost?

**Why.** Self-hosting is the largest architectural commitment. The tokenizer is
235 lines of `.pac`; the parser and type checker are much larger.

**Hypothesis.** Lines-of-code ratio (PEACOCK/Python) for the parser will be
1.2–2.0×, and missing language features (enums, modules, maps) will account for
most of the friction.

**Experiment.** Port the parser to PEACOCK behind a feature flag; record missing
features, defects and parity on the corpus. Do not claim self-hosting.

**Metric.** LOC ratio, parity failures, blockers.

**Decision rule.** Proceed to stage 3 only if the parser reaches 100 % corpus
parity and the required language additions can be specified and tested without
destabilising v0.1.

**Status:** Partial. The parser port (`selfhost/parser.pac`, 1,085 lines) reaches
100 % AST-digest parity on the 14-file corpus and self-parses. Measured source
ratio is about 0.94 against `lexer.py` + `parser.py` (1,150 Python lines), but the
port emits strings rather than typed nodes, so this is not yet a like-for-like
port. Missing enums/modules did not block a string digest; they do block a typed
AST and diagnostic objects.

---

## OQ-014 — Which language features are prerequisites for self-hosting?

**Why.** Adding features for their own sake violates the spec-first rule; adding
them too late stalls self-hosting.

**Hypothesis.** The minimum set is: user modules/imports, a sum type or tag
convention, string builders, maps or an efficient association structure, and
better diagnostics formatting.

**Experiment.** Derive requirements from the tokenizer port and a paper design of
the parser port; implement only what a concrete port needs.

**Metric.** Blockers encountered per stage.

**Decision rule.** Any new feature must have a spec entry, positive/negative
tests and a use in the port; otherwise it is deferred.

**Status:** Open, constrained by ADR-0003 and the roadmap.

---

## OQ-015 — Does the benchmark suite represent the workloads the project claims?

**Why.** Microbenchmarks can mislead. Compilation of a 200-function synthetic
file and a 48×48 matmul are not applications.

**Hypothesis.** The suite's ranking of bottlenecks (VM dispatch, Python
arithmetic, raster loops) matches an end-to-end demo workload within one order of
magnitude.

**Experiment.** Profile the aurora and training examples end-to-end; compare
share-of-time by subsystem with the microbenchmarks.

**Metric.** Spearman rank correlation of subsystem costs; absolute share.

**Decision rule.** Add or replace benchmarks when a subsystem's share differs by
> 2×; keep microbenchmarks as diagnostics, not as headline claims.

**Status:** Partial. End-to-end example timings exist, but no share-of-time
analysis is checked in.

---

## OQ-016 — What is the real security value of artifact hashing?

**Why.** A SHA-256 digest detects accidental corruption and naive tampering, but
an attacker who can rewrite the file can rewrite the digest. It is not a
signature.

**Hypothesis.** Hashing prevents accidental corruption and mutation by programs
that lack write access to the artifact, and provides no protection against an
attacker with write access.

**Experiment.** Threat-model the loader; attempt tampering with and without
digest recomputation; document results in SECURITY.md.

**Metric.** Attack success under each adversary capability.

**Decision rule.** Never describe hashing as authentication; if signed artifacts
are needed, specify a signature format and key management separately.

**Status:** Answered for v0.1: it is integrity checking, not authenticity. See
SECURITY.md and tests that reject edited images.

---

## OQ-017 — How much does deterministic fuzzing actually cover?

**Why.** 1000 iterations with a fixed seed found no crashes, which is weak
evidence.

**Hypothesis.** The current fuzzer reaches < 40 % of parser productions and < 25 %
of bytecode operand combinations; coverage-guided fuzzing would find defects the
current corpus does not.

**Experiment.** Instrument coverage of tokens/opcodes hit per fuzz run on the
existing seeds; measure unique error codes and paths; compare with a
mutation-based generator.

**Metric.** Production/opcode coverage, unique diagnostics, crashes per 10k runs.

**Decision rule.** Invest in a coverage-guided fuzzer before claiming robustness;
until then describe fuzzing as smoke testing.

**Status:** Partial. Crash-freedom is verified for seed 1; coverage is unmeasured.

---

## OQ-018 — What should "AGI research tooling" mean for a language with no large models?

**Why.** The phrase is expansive and easy to overclaim. The project needs a
concrete, falsifiable deliverable that fits the hardware budget.

**Hypothesis.** A useful v0.1 research substrate is: reproducible small-model
experiments, dataset provenance, evaluation metrics with confidence intervals,
and exportable experiment records — not agents or LLMs.

**Experiment.** Define an experiment-record schema; run the XOR/spiral suite with
multiple seeds; measure variance and produce a report that a third party can
re-run.

**Metric.** Re-run success rate from the record alone, variance reporting
completeness.

**Decision rule.** Phase 10 is "done" only when an external re-run reproduces the
recorded metrics within stated tolerance and the roadmap's tooling checklist is
met. Otherwise the feature is labelled "experiment records", not AGI tooling.

**Status:** Open. This is the intended meaning of the roadmap phase; no phase-10
work has started.
