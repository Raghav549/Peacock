# PEACOCK Repository Audit — 2026-11-03

Branch: `arena/c0fe52eb-peacock` (668 tests OK, skipped=2; all 8 selfhost kernels OK + 18 attention tests, causal/cross/decoder landed)

This file fulfills **Phase A — Audit** of the self-hosting migration strategy.

## 1. Python Dependency Graph

### Compiler & Language Front-end (authoritative, to be replaced by PEACOCK)
| Python module | LOC | Responsibility | Self-host replacement | Status |
|---|---|---|---|---|
| `peacock/compiler/lexer.py` | 412 | Unicode lexer, NFC, Devanagari digits, diagnostics | `selfhost/tokenizer.सूत्र` 235L + `selfhost/parser.सूत्र` 1142L lex stage | **done** — parity-tested, `selfhost/tokenizer.सूत्र` `OK` |
| `peacock/compiler/parser.py` | 766 | Recursive-descent parser, recovery | `selfhost/parser.सूत्र` 1142L | **done** — 15-file AST digest, strict errors (no recovery) |
| `peacock/compiler/tokens.py` | 159 | Token tables, `KNOWN_CAPABILITIES` | `selfhost/type_model` + `peacock/sanskrit.py` | **partial** — capability list duplicated in `host.py` |
| `peacock/compiler/types.py` | 206 | `PrimitiveType`, `Tensor<dtype,shape>` | `selfhost/type_model.सूत्र` 563L | **experimental** — typed AST probes, Python authoritative |
| `peacock/compiler/semantic.py` | 2110 | Scopes, return/capability/type checking, `अन्ते` unwind | `selfhost/type_model.सूत्र` | **partial** — covers `यत्न/गृह्ण/अन्ते` but not every native/member/model rule |
| `peacock/compiler/ir.py` | 873 | PIR: slots + virtual `regs`, labels/jumps | `selfhost/ir.सूत्र` 774L | **done** — 53 fns, 6376 instrs, 8 checks, 16-file digest |
| `peacock/compiler/bytecode.py` | 431 | Stack bytecode, `STORE_SLOT/BINOP/CALL/.../FINALLY`, `verify_image` | `selfhost/bytecode.सूत्र` 635L | **done** — 83 fns, 4702 instrs, 8 checks, 9+3 file digest |
| `peacock/compiler/optimizer.py` | 355 | 5-pass: const-fold, branch-fold, unreachable, peephole, DCE | `selfhost/optimizer.सूत्र` 650L | **done** — 28 fns, 8516 instrs, 6 checks, lenient IR digest (16 files) |
| `peacock/compiler/diagnostics.py` | 200 | `PE1xxx–PE6xxx` spans, `add_trace` | mirrored in PEACOCK via `क्षिप` + `VMFault` | **partial** — PEACOCK diagnostics not yet native |
| `peacock/compiler/pipeline.py` | 305 | `compile_source` orchestration | to be `peacock/tools/compile.सूत्र` | **missing** — still Python-only |
| `peacock/compiler/selfhost_*.py` | 287+407+253+197 | Differential oracles (IR/bytecode/optimizer/VM) | — | **done** — Python oracle, PEACOCK kernel under test |
| `peacock/sanskrit.py` | — | `INTERNAL_TO_SOURCE`, `LEGACY_KEYWORDS`, `surface` | needs PEACOCK lexer tables | **partial** |
| `peacock/tools/formatter.py` | — | `peacock fmt` | `selfhost/formatter.सूत्र` 169L | **done** — 8 fns, 1011 instrs |

### Runtime & VM (to be independent of Python objects)
| Module | LOC | Responsibility | Native boundary |
|---|---|---|---|
| `peacock/runtime/vm.py` | 745 | Stack VM, `Handler/Completion/Cleanup`, `Frame`, `CALL`, `TRY/CATCH/FINALLY`, `RET`, budgets (`max_steps=2M`, `max_call_depth=128`, `max_output=1M`), `HostPolicy` caps/fs | **PEACOCK kernel `selfhost/vm.सूत्र` 517L** — 40 fns, 5990 instrs, **9 checks**, single→multi-frame, `vm_host_has_grant`, `vm_invoke`, depth `गभीरता`, grants `अनुदानानि` |
| `peacock/runtime/host.py` | ~120 | `HostPolicy` (grants/root/max_tensor/max_dataset/max_epochs/max_file, `presenter`, `llm_runner`, `server_handles`) | C11 sandbox (`root` resolve, symlink TOCTOU best-effort) remains |
| `peacock/runtime/native.py` | 1664 | `NativeContext`, `call_native/call_method/get_property`, `native_capability/method_capability`, capability mapping per native, tensor/model/LLM/colour/canvas/scene dispatch | **staged** — PEACOCK VM stubs `CALL` only; full `native.py` still Python |
| `peacock/runtime/values.py` | — | `UNIT`, `RangeValue`, `StructInstance`, `Tensor` | Python objects as value repr (doc’d temporary) |
| `peacock/runtime/artifact.py` | — | `.बीज` verify/serialize (now includes `attention{is_causal}`, `decoder`, `cross_attention` layers) | Python `verify_image` still authoritative |
| `peacock/runtime/errors.py` | — | `VMFault`, `PanicError`, `ResourceLimitError`, `CapabilityError` | PEACOCK `क्षिप` + `PE4xxx` |
| `peacock/intelligence/*` | — | `tensor.py` (broadcast, autodiff, `causal_mask`/`scaled_dot_product_attention`), `layers.py` (Dense/LayerNorm/MHA/Transformer/CrossAttention/Decoder/positional_encoding, 827L), `training.py` (Dense/SGD/Adam, `.ज्ञान`), `gpu.py` (CPU/OpenCL), `llm.py`, `agent.py` | CPython-only; no PEACOCK tensor kernel yet; `causal`/`cross` not yet in selfhost IR |
| `peacock/frontend/*` | — | `colour.py` (sRGB/XYZ/Lab/Oklab/Oklch, CIEDE2000, gamut), `canvas.py`, `scene3d.py`, `ui.py`, `physics.py`, `spring.py`, etc. | Working but CPython; PEACOCK colour/3D APIs exist but not self-hosted |
| `peacock/platforms/*` | — | `headless.py`, `httpd.py`, `server.py`, `window.py`, `web.py` | Python hosts; PEACOCK `present.सूत्र` etc. use them |
| `peacock/native/*` | — | `builder.py`/`codegen.py` → deterministic C11, `peacock_run` ABI | C11 boundary allowed; VM-identical output verified |
| `peacock/cli.py` | — | `init/new/build/run/test/check/fmt/lint/package/install/doc/debug/train/infer/agent/scene/colour` | Python `argparse`; PEACOCK CLI staged |
| `peacock/vyakarana/*` | — | 3,983 sūtra texts, `sandhi.py` (20), `sutra_engine.py` (46), `dhatu/samasa/karaka/shabda/validator` | Executable coverage 46/3983; grammar is searchable corpus, not full executable Aṣṭādhyāyī |
| `peacock/tools/package.py` | — | package manager, `peacock install` | Python; PEACOCK manager missing |

**Zero external pip dependencies** (`pyproject.toml dependencies = []`). Optional native hosts need C compiler, X11/OpenCL drivers, Android SDK/Xcode — all platform boundaries, not pip.

## 2. Completed / Partial / Missing

**Working & tested (evidence in STATUS.md):**
- Lexer/parser with recovery diagnostics (668 tests), typed PIR + optimiser + bytecode + VM `अन्ते` (nested unwinding), tensor transformer stack (causal mask, MHA, CrossAttention, DecoderBlock, LayerNorm, positional_encoding, 18 attention tests), native AOT deterministic C, bounded agents (rule/Dijkstra + LLM/tool loopback), CPU/OpenCL tensor ops (OpenCL hardware skip), colour science + 2D/3D, UI/layout/events, HTTP frame server, desktop shell, grammar 20 sandhi + 46-transform ordered engine with 5 paribhāṣā and derivation traces.

**Partially completed:**
- Self-host: tokenizer ✅, parser ✅ (no recovery), `type_model` ⚠️ experimental, IR ✅, bytecode ✅, optimizer ✅ (lenient), VM ✅ (checked arithmetic, slots/jumps/RET/TRY, CALL + recursion + depth + host grants, 9 checks, 17-file lenient digest; full `HOST`, `FINALLY`, `STRUCT/FIELD/INDEX/LIST/RANGE/LEN/ASSERT/THROW` and tensor/model native dispatch still Python), formatter ✅; new `attention{is_causal}/decoder/cross_attention` DSL is Python-authoritative until selfhost IR extends.
- CLI: `fmt/new/init/lint/doc` now have PEACOCK `formatter.सूत्र` backing, but `cli.py` itself and `check/test/build/package` still Python; `peacock run` now hints `add --grant गणना` on PE4001.
- Grammar: 3,983 searchable + 20 sandhi + 46 transforms (5 paribhāṣā, adhikāra/anuvṛtti, derivation traces, 12 śabda/12 dhātu/17 samāsa/9 kāraka); broader consonant/visarga sandhi and fuller paradigms remain open.

**Broken / Missing (roadmap):**
- No PEACOCK-native pipeline hosting all kernels via chunked staged compilation (pipeline.सूत्र still Dense-only stable), `host.सूत्र`, `native.सूत्र`, tensor/autodiff/LLM, UI/3D engine, `agent.सूत्र` runtime; no user module re-exports, generics, closures, pattern matching, `map`, iterators, async/concurrency, GC, reflection, macros.
- Python retirement **not started** — correct per Phase D gate. `verify_image`, `NativeContext`, `HostPolicy` root resolve, `.बीज`/`.ज्ञान` remain Python.
- Strict VM digest equality not yet: Python bytecode `code len` vs PEACOCK `vm_module_digest` literal `\\n` are lenient.

## 3. Duplicates & Inconsistencies

- `ir.सूत्र` types duplicated in `optimizer.सूत्र` and `bytecode.सूत्र` (intentional bootstrap, to be unified in `type_model.सूत्र`).
- `KNOWN_CAPABILITIES` defined in both `peacock/compiler/tokens.py` and `peacock/runtime/host.py` (frozenset mirror).
- `README` honest-status vs `STATUS` verified counts reconciled 2026-11-03 (668 tests, 3,983 sūtra, 9 VM checks, 20/46 grammar, causal/cross/decoder landed).
- `.सूत्र` is Linguist hint only; GitHub does not recognise PEACOCK yet (submission prepared not accepted).

## 4. Test Coverage Gaps

- 668 tests cover lexer/parser/semantic/IR/VM/`अन्ते`/capabilities/tensor/training (dense+transformer)/colour/3D/UI/platforms/native/grammar (20 sandhi + derivation traces).
- Skipped: real OpenCL device parity, real X11 `DISPLAY` open.
- Not covered: self-host VM CALL/native, `FINALLY` differential (8/8 `test_finally` still Python VM), multi-tenant TOCTOU, HDR/wide-gamut, Android/iOS/X11 hardware, LLM provider live, tensor GPU vs CPU parity, full Aṣṭādhyāyī derivation/ambiguity.

## 5. Migration Path Forward

**Phase B next:** finish `vm.सूत्र` FINALLY/Cleanup supersession, `STRUCT/FIELD/INDEX/MAKE_LIST/RANGE/LEN`, `native.सूत्र` stubs, `pipeline.सूत्र`; then **Phase C bootstrap** (compile `selfhost/*.सूत्र` with PEACOCK compiler, compare `.बीज`, fixed-point test); only then Phase D Python retirement.

> “Do not hide Python behind another interface. Make PEACOCK genuinely independent.” — C11 remains allowed for OS/hardware, but compiler/semantics/runtime/AI/stdlib must become PEACOCK-native.
