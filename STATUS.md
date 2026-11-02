# PEACOCK Status

Last verified: **2026-11-03** on `arena/c0fe52eb-peacock` (working tree;
not a released/tagged upstream version). Re-run the commands before relying on
any number. Canonical source extension: `.सूत्र`. The compiler is **not
self-hosting** (bootstrap is pipeline-digest parity via `peacock.tools.bootstrap`;
`pipeline.सूत्र` now wires all 7 selfhost kernels with chunked literals and
hash/len parity; new decoder/cross-attention/causal DSL is Python-authoritative
until selfhost IR catches up). GitHub does **not** yet recognise PEACOCK; local
Linguist metadata and the prepared submission are not upstream acceptance.

## 1. Current verification

### Complete suite

```bash
python -m unittest discover -s tests -q
# Ran 668 tests in ~57s (644 prior + 6 LayerNorm + 18 Attention/Transformer)
# OK (skipped=2)
```

New in 2026-11-02/03: **Transformer stack — encoder + decoder with causal & cross-attention.**
* `peacock/intelligence/tensor.py:layer_norm`, `causal_mask(seq_q,seq_k)` and
  `scaled_dot_product_attention(..., is_causal)` — lower-triangular 1/0 mask,
  broadcast combine, -1e9 masked softmax; `matmul` rank N-D with batched ND.
* `peacock/intelligence/layers.py:LayerNorm` (γ/β, finite-diff), `MultiHeadAttention`
  (Xavier, split/combine, `is_causal` flag), `TransformerBlock` (872p @8/2/16),
  `CrossAttention` (Q decoder, K/V encoder, 8 tensors), `DecoderBlock` (causal
  self→cross→FFN, 3 norms), `positional_encoding` sinusoid, `Sequential`/`Model`
  with `causal_mask` support — 18 attention tests + causal/decoder smoke.
* PEACOCK DSL now accepts `सामान्यीकरण(सामान्यमान: N, सहिष्णुता: eps)`,
  `एकाग्रता(प्रारूपविस्तार: M, शीर्षसंख्या: H, कारणबद्ध: सत्य/असत्य)`,
  `रूपान्तरक(प्रारूपविस्तार: M, शीर्षसंख्या: H, अग्रविस्तार: F)`,
  `विसंकेतक(प्रारूपविस्तार: M, शीर्षसंख्या: H, अग्रविस्तार: F)` and
  `तिर्यगेकाग्रता(प्रारूपविस्तार: M, शीर्षसंख्या: H)`; `is_causal` preserved in
  `.बीज`, `disasm` shows `एकाग्रता(M,H,causal)`/`विसंकेतक`/`तिर्यगेकाग्रता`. CLI
  gives PE4001 hint `add --grant गणना`.
  see `tests/ai/test_attention.py`, `examples/transformer_demo.सूत्र`.

The two skips are explicit environment gates: the real OpenCL device parity
test and the real X11 open/draw/close test. CPU fallbacks, source-only mobile
shells and compile-only checks are not counted as hardware/device validation.

### Additional checks

```bash
./bin/peacock fuzz --iterations 1000 --seed 1
# lexer    OK handled=1000 crashes=0
# parser   OK handled=1000 crashes=0
# artifact OK handled=1000 crashes=0
# model    OK handled=666  crashes=0

python -m unittest tests.unit.test_documentation -q
# Ran 7 tests — OK

git diff --check
# clean
```

Focused development runs also passed:

| Area | Observed result |
|---|---|
| `tests/integration/test_finally.py` | 8/8: normal/catch/throw, return, break/continue, nested cleanup, supersession, optimizer parity and disassembly |
| self-host parser differential suite | 2/2: 15-file AST-digest corpus, finalization fixture, tokenizer/parser self-parse |
| self-host IR differential suite | 2/2: 16-file IR-digest corpus (hello/tour/xor/spiral/types/tokenizer etc.), oversized limit documented, 8 builtin IR checks |
| self-host bytecode differential suite | 3/3: 9-file core + 3 linguist bytecode-digest corpus (hello/tour/native/xor/spiral + fixtures), 8 builtin bytecode checks, tokenizer pending |
| self-host optimizer differential suite | 1/1: 16-file IR corpus lenient digest parity (Python vs PEACOCK 5-pass: const-fold/branch-fold/unreachable/peephole/DCE), 6 builtin optimizer checks |
| self-host VM differential suite | 1/1: 17-file lenient VM-digest parity (Python VM vs PEACOCK VM 7-check kernel: checked arithmetic + CALL recursion fact(5)=120 + FINALLY supersession + STRUCT/LIST ops (MAKE_LIST/LEN/INDEX/STRUCT_NEW/FIELD), slot/jump/RET/TRY/FINALLY, call-depth/host-grant budgets + 9 checks + native/pipeline stubs), 10 selfhost kernels, 17 example programs |
| bootstrap fixed-point | 3/3: Python fixed-point (10 selfhost programs → `.बीज` deterministic, 54,940 instr, artifact round-trip SHA-256), PEACOCK pipeline **strict** digest (via VM, **chunked literals** `CHUNK_SIZE=500` + **hash/len parity** `sha256[:16]+len`), `peacock.tools.bootstrap --write` emits `build/bootstrap/*.बीज` (`pipeline.सूत्र` now 4,460 instr/18 fns, 12 checks via wired `lex/parse/type/ir/bytecode/opt/vm` kernels) |
| native AOT | 8/8: real builds, deterministic C, VM-identical output, recoverable ABI faults and zero live allocations after success/fault runs |
| LLM + compute backends | 18 tests, 1 OpenCL skip: real loopback provider, schema/grant/budget/redirect checks, CPU and non-square matmul |
| HTTP server/finalization/LLM/GPU combined regression | 31 tests, 1 OpenCL skip after the final server hardening |

Fuzzing is deterministic and limited to those inputs; it is not a security
proof. Focused results are included in the complete-suite total, not added to it.

### Packaging and native execution

A `peacock_ai-0.4.0` wheel was built without dependencies, installed into an
empty temporary target and checked for version, all 3,983 sūtra records, four
executable sandhi IDs and `peacock/native/runtime.{c,h}`. The **installed**
package then compiled `examples/native.सूत्र` with a host C compiler. The resulting
standalone executable printed:

```text
native total: 30
native list: [1, 2, 3, 30]
स्वतन्त्रम्
```

The installed-package shared library returned the same output with zero live
allocations. The same generated example completed under AddressSanitizer and
UndefinedBehaviorSanitizer with leak detection enabled. The native
shared-library/desktop path was also built and inspected during
development: an x86-64 PIE desktop launcher used the generated PEACOCK C library
plus system C/math libraries, not Python, and its output matched the VM
byte-for-byte. Android/iOS were not built.

## 2. Working implementations

* **Sanskrit language/core:** hand-written Unicode lexer, recursive-descent
  parser and recovery diagnostics; NFC identifiers and Devanagari digits;
  static types/scopes/returns; capability checking; typed PIR, verification and
  optimisation; verified `.बीज` artifacts and disassembly; `अक्षरमाला.विपर्यय()`
  (string reverse, `examples/viparyaya.सूत्र` smoke-test) and `सूची.विपर्यय()`.
* **Runtime:** checked 64-bit arithmetic, lists/strings/structs/ranges, catchable
  faults, uncatchable panic/resource exits, nested `यत्न`/`गृह्ण`/`अन्ते`
  unwinding and cleanup supersession. `अन्ते` is included in the self-hosted
  tokenizer/parser and AST-digest oracle.
* **Independent native subset:** deterministic C11 control-flow generation,
  checked values/operators/lists/strings/functions, standalone executables and
  an embeddable `peacock_run` shared-library ABI with output callbacks and
  recoverable errors. Unsupported opcodes fail before C compilation.
* **AI:** broadcasting tensors, reverse-mode autodiff, Dense/LayerNorm/
  MultiHeadAttention/Transformer/CrossAttention/Decoder + positional_encoding +
  causal masking, SGD/Adam, XOR/spiral training, evaluation, `.ज्ञान`
  serialisation and int8 analysis; deterministic Dijkstra agents; bounded
  OpenAI-compatible LLM/tool agents with schemas, grants, traces and aggregate budgets.
* **Compute:** CPU addition/multiplication/ReLU/matmul and a real OpenCL 1.2
  implementation using device kernels/buffers. CPU tests pass, including
  non-square `[m,k] × [k,n]`; actual OpenCL execution remains untested here.
  Transformer/decoder training uses only the CPU autodiff path.
* **Graphics/UI:** advanced sRGB/XYZ/Lab/Oklab/Oklch colour, CIEDE2000, weighted
  and approximate-subtractive mixing, gamut mapping; RGBA canvas/PNG; CPU 3-D
  meshes/depth/lights; retained Sanskrit UI, layout, audits, bounded bubbling
  events, text/enabled/focus mutation and HTML export.
* **Interactive hosts:** browser `/event` + `/fragment` UI host and native X11
  window/pointer/key/close host. Real loopback browser event tests pass; the
  display-dependent X11 test is skipped without `DISPLAY`.
* **Servers:** fixed frame HTTP hosting and PEACOCK-owned synchronous HTTP
  listeners with numeric-IP binding, bounded UTF-8 requests/responses, actual
  port query and host cleanup. Real Sanskrit POST/201 and raw-socket negative
  tests pass.
* **Grammar:** attributed offline corpus of all 3,983 Aṣṭādhyāyī sūtra texts,
  inheritance/anuvṛtti display, generic Māheśvara pratyāhāra expansion, 20
  executable sandhi rules with varṇa/paribhāṣā/adhikāra ordering and derivation
  traces, plus śabda (12 paradigms)/dhātu (12 dhātus)/samāsa (17)/kāraka (9
  sentence kinds)/validator and 10 vyutpatti prakriyās (`6.1.77`, `6.1.78`,
  `6.1.87`, `6.1.88`, `6.1.101`, `6.1.109`, `6.1.113`, `8.2.39`, `8.3.15`, `8.3.23`,
  `8.3.34`, `8.4.40` etc.; 46 executable transforms via `sutra_engine` with 5
  paribhāṣā — 1.4.2 paraṃ kāryam, 1.4.1, 1.1.66, 1.1.67, 8.2.1 asiddha).
* **Self-host components:** PEACOCK-written tokenizer, full-grammar parser
  with AST-digest parity, deterministic `formatter.सूत्र` (brace-depth,
  operator spacing, idempotent) and user-module system (`उपयोग <file>;`
  file imports with recursive merge, qualified `module.func`, `रूपेण` aliases for file and builtin namespaces, circular detection, 233 compiler tests);
  experimental VM-executed semantic-shadow probes, `selfhost/ir.सूत्र` PIR builder (765 lines, 8 checks, 16-file parity) and `selfhost/bytecode.सूत्र` bytecode emitter (628 lines, 8 checks, 9-file core + 3 linguist parity) and `selfhost/optimizer.सूत्र` optimiser (650 lines, 6 checks, constant/branch/unreachable/peephole/DCE with 5-pass pipeline — `parser.सूत्र`/`type_model.सूत्र` exceed 256-slot VM limit). Python remains authoritative
  for production semantics, IR, bytecode and VM.
* **Applications/tooling:** twelve-route PEACOCK-authored static website,
  examples, CLI compiler/VM/native/grammar/audit/bench/fuzz/test commands,
  generated Linguist/VS Code grammars and linked subsystem manuals.

## 3. Partial implementations and explicit boundaries

* **Native AOT:** only the opcodes/natives listed in `docs/native.md`. General
  cleanup unwinding, structs/maps/objects, user modules, UI, HTTP, tensors/GPU
  and model declarations are not silently
  compiled. Embedded C state is currently process-global, not thread-safe or
  reentrant; the ABI is not stable across versions.
* **Language:** user modules are file-based `उपयोग` with qualified `module.func` and `रूपेण` aliases (flat+qualified merge, no visibility control or package versioning); generics, closures, enums/match, traits, first-class functions, general concurrency and async/await remain unimplemented.
* **LLM agents:** bounded iteration over host-registered tools, not AGI,
  unrestricted autonomy or a bundled model. No external hosted-model quality
  evaluation was performed. Tool handlers are cooperative and need their own
  I/O timeouts; schema validation is not semantic proof that an action is safe.
* **GPU:** four synchronous operations only. No OpenCL device was available;
  CUDA/Metal/Vulkan, device-resident graphs, GPU autodiff/training and GPU 3-D
  are not implemented.
* **UI:** no complete complex-script shaping, native accessibility API,
  text-input widget, drag/drop or general frame scheduler. Browser and X11 are
  limited hosts, not a finished cross-platform widget toolkit.
* **Servers:** plaintext development/native transports without authentication,
  TLS, multi-tenant isolation, chunked requests, pipelining, binary bodies or
  concurrent request dispatch. Loopback is the CLI default; exposure needs OS
  isolation and a hardened proxy.
* **Grammar:** 3,983 searchable texts; 46 executable transformations (20 sandhi + 26 paribhāṣā/kāraka/śabda/dhātu/samāsa). Executable coverage is measured separately from textual corpus.
  Declension, conjugation, samāsa, kāraka, ordered rule interaction and complete
  executable Pāṇini remain open. Connected-literature entries are a catalogue,
  not bundled full texts.
* **Models:** one input/output, Dense only, small local datasets and no general
  data pipeline. Quantised models are analysis output, not an executable format.
* **Self-hosting:** parser diagnostics/recovery and typed AST are incomplete;
  the semantic shadow does not cover every native/member/model rule. There is
  no compiler fixed point independent of Python.
* **CPython-scale completeness:** user modules, maps/containers, independent GC,
  concurrency, Unicode shaping, packaging and broad platform CI remain gaps.
  The pinned inspection and the implemented `अन्ते` response are recorded in
  [`docs/CPYTHON_AUDIT.md`](docs/CPYTHON_AUDIT.md).

## 4. Platform evidence

| Target | Current status | Evidence / missing gate |
|---|---|---|
| Linux VM/headless | working | complete suite and real CLI examples |
| Static web/frame host | working | PNG/manifest/HTML and real HTTP tests |
| Interactive browser UI | working development host | real POST wakes VM and republishes Sanskrit UI |
| PEACOCK HTTP server | working bounded subset | real request/response and raw-socket limits |
| Native executable/library | working documented subset | real C builds, `ctypes` ABI and installed-wheel smoke |
| Linux desktop shell | executed | x86-64 PIE; VM-identical output |
| Native X11 window | implementation + model tests | real display test skipped; requires X11/`DISPLAY` |
| OpenCL | implementation + CPU reference | hardware parity skipped; no device/driver |
| Android | source/generated-C only | SDK/NDK, JNI build, APK and emulator/device tests pending |
| iOS | source only | Xcode simulator/device/signing/distribution tests pending |
| WebAssembly | not implemented | backend and browser ABI required |
| Non-Linux desktop | not tested | no hosts available |

## 5. Historical bootstrap benchmarks

The checked-in reference snapshot was generated at commit `755fbc8` on a dirty
working tree: CPython 3.11.2, Linux 6.1.158 x86_64, 2 vCPUs, 3.8 GiB RAM, no
GPU. It was **not re-run** for 0.4 and contains no native-AOT/GPU comparison.
Generate a new report with `./bin/peacock bench --json benchmarks/latest.json`.

| Category | Measurement | Historical result |
|---|---|---:|
| Compiler | hello, full pipeline | 0.518 ms |
| Compiler | tour (63 lines, 477 instrs) | 4.130 ms |
| Compiler | selfhost tokenizer | 14.793 ms |
| Compiler | synthetic throughput | 311.6 KiB/s |
| Runtime | tight loop, 640,027 steps | 224.9 ms |
| Runtime | VM dispatch | 2.85 M steps/s |
| Intelligence | 48×48 matmul | 8.032 ms (27.5 MFLOP/s) |
| Intelligence | XOR, 100 epochs | 30.148 ms (loss 0.010279, acc 1.0) |
| Frontend | 320×180 gradient | 123.7 ms |
| Frontend | PNG encode 320×180 | 73.5 ms |
| Motion | spring substeps | 772,727 steps/s |

These values describe the pure-Python bootstrap on one container, not native
PEACOCK or production hardware. See `research/benchmark-methodology.md`.

## 6. External boundaries and known deviations

* Core runtime/tests use Python 3.11 standard-library modules; no NumPy,
  PyTorch, LLVM, React or third-party runtime package is required. Optional
  native builds need a C compiler; X11/OpenCL/mobile toolchains are platform
  boundaries. An LLM provider is contacted only when explicitly configured and
  invoked; no provider is bundled.
* Float32 tensors round on storage but arithmetic uses binary64 before storage;
  this is a documented deviation from strict binary32 arithmetic.
* `Int / Int` truncates toward zero and `%` takes the dividend's sign.
* VM memory is managed by CPython, including its own cyclic GC outside PEACOCK
  semantics. There is no independent language GC API; native AOT tracks and
  releases run-scoped allocations. Neither provides a complete process-memory quota.
* Capability confinement is process-level and best effort, with filesystem
  TOCTOU exposure. It is not a kernel sandbox or proof of multi-tenant safety.
* Tokenizer parity compares counts and non-string token classification; string
  escape decoding is not fully differentially asserted. Parser AST digests
  intentionally elide literal values and source spans.
* `.gitattributes` is only a local language hint. The Linguist submission is
  prepared, not submitted/accepted; VS Code metadata is not a published extension.

## 7. Next priorities

1. Broaden cited executable grammar rules and derivation/ambiguity tests.
2. Harden UI tree concurrency, shaping/accessibility and real-display coverage.
3. Expand VM/native differential coverage and make embedded native state
   thread-safe before claiming concurrent embedding.
4. Run Android/iOS/X11/OpenCL platform CI on real toolchains/hardware.
5. Complete self-host parser diagnostics and semantic parity without promoting
   the experimental shadow prematurely.
6. Add user modules, deterministic packaging and the next independent compiler
   stages; do not label bounded agents as AGI or subset servers as production
   multi-tenant infrastructure.

See [ROADMAP.md](ROADMAP.md) for acceptance criteria and dependencies.
