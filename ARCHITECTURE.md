# PEACOCK Architecture

Status: describes the v0.1 bootstrap implementation. The language definition is
independent of this implementation; the Python toolchain is a temporary host
(ADR-0001). Components marked **planned** do not exist yet.

## 1. Goals and non-goals

PEACOCK is being built as an AI-native language and computing ecosystem:

* a statically typed language with first-class tensors, differentiable
  computation, model declarations, colour, 2D graphics, motion and physics;
* an original compiler pipeline and bytecode runtime with capability-based
  security and enforced resource budgets;
* an ecosystem that can eventually host its own compiler and tools.

Non-goals for v0.1: being a general-purpose replacement for Python, shipping a
production UI toolkit, matching GPU performance, or claiming AGI. The reference
implementation is deliberately small enough to audit and test.

## 2. System map

```
 .pac source
     │  lexer (compiler/lexer.py)
     ▼
 tokens ──► parser (compiler/parser.py) ──► AST (compiler/ast_nodes.py)
                                              │  semantic analyser
                                              ▼  (compiler/semantic.py + types.py + builtins.py)
                                         typed AST / slots / capabilities
                                              │  IR builder (compiler/ir.py)
                                              ▼
                                         PIR (typed, SSA-like temporaries + named slots)
                                              │  verifier + optimiser (compiler/optimizer.py)
                                              ▼
                                         verified PIR
                                              │  bytecode compiler (compiler/bytecode.py)
                                              ▼
                                         .pkb image (JSON + SHA-256)
                                              │  VM loader + verifier (runtime/vm.py)
                                              ▼
                                         stack VM execution
                        ┌─────────────────────┼──────────────────────┐
                        ▼                     ▼                      ▼
                  host policy           native library         platform hosts
                  (capabilities,        (runtime/native.py)    (platforms/)
                   budgets, sandbox)
```

The intelligence engine (`peacock/intelligence/`) and frontend engine
(`peacock/frontend/`) are libraries used by natives and directly by tests and
embedders. They do not depend on the compiler.

## 3. Compiler pipeline

### 3.1 Lexing

`compiler/lexer.py` is a hand-written scanner over Unicode text with explicit
line/column tracking. It never uses regular expressions. Tokens carry `kind`,
`text`, decoded `value` and a `Span`. Comments are skipped; block comments nest.
Numbers are validated for radix, underscores and 64-bit range. Errors recover and
continue so one run can report several lexical problems.

### 3.2 Parsing

`compiler/parser.py` is recursive descent with one-token lookahead. It produces
dataclass AST nodes from `ast_nodes.py`. The grammar is in
[SPECIFICATION.md](SPECIFICATION.md) §3. Error recovery synchronises at statement
and item boundaries; chained comparisons, positional-after-named arguments and
invalid assignment targets have targeted diagnostics.

### 3.3 Semantic analysis

`compiler/semantic.py` performs, in order:

1. declaration collection (functions, structs, models, trainings) with
   collision checks against built-ins;
2. type resolution (primitive, list, tensor, struct, opaque);
3. function-body checking with lexical scopes;
4. model and training validation;
5. entry-point checks (`main` takes no parameters, returns Unit);
6. capability checking for protected natives and declaration methods.

Each local receives a **slot**; temporaries are assigned in the IR stage. The
analyser is deliberately conservative: it does not infer full flow-sensitive
types, but it does track definite returns and unreachable statements. Diagnostics
are collected in one `DiagnosticBag`; `ErrorType` suppresses cascades.

### 3.4 Typed IR (PIR)

`compiler/ir.py` lowers the typed AST into a linear instruction list per
function:

```
const dst value            slot_get dst slot        slot_set slot src
binop dst op a b           unop  dst op a            call dst fn args
call_native dst name args  method dst recv name args  struct_new dst Type args
field_get dst base field   field_set base field src  index_get dst base idx
index_set base idx src     make_list dst items       make_range dst start end
len dst value              assert cond msg           throw value
jump label                 branch cond then else     label name
try_begin catch_label end  try_end                   catch dst
model_init dst Name seed   training_method dst Training method args
return value
```

Registers are typed. `IRVerifier` checks slot ranges, jump targets, duplicate
labels, stack-ish structure of try scopes, terminators, and binop operand types.
`optimizer.py` performs constant folding, constant branch folding, unreachable
code elimination, dead-temporary elimination, and simple peephole rewrites. It
preserves try/catch scope markers structurally. The verifier runs before and
after optimisation.

### 3.5 Bytecode

`compiler/bytecode.py` maps PIR labels to instruction indices and emits a
stack-machine image. The image is a JSON-serialisable dict (sorted keys for
determinism) with:

```
format, format_version, language_version, compiler_version,
module, uses, source_path, source_sha256,
functions: { name: {arity, slots, caps, return_type, params, code, lines} },
structs, models, trainings
```

`verify_image` re-checks the image independently of the compiler: opcode set,
operand shapes, slot ranges, jump/catch targets, native names and arities,
capability names, struct/model/training references, and `main` arity. The VM
calls it again on load, so a tampered artifact cannot reach dispatch.

### 3.6 Artifacts

`runtime/artifact.py` writes `.pkb`:

```
magic b"PEACOCK\x1a" | <H format_version> | <I language minor> |
<I payload length> | canonical JSON | SHA-256(payload prefix)
```

The loader verifies magic, versions, length bounds, JSON shape and the digest
before verification. Models use a separate `.pkm` format with magic
`PEACOCKM`, a versioned header, a parameter table, a float32 payload, and a
SHA-256 digest (`intelligence/serialization.py`).

## 4. Runtime

### 4.1 Execution model

`runtime/vm.py` is a stack VM. Each function call creates a `Frame` with:

* a fixed slot array (locals/parameters, `None` means uninitialised);
* an operand stack;
* a program counter and source-line table;
* active exception handlers (`start`, `end`, `target`, stack depth);
* declared capabilities.

Execution is single-threaded and deterministic. There is no garbage collector
in the language; values are Python objects owned by the host process. Reference
cycles are the host's responsibility. This is a documented bootstrap limitation,
not the planned memory model.

### 4.2 Values

`runtime/values.py` defines `UNIT`, `StructInstance`, `RangeValue`, and display
formatting. Lists, structs, tensors, canvases, models and datasets have reference
semantics; Int, Float, Bool, String, Unit and Range are value-like.

### 4.3 Checked operations

Integer `+ - * **` are checked against the signed 64-bit range; division and
remainder truncate toward zero and reject zero; float `/` by zero is a fault;
math domain errors become catchable faults. Bounds are checked for lists,
strings and tensors. Assertions raise PE4010.

### 4.4 Errors

`runtime/errors.py` defines `VMFault` (catchable) and stack-trace accumulation.
`compiler/diagnostics.py` defines the shared hierarchy: `CapabilityError`
(PE4001), `ResourceLimitError` (PE4003), `PanicError` (PE4011), `HostError`,
`ArtifactError`. PEACOCK `try/catch` catches `PeacockError` subclasses except
`PanicError` and `ResourceLimitError`, which always terminate.

### 4.5 Capabilities and sandbox

Three enforcement layers:

1. **Static:** the semantic analyser rejects calls to protected natives unless
   the enclosing function declares the capability.
2. **VM:** before every native/method dispatch the VM checks the function's
   declared capabilities and the host's grants.
3. **Host:** `HostPolicy` grants capabilities, enforces step/depth/output/tensor/
   dataset/epoch/file budgets, resolves filesystem paths inside a sandbox root
   (rejecting `..`, absolute paths, symlink escapes, NUL bytes and oversized
   files), and forwards `graphics.present` frames to an attached backend, failing
   with PE4006 when none is attached.

The capabilities are `compute`, `fs` and `ui`. `ui` is presentation-only: it
grants no input, window management or display query.

This is best-effort process-level isolation, **not** a kernel sandbox. See
[SECURITY.md](SECURITY.md).

## 5. Intelligence engine

* `tensor.py`: flat float/int/bool storage plus shape; broadcasting; elementwise
  ops; matmul; reductions; softmax/log-softmax; reverse-mode autodiff with a
  topological backward pass. Float32 is rounded on storage; arithmetic uses
  binary64 (documented deviation).
* `random.py`: xoshiro256** with deterministic seeding for reproducible runs.
* `datasets.py`: XOR and synthetic two-arm spiral, plus host-supplied datasets.
* `layers.py`: Dense and Sequential/Model; deterministic initialisation.
* `training.py`: mini-batch SGD/Adam loops, cross-entropy and MSE, finite-loss
  guards, training reports.
* `evaluation.py`: accuracy, confusion matrix, per-class report.
* `optim.py`: original SGD (optional momentum) and Adam.
* `serialization.py`: `.pkm` v1 with per-parameter dtype/shape, float payload,
  metadata, SHA-256, and int8 quantisation helpers.

Gradient correctness is checked against finite differences in tests
(`test_tensor.py`, `test_training.py`) with tolerances around 1e-9 for the
small analytic cases. This is numerical validation, not a proof.

## 6. Frontend engine

* `colour.py`: sRGB transfer functions, XYZ, CIELAB, Oklab/Oklch, WCAG
  luminance/contrast, mixing, hue rotation, palettes, gradients.
* `canvas.py`: premultiplied RGBA software framebuffer; 4×4 supersampled
  rectangles/circles/lines; additive glow; perceptual gradients; procedural
  aurora; explicit dimension/pixel limits.
* `png.py`: original PNG container writer/reader (IHDR/IDAT/IEND, filter 0,
  zlib, CRC validation), tone mapping for HDR values.
* `easing.py`, `spring.py`, `timeline.py`: deterministic motion.
* `layout.py`: row/column flex layout with grow factors, padding, gaps, minimum
  sizes and overflow reporting.
* `physics.py`: fixed-step AABB rigid bodies with gravity, restitution,
  friction and positional correction.

Rendering is 2D and CPU-only. Text shaping, accessibility, a widget toolkit, 3D,
and GPU backends are planned.

## 7. Host boundaries and platforms

`peacock/platforms/` defines a `Frame` and `Backend` contract plus three
implementations:

* `HeadlessBackend` — keeps the latest frame, optionally writes PNGs.
* `WebBackend` — writes frames, `latest.png`, a manifest and a static HTML
  viewer (no JavaScript/framework).
* `ServerBackend` — a stdlib HTTP host serving the latest frame, manifest,
  viewer and health check.

They are driven by the `graphics.present(canvas)` native (capability `ui`): the
host attaches a backend through `HostPolicy(presenter=...)`, and the CLI exposes
this as `--present DIR` with a `WebBackend` or `--serve PORT` with a
`ServerBackend`. The VM never imports `peacock/platforms`; it calls the host
policy, so a future window, Android or web host can attach a different backend
without changing language semantics. A native window shell, input events
and mobile shells are roadmap work; Android and iOS require platform toolchains
and signing, and are documented as **not implemented**, not stubbed as if they
worked.

## 8. External dependencies

| Dependency | Use | Why it is allowed |
|---|---|---|
| CPython 3.11+ | runs bootstrap compiler/VM | temporary host; language definition does not depend on it |
| `zlib` | DEFLATE in PNG | documented platform compression library; PNG framing/CRC are ours |
| `hashlib` | SHA-256 digests | standard library primitive |
| OS filesystem | `fs` capability | documented interop boundary behind the sandbox |
| Browser | static web preview | presentation only; no JS framework or language runtime |
| HTTP stdlib | server host | transport boundary, not language semantics |

No NumPy, PyTorch, TensorFlow, JAX, LLVM, MLIR, Rust, Node, React or Flutter is
used in the core. No code from other language implementations was copied;
research ideas are cited in `research/references.bib`.

## 9. Performance and memory

The reference engine is pure Python. Representative measurements on the
recorded machine are in [STATUS.md](STATUS.md) and
`benchmarks/latest.json` when generated. They characterise this bootstrap only
and are not used to claim superiority over other languages. The VM is a switch
dispatch over Python lists; there is no JIT, tiering or native code. Tensors are
flat lists, not contiguous typed buffers. The optimiser operates on a
straight-line IR, not an SSA graph with dominance frontiers.

Planned performance work (phase 8): typed buffers, a register-based bytecode or
closure IR, a native backend for a subset, and profile-guided intrinsics.
Memory: no GC tuning, no arenas; host process memory is the limit. Canvas and
tensor sizes are bounded by host policy and explicit library limits.

## 10. Testing strategy

`tests/` uses only `unittest` and is split by subsystem:

* `compiler/` — lexer, parser, types, semantics, IR/optimiser, pipeline/artifacts,
  VM, diagnostics;
* `ai/` — tensors, autodiff, training, serialisation;
* `frontend/` — colour, canvas/PNG, motion/layout/physics, platform hosts;
* `security/` — capability bypass attempts, sandbox escapes, resource limits,
  artifact tampering;
* `integration/` — the real CLI end-to-end, examples, self-host tokenizer and parser parity,
  fuzzing;
* `benchmarks/` — the benchmark harness itself;
* `unit/` — diagnostics and metadata invariants.

Every positive construct has negative/diagnostic tests where it can fail. The
fuzzers (`peacock/fuzzing.py`) check the lexer, parser, artifact loader and model
loader with deterministic mutated inputs; they are not proof of security.

## 11. Bootstrap and self-hosting

The Python implementation is split into (a) the language definition and
compiler stages, and (b) host services. The self-hosting plan reimplements (a)
in `.pac` while keeping OS access behind natives:

1. tokenizer — **done** (`selfhost/tokenizer.pac`, parity-tested);
2. parser and AST — **partial** (`selfhost/parser.pac`): full 0.1 syntax,
   including model/training declarations, with canonical AST-digest parity on the
   14-file corpus and self-parse; strict first-error reporting, no recovery or
   `PE2xxx` diagnostic parity yet, and no typed AST nodes;
3. semantic analyser and type checker;
4. IR/bytecode emitter;
5. VM in PEACOCK (with a small host ABI for allocation, I/O and time);
6. bootstrap chain: Python compiler builds the PEACOCK compiler, which then
   rebuilds itself; the Python compiler is retired only when the fixed point and
   test suite pass.

See `docs/compiler/bootstrap.md` and ADR-0003.

## 12. Known architectural gaps

* The VM interprets JSON images directly; there is no linker, separate
  compilation, or module cache.
* No user modules, generics, closures, or first-class functions.
* No native code generation.
* No GPU tensors, no convolution/attention layers, no data loader pipeline.
* No UI toolkit, text shaping, accessibility, 3D, or native windowing.
* Capability isolation is process-level and best effort; it is not a hardened
  multi-tenant sandbox.
* The Python bootstrap adds latency and memory overhead that the native path is
  intended to remove.
