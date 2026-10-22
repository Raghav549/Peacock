# Literature review

Scope: the mechanisms PEACOCK uses or plans to use. This is a design-oriented
review, not an exhaustive survey. Citation keys refer to
[`references.bib`](references.bib). Statements about the literature are limited
to well-established results; statements about PEACOCK's implementation are
limited to what its tests and benchmarks demonstrate.

## 1. Compiler construction and language implementation

The classical pipeline — lexical analysis, recursive-descent or table-driven
parsing, semantic analysis, intermediate representation, optimisation, code
generation — is thoroughly documented [aho2006compilers], [appel1998modern],
[cooper2011engineering]. PEACOCK follows it deliberately rather than inventing a
new compilation model. The lexer is hand-written without regular expressions; the
parser is recursive descent with explicit precedence; diagnostics carry spans and
codes.

Two design points matter more than the pipeline itself:

* **Intermediate representation shape.** Graph-based IRs such as Sea of Nodes
  [click1995simple] and SSA [cytron1991ssa] enable powerful analyses, but they
  require substantial machinery (dominance, phi placement, register allocation).
  PEACOCK's PIR is a linear, typed, three-address-like list with slots and
  explicit try regions. This is closer to a teaching compiler than to LLVM
  [lattner2004llvm]; the optimiser performs constant folding, branch folding,
  unreachable-code elimination and dead-temporary elimination [muchnick1997advanced].
  The literature on dataflow analysis [wegman1991constant], [bacon1994compiler]
  explains what is missing (SSA-based propagation, loop optimisation, alias
  analysis).
* **Verification.** A bytecode verifier inspired by the JVM specification
  [lindholm2014jvm] checks opcodes, operands, slots, jump targets, arities,
  capabilities and model references before execution. This is structural
  verification, not a proof of type safety; the type checker and verifier are
  separate implementations, which provides some defence in depth.

The stack-machine choice follows the JVM and the interpreter-performance
literature [ertl2003interpreters], [smith2005virtual]. Stack machines are simple
to verify and portable; register machines are faster but harder to generate and
verify. PEACOCK has no JIT, no tiering and no inline caches. WebAssembly's design
[haas2017webassembly] is a useful reference for a compact, verifiable bytecode,
but PEACOCK's format is its own JSON container and is not WASM-compatible.

**Type systems.** The implemented type system is monomorphic with explicit
annotations; it is informed by the simply typed lambda calculus and the
soundness literature [pierce2002types], [wright1994syntactic] and by the
operational-semantics tradition [plotkin1981structural]. It does **not** implement
Hindley–Milner inference [hindley1969principal], [milner1978theory], row
polymorphism, subtyping, effects or dependent types. The specification defines the
subset precisely; anything outside it is rejected. This is a deliberate trade: a
small, checkable type system with good diagnostics is more useful at this stage
than an inferred one with unclear failure modes.

**Garbage collection.** The runtime currently relies on the host's memory
management. The literature on tracing, generational and real-time collectors
[wilson1992gc], [ungar1984generation], [jones2011gc], [bacon2004unified] defines
what a native runtime will need. There is no PEACOCK GC in 0.2; cycles are not
collected, and memory is bounded by host limits and tensor/canvas budgets.

**Self-hosting.** The staged plan (tokenizer → parser → semantic analyser → IR
and codegen → VM → fixed point) is documented in
[`../docs/compiler/bootstrap.md`](../docs/compiler/bootstrap.md). The lexer and a
full-grammar parser are genuinely written in PEACOCK and parity-tested against the
bootstrap; semantic analysis, IR and code generation are not, so the compiler is
not self-hosting.
The literature offers many self-hosting precedents, but the engineering rule is
simple: the claim is allowed only after a fixed-point build runs the suite.

## 2. Capability security

Capability systems originate in the multiprogramming work of Dennis and Van Horn
[dennis1966programming] and were articulated as a design philosophy by Saltzer
and Schroeder [saltzer1975protection]: least privilege, economy of mechanism,
complete mediation, open design. Lampson's protection model [lampson1971protection]
and Levy's survey [levy1984capability] describe the object-capability tradition.
The confused-deputy problem [hardy1988confused] is the canonical motivation for
passing authority explicitly rather than relying on ambient names.

PEACOCK applies the idea at three layers:

1. a **static declaration** in the function that performs a privileged operation;
2. a **VM check** against the frame's declared set and the host's grants;
3. a **host policy** that resolves paths under a sandbox root and enforces byte,
   step, depth, output, tensor, dataset and epoch budgets.

This is capability-style *authorisation*, not a full object-capability OS in the
sense of E [miller2006robust] or a hardware capability architecture such as CHERI
[watson2015cheri], [watson2019cheri]. There is no capability passing, no
revocation, no delegation and no per-object rights. The threat model in
[`../SECURITY.md`](../SECURITY.md) states the limits: process-level best-effort
confinement, a TOCTOU window, no isolation from a malicious host, no formal
guarantee. The reference-monitor concept [anderson1972security] is approximated,
not proved.

The important negative result is architectural: **a grant flag alone is not
enough, and a declaration alone is not authority.** Tests exercise both missing
cases, caught denials, and non-catchable panics/limit errors.

## 3. Automatic differentiation

Reverse-mode differentiation is the algorithmic core of deep learning. The chain
rule as a computational-graph transformation is described by Linnainmaa
[linnainmaa1976taylor], Speelpenning [speelpenning1980compiling], Werbos
[werbos1974beyond] and Rumelhart et al. [rumelhart1986learning]. Modern surveys
[baydin2018automatic], [griewank2008evaluating] distinguish forward and reverse
mode, checkpointing and complexity bounds.

PEACOCK implements a tape-based reverse mode over dense tensors:

* each differentiable operation records its parents and a backward closure;
* `backward()` topologically sorts the graph and accumulates gradients;
* `zero_grad()` clears accumulated gradients;
* non-scalar outputs require an explicit gradient seed.

This mirrors the design of Autograd [maclaurin2015autograd] and the eager mode of
PyTorch [paszke2019pytorch] in spirit, but the implementation is original and
much smaller. It has no forward-mode, no checkpointing, no higher-order
derivatives, no vmap/jit and no GPU. Gradient checking against central finite
differences is numerical evidence for the tested operations, not a proof.

Compiler-oriented systems such as TVM [chen2018tvm], Halide [ragan2013halide],
MLIR [lattner2020mlir], JAX [frostig2018jax] and differentiable programming
languages [innes2019differentiable] show where an AI-native language could go:
shapes and kernels as first-class concepts, transformations as language
primitives, and compilation across host/accelerator boundaries. PEACOCK's
`प्रतिमान`/`अभ्यास` declarations are a small, surface-level step in that
direction; they are not a tensor compiler.

## 4. Training, architectures and evaluation

Stochastic approximation [robbins1951stochastic], momentum [polyak1964some],
Nesterov acceleration [nesterov1983method] and Adam [kingma2015adam] are the
optimisation background. Initialisation follows Xavier/Glorot [glorot2010understanding]
and He et al. [he2015delving]; normalisation and regularisation are discussed in
[ioffe2015batch], [srivastava2014dropout], [ba2016layer] but only partially
implemented. Universal approximation results [cybenko1989approximation],
[hornik1989multilayer] explain why small MLPs can fit the XOR/spiral examples;
they say nothing about generalisation.

The architecture literature — CNNs [lecun1998gradient], [krizhevsky2012imagenet],
residual networks [he2016deep], recurrent networks and LSTM [elman1990finding],
[hochreiter1997lstm], attention and transformers [bahdanau2014neural],
[vaswani2017attention], generative models [kingma2014auto],
[goodfellow2014generative], [ho2020denoising] — informs the roadmap. **None of
these architectures is implemented in v0.2.** The engine supports Dense layers
with linear/ReLU/sigmoid/tanh/softmax activations, MSE and cross-entropy, SGD
with momentum and Adam. Claiming "AI-native" does not mean claiming a transformer
implementation.

Evaluation practice is influenced by model cards [mitchell2019model],
datasheets [gebru2021datasheets] and the technical-debt literature
[sculley2015hidden]. Training reports include dataset provenance, seeds,
hyperparameters, per-epoch loss and accuracy, and a determinism statement. This
is provenance for reproducibility, not a fairness or safety certification.

## 5. Numerical behaviour

Floating-point semantics are subtle [goldberg1991what], [higham2002accuracy];
IEEE 754 [ieee754] defines the arithmetic but not reproducibility across
implementations. PEACOCK stores Float32 tensors but performs arithmetic in
binary64 before rounding back, a deliberate deviation chosen for a simple,
predictable pure-Python engine. It does not claim bit-identical results with
hardware Float32 libraries. Kahan summation [kahan1965further] is not used.

Integers are 64-bit and checked: overflow is a fault, not wrap-around. Division
truncates toward zero and remainder takes the dividend's sign; this is specified
and tested, because "whatever the host language does" is not a language
definition.

These choices reduce performance and should be revisited by measurement (see
OQ-005, OQ-006).

## 6. Colour science

The pipeline follows standard colorimetry: sRGB transfer functions
[iec61966], CIE XYZ and Lab [cie2004colorimetry], [fairchild2013color], and
Oklab/Oklch for perceptual interpolation [ottosson2020oklab]. WCAG contrast
[wcag22] and CSS Color 4 [w3ccsscolor4] provide the accessibility and
interpolation conventions. Poynton [poynton2012digital] supplies the video/transfer
background; ITU-R BT.709 [itu709] defines the primaries used by sRGB.

Implemented: sRGB↔linear, XYZ (D65), Lab, Oklab, Oklch, WCAG relative luminance
and contrast, Oklab mixing, lighten/darken, hue rotation, palettes, LUT
gradients, gamut checks and clipping. Not implemented: ICC profiles, chromatic
adaptation beyond D65, spectral rendering, colour appearance models such as
CIECAM02, or display calibration. Documented reference values and tolerances are
in the tests.

## 7. Raster graphics and imaging

Compositing follows Porter–Duff [porter1984compositing]; anti-aliasing follows
the classical coverage/supersampling discussion [crow1977aliasing]; physically
based rendering [pharr2023pbr] informs the linear-light pipeline, though PEACOCK
implements only 2-D source-over. The rasteriser uses 4×4 coverage samples for
rectangles, circles and lines; gradients are evaluated in Oklab. PNG encoding is
implemented against the W3C specification [pngspec] using zlib [rfc1950],
[rfc1951], with a validating decoder.

Procedural aurora imagery uses fBm built from value noise inspired by Perlin
[perlin1985image], [perlin2002improving]; it is explicitly artistic, not a
physical model of atmospheric emission. Tone mapping uses a documented ACES
approximation [narkowicz2016aces] or clipping; the photographic operator
[reinhard2002photographic] is background, not implemented.

There is no path tracer, no 3-D pipeline, no GPU, no text shaping, no vector
path rasteriser, no colour management and no image formats other than RGBA8 PNG.
The performance numbers in `benchmarks/reference-machine.json` reflect a Python
loop, not a graphics engine.

## 8. Animation, layout and physics

Animation principles [thomas1981illusion], [lasseter1987principles] and the
easing conventions popularised by Penner [penner2001easing] inform the motion
API. Springs are integrated as a damped harmonic oscillator with fixed substeps;
the control-theory background is standard [ogata2010modern]. Timelines apply
easing to the segment ending at each keyframe, matching CSS-style semantics.

Physics uses AABB rigid bodies, fixed 1/120 s substeps, gravity, restitution,
friction and positional correction. This is a deliberately small subset of the
game-physics literature [eberly2010game], [catto2009modeling], [box2d]; there are
no rotations, joints, continuous collision detection, broadphase or constraints.

Layout implements one-pass row/column stacks with grow factors, gaps, padding and
overflow reporting. CSS Flexbox [cssflexbox] is the reference point, but this is
not a CSS implementation; Cassowary-style constraint solving [badros2001cassowary]
is not used.

## 9. Benchmarking and empirical method

Performance claims are notoriously easy to falsify through measurement error
[mytkowicz2009producing], [curtsinger2013stabilizer]. The methodology
[georges2007statistically], [hoefler2015scientific], [beyer2019reliable] requires
a stated machine, workload, warm-up, dispersion and reproducibility. PEACOCK's
harness reports medians of a small number of in-process wall-clock samples,
records the environment, and **does not compare against other languages or
frameworks**. There are no confidence intervals and the sample counts are small;
results are descriptive, not inferential. Summary statistics advice
[fleming1986how] and the dangers of single-run reporting are acknowledged.

Testing practice draws on fuzzing [miller1990empirical], property-based testing
[claessen2000quickcheck] and mutation testing [demillo1978hints], [jia2011analysis].
The repository has deterministic fuzzers for the lexer, parser, artifact and
model loaders, but no coverage-guided fuzzer and no mutation score.

## 10. Sanskrit grammar, native vocabulary, and language technology

PEACOCK 0.2 uses Sanskrit as its actual reserved source vocabulary rather than
as a file-extension label. The linguistic design is documented with the original
sūtra numbers in [`../docs/language/sanskrit.md`](../docs/language/sanskrit.md).
The strongest transferable ideas are exact technical designation (`saṃjñā`),
explicit domains for rules, ordered correspondence, and deterministic conflict
resolution. The implementation does **not** equate these ideas with a complete
simulation of the *Aṣṭādhyāyī*.

The primary-text anchors are `वृद्धिरादैच्` (1.1.1)
[panini1x1x1], `उपदेशेऽजनुनासिक इत्` (1.3.2) [panini1x3x2],
`यथासंख्यमनुदेशः समानाम्` (1.3.10) [panini1x3x10],
`विप्रतिषेधे परं कार्यम्` (1.4.2) [panini1x4x2],
`समर्थः पदविधिः` (2.1.1) [panini2x1x1], and `प्रत्ययः`
(3.1.1) [panini3x1x1]. Patañjali's *Mahābhāṣya* and Kātyāyana's `vārttika`
tradition motivate critical interpretation and regression evidence
[patanjalimahabhashya]; Bhartṛhari's *Vākyapadīya* is relevant to the distinction
between formal expression and meaning, not to a concrete VM algorithm
[bhartrharivakyapadiya].

The computational literature separates two problems that must not be conflated.
Krishna and Goyal use `anuvṛtti`, inheritance networks, and strict rule ordering
for Pāṇinian derivative-noun generation [krishna2015derivative], while Rama and
Lakshmanan model sandhi computation [rama2009sandhi]. In contrast, work on neural
sandhi splitting explicitly identifies non-uniqueness and context dependence
[dave2020sandhi]. Sanskrit segmentation/morphology systems
[li2022segmentation], [sandhan2023sanskritshala], [nehrdich2024byt5] are valuable
research tools but are not deterministic compiler lexers and are not PEACOCK
dependencies. `Kāraka` research in multimodal grounding is a future structured-
representation direction, not an implemented agent capability [gorthi2022karaka].
Jayanti's native technical-writing work supports intentional Indic terminology
rather than automatic borrowing of English computing vocabulary
[jayanti2026indic].

The implementation consequence is deliberately strict: Unicode NFC identifiers,
explicit combining-mark handling, Unicode decimal digits, one auditable Sanskrit
lexicon, and no probabilistic tokenisation or automatic sandhi splitting.

## 11. AGI research tooling and safety

The planned "AGI research tooling" phase is informed by the safety literature:
concrete problems [amodei2016concrete], reward modelling [leike2018scalable],
learned optimisation risks [hubinger2019risks], the deep-learning alignment
framing [ngo2022alignment], and unsolved ML safety problems [hendrycks2021unsolved].
Evaluation design draws on the measurement-of-intelligence debate
[chollet2019measure], [legg2007universal] and on benchmark methodology
[hoefler2015scientific]. Tooling for LLM workflows (chain-of-thought [wei2022chain],
ReAct [yao2022react], tool use [schick2023toolformer], retrieval [lewis2020retrieval])
is roadmap material.

**What exists in v0.2:** deterministic datasets, seeded training, evaluation
metrics, training reports with provenance, and model save/load. That is a
reproducible experiment substrate for small models. It is not an AGI system, an
agent framework, a reward-model trainer, an interpretability toolkit or an
alignment benchmark. The project should not use the phrase "AGI research tooling"
in the present tense until the phase-10 acceptance criteria in
[`../ROADMAP.md`](../ROADMAP.md) are met.

Self-improvement ideas such as Gödel machines [schmidhuber2006godel] and universal
intelligence [hutter2005universal] are background for framing; no implementation
exists or is planned within the current roadmap.

## 12. Gaps in this review and in the implementation

1. **No formal semantics.** The specification is precise but not mechanised. The
   type-soundness literature [wright1994syntactic] describes proofs PEACOCK does
   not have.
2. **No compiler-for-ML.** TVM/Halide/MLIR/JAX are cited as direction, not as
   implemented mechanisms.
3. **No HCI evaluation.** Layout and motion choices are informed by design
   literature [card1983psychology], [nielsen1993usability], [tufte1983visual],
   [bringhurst2004elements], but no user study has been run.
4. **No statistical benchmarking.** Medians only; no confidence intervals or
   effect sizes.
5. **Thin coverage of security literature beyond capabilities.** No formal
   information-flow analysis, no verified sandbox, no side-channel work.
6. **Citation verification.** Bibliography entries were not fetched in this
   environment; see the note in `references.bib`.
