# PEACOCK Status

Last verified: **2026-10-22** (working tree on the Arena development branch;
not committed). Re-run the commands below before trusting any number.

Canonical source extension: `.सूत्र`. The compiler is **not self-hosting**; the
reference implementation is a Python bootstrap. GitHub does **not** yet
recognise PEACOCK as a language; the Linguist submission is prepared, not
accepted.

## 1. Verification commands and results

```bash
./bin/peacock test
# Ran 511 tests in 44.960s — OK (v0.2.0, 2026-10-22)
```

This run is from the current uncommitted Arena working tree and includes the
Sanskrit lexical/Unicode, semantic-shadow, filesystem capability, documentation, and PEACOCK-authored website regressions.

| Suite | Tests | Result |
|---|---:|---|
| `tests/compiler` | 227 | OK |
| `tests/ai` | 81 | OK |
| `tests/frontend` | 74 | OK |
| `tests/security` | 37 | OK |
| `tests/integration` | 65 | OK |
| `tests/unit` | 21 | OK |
| `tests/benchmarks` | 6 | OK |
| **Total** | **511** | **OK** |

```bash
./bin/peacock fuzz --iterations 1000 --seed 1
# lexer OK handled=1000 crashes=0
# parser OK handled=1000 crashes=0
# artifact OK handled=1000 crashes=0
# model OK handled=666 crashes=0
```

The fuzzers are deterministic but not exhaustive. A clean run is evidence against
crashes on those inputs, not a security proof.

## 2. Featured real executions

All commands were run from the repository root on the reference machine.

| Command | Observed result |
|---|---|
| `./bin/peacock run examples/hello.सूत्र` | `Hello from PEACOCK`; 6 bytecode steps |
| `./bin/peacock run examples/tour.सूत्र` | prints `sum: 55`, `caught: doubled() does not accept negative numbers`, `types: अक्षरमाला, दशमलव, सूची` |
| `./bin/peacock run examples/xor.सूत्र --grant गणना` | 400 epochs, final loss `0.0013468142908857894`, accuracy `1.0` |
| `./bin/peacock run examples/spiral.सूत्र --grant गणना` | 48 samples, 250 epochs, final loss `0.06998025545183473`, accuracy `1.0` |
| `./bin/peacock run examples/tensors.सूत्र --grant गणना` | autodiff and closed-form MSE gradients agree, `max abs difference: 0.0` |
| `./bin/peacock run examples/aurora.सूत्र --grant सञ्चय` | writes `examples/out/aurora.png` (960×540, 162,337 bytes, valid PNG) |
| `./bin/peacock run selfhost/tokenizer.सूत्र --grant सञ्चय -- examples/tour.सूत्र` | prints `367`, equal to the bootstrap lexer's token count minus EOF |
| `./bin/peacock run selfhost/parser.सूत्र --grant सञ्चय --root . --max-steps 300000000 -- examples/xor.सूत्र` | AST digest identical to the bootstrap on the 14-file corpus; parses its own 1,131-line source with identical digest |
| `./bin/peacock run selfhost/type_model.सूत्र` | 56 PEACOCK assertions pass, including ErrorType iterable recovery |
| `./bin/peacock check examples/tour.सूत्र --semantic-shadow --json` | Experimental VM-executed semantic probes pass; JSON includes type/semantic/builtin probe counts |
| `./bin/peacock run examples/present.सूत्र --grant दृश्य --present out/preview` | prints `presented 4 frames`; manifest lists 4 × 320×180 frames; `latest.png` decodes to 230,400 RGBA bytes |
| `./bin/peacock run examples/present.सूत्र --grant दृश्य` (no backend) | PE4006, exit 3; the host, not the program, decides where frames go |
| `./bin/peacock run examples/present.सूत्र --grant दृश्य --serve 8099 --linger 2` | `/manifest.json` reports 4 frames and a 320×180 latest frame; `/frame.png` decodes; `/` serves script-free HTML; the port closes after exit |
| `./bin/peacock build examples/hello.सूत्र -o /tmp/hello.बीज` | 615-byte verified artifact; language 0.2, format 1, SHA-256 `67655b3d266dc095e88ce24af7ee8d16452032c3bd7cbfc6437f737782a6a646` |
| `./bin/peacock check website/site.सूत्र` | PEACOCK source checks; 32 functions, 4,574 instructions |
| `./bin/peacock run website/site.सूत्र --grant सञ्चय --root . --max-steps 10000000 -- website/dist` | Generates 12 HTML routes, responsive CSS and the project SVG through the real CLI/compiler/VM; no JS bundle |
| `python -m unittest tests.integration.test_website -v` | 4 website export/audit tests pass |

The integration suite re-runs the examples through the CLI, including the PNG
decode, training report JSON, tokenizer parity, artifact tampering rejection and
capability-denial exit code.

## 3. Component status

### Working (implemented and tested)

* hand-written lexer, recursive-descent parser, AST, caret diagnostics, error
  recovery, reserved-keyword messages;
* static types (`पूर्णाङ्क`, `दशमलव`, `सत्यता`, `अक्षरमाला`, `एकक`, `अभाव`,
  `सूची`, `आयाम`, structs, opaque host types), scopes, definite-return checks, homogeneous list literals,
  static tensor shape/dtype checks;
* Sanskrit reserved vocabulary, NFC identifiers, combining marks, Unicode decimal
  digits, native type/option displays, and PE1007 rejection of withdrawn English
  reserved words;
* capability declarations, static enforcement, runtime enforcement, host grants;
* typed PIR, verifier, constant/branch folding, DCE, peephole optimiser;
* bytecode compiler, independent image verifier, `.बीज` container with SHA-256,
  disassembler, capability audit;
* stack VM with checked arithmetic, lists, strings, structs, ranges, try/catch,
  uncatchable panics and resource budgets;
* capability sandbox: path traversal/absolute/symlink/NUL/file-size rejection; `सञ्चय.निधिरचना` is grant-gated and sandbox-rooted;
* tensor engine with broadcasting, matmul, reductions, activations, softmax,
  reverse-mode autodiff; finite-difference checks pass;
* Dense/Sequential models, XOR and spiral datasets, SGD/Adam, cross-entropy/MSE,
  training reports, evaluation metrics, `.ज्ञान` save/load, int8 quantisation
  helpers;
* sRGB/XYZ/CIELAB/Oklab/Oklch colour, WCAG contrast, palettes, gradients;
* premultiplied RGBA canvas, 4×4 AA shapes, glow, aurora, PNG encode/decode with
  CRC checks and HDR tone mapping;
* easing, cubic Bézier, springs, timelines, flex layout, 2-D AABB physics;
* headless, static-web and HTTP frame host adapters;
* `चित्र.प्रदर्शय` native with the `दृश्य` capability and an attached-backend
  contract; `--present DIR` drives `WebBackend` from a real program; backend
  failures are wrapped as PE5003 and never leak host exceptions into the VM;
* CLI (`version`, `check`, `run`, `build`, `disasm`, `audit`, `tokens`, `ast`,
  `bench`, `fuzz`, `test`) with JSON modes and exit codes;
* deterministic fuzzers for lexer/parser/artifact/model loaders;
* PEACOCK-written tokenizer with bootstrap token parity;
* PEACOCK-written full-grammar parser (stage 2a) with canonical AST-digest parity
  on examples, Linguist samples and itself; strict first-error diagnostics;
* PEACOCK-authored static website exporter (`website/site.सूत्र`) with twelve
  routes, reusable app-specific components, responsive CSS and SVG; actual CLI/
  compiler/VM export and integration checks for links, structure and source;
* opt-in semantic shadow checks on typed-AST relations, expressions, local
  scopes/names, assignments, user-function calls/returns and loop conditions;
  Python remains the authority and the kernel does not produce diagnostics.

### Documentation, research and tooling

* specification with full EBNF grammar, Sanskrit grammatical/literary rationale,
  architecture, roadmap and status are checked in and cross-linked;
* research programme: 178-entry bibliography, Sanskrit/Pāṇinian literature and
  verified arXiv metadata, literature review, 18 open
  questions, 22 ADRs and benchmark methodology;
* Linguist package prepared (language entry, TextMate grammar, six compiled
  samples, logo); **not submitted and not recognised by GitHub**;
* VS Code package prepared (grammar + language configuration); **not published**;
* documentation tests check relative links, citation keys, the grammar, sample
  compilation, all fenced PEACOCK documentation examples, generated-grammar
  freshness, and the PNG icon (7 tests).

### Partial

* **Language:** no user modules, generics, closures, enums/match, traits,
  concurrency, operator definitions, or first-class functions.
* **Frontend:** a twelve-route static site is now authored in `.सूत्र` and exported
  by the actual toolchain; it is not a general UI toolkit. No general widget
  library, text shaping, native accessibility APIs, 3D, or GPU rasterisation.
  Motion/physics have no frame scheduler integration.
* **Platforms:** the `--present` static frame viewer and `--serve` HTTP frame host
  are reachable from `.सूत्र`; separately, `website/site.सूत्र` produces static
  application pages. There is no input, frame clock or vsync, and the HTTP frame
  host is a development boundary, not a hardened server. No desktop window
  shell, Android, iOS or WASM target.
* **Models:** one input/output, Dense only, SGD/Adam, small synthetic datasets.
* **Self-hosting:** the PEACOCK tokenizer and full-grammar parser have the
  existing parity evidence; `selfhost/type_model.सूत्र` now provides a broader
  experimental type/expression/scope kernel. The opt-in compiler/CLI shadow
  adapter emits VM-executed probes from the typed AST for supported expressions,
  declarations, names, assignments, user-function signatures/calls, conditions
  and returns. Tests cover the compiled `.सूत्र` corpus, valid/invalid cases and
  selected diagnostic equality, including ErrorType iterable recovery. Python
  remains authoritative; the kernel does not generate diagnostics and is not a
  production switch. The parser still lacks error recovery, full `PE2xxx`
  diagnostic/span parity and a typed self-hosted AST; production semantics, IR,
  code generation and VM remain Python.
* **Diagnostics:** warning quality is intentionally minimal; no machine-readable
  fixes or LSP.

### Planned / not implemented

* native code generation, typed tensor buffers, GPU kernels;
* convolution/attention/sequence layers, data pipeline, mixed precision;
* UI toolkit, text, 3D, image codecs beyond PNG;
* desktop/Android/iOS/WASM hosts;
* package manager, formatter, linter, LSP, debugger;
* AGI research tooling beyond reproducibility and evaluation infrastructure.

### Untested

* mobile devices and emulators (no SDKs/macOS here);
* GPU paths (none implemented);
* multi-tenant or adversarial host isolation beyond the tests listed;
* large models/datasets, long-running training, memory pressure;
* non-Linux hosts;
* browser rendering/interaction and visual layout of the generated website (the
  static HTML/CSS is audited by source-level integration tests; no browser or
  screenshot automation has been run);
* any claim of formal verification or cryptographic security.

## 4. Benchmarks (reference machine)

Environment: CPython 3.11.2, Linux 6.1.158 x86_64, 2 vCPUs, 3.8 GiB RAM, no GPU,
historical reference snapshot generated at commit `755fbc8` on a dirty working
tree (per the checked-in report metadata). It was not re-run as part of the
current status update; full JSON is retained for reproducibility. Generate a new
report with `./bin/peacock bench --json benchmarks/latest.json`.

| Category | Measurement | Result |
|---|---|---:|
| Compiler | hello, full pipeline | 0.518 ms |
| Compiler | tour (63 lines, 477 instrs) | 4.130 ms |
| Compiler | selfhost tokenizer (235 lines, 1932 instrs) | 14.793 ms |
| Compiler | 200 functions, 9.5 KiB | 28.592 ms |
| Compiler | synthetic throughput | 311.6 KiB/s |
| Compiler | peak memory, tokenizer compile | 0.843 MiB |
| Runtime | tight loop, 640,027 steps | 224.9 ms |
| Runtime | VM dispatch | 2.85 M steps/s |
| Runtime | hello startup (load+run) | 0.136 ms |
| Intelligence | 48×48 matmul | 8.032 ms (27.5 MFLOP/s) |
| Intelligence | 128×128 softmax | 2.775 ms |
| Intelligence | MLP train step, batch 16 | 2.547 ms |
| Intelligence | XOR, 100 epochs | 30.148 ms (final loss 0.010279, acc 1.0) |
| Intelligence | single inference | 0.039 ms |
| Frontend | 320×180 gradient | 123.7 ms |
| Frontend | 160×90 aurora | 100.6 ms |
| Frontend | PNG encode 320×180 | 73.5 ms |
| Frontend | 512×512 UI frame (40 shapes) | 30.7 ms |
| Motion | spring substeps | 772,727 steps/s |
| Motion | easing calls | 3.27 M calls/s |

These numbers characterise the **pure-Python bootstrap**, not native PEACOCK.
They must not be compared against optimised engines without identical workloads
and methodology. See `research/benchmark-methodology.md`.

## 5. Platform support

| Host | Status | Evidence / note |
|---|---|---|
| Linux headless | working | `tests/frontend/test_platforms.py` |
| HTTP frame server | working | same suite, real HTTP requests |
| Static web viewer (`WebBackend`) | working | HTML + PNG, no JavaScript |
| PEACOCK-authored static website exporter | working | 12 routes via `website/site.सूत्र`; `tests/integration/test_website.py` (no browser visual suite) |
| Desktop window | not implemented | needs a windowing boundary |
| Android | not implemented | needs SDK/NDK + JNI/ABI bridge |
| iOS | not implemented / blocked | requires macOS + Xcode, unavailable here |
| WebAssembly | not implemented | needs a backend |

## 6. External dependencies

Runtime and tests use only Python 3.11 standard-library modules (`zlib`,
`hashlib`, `struct`, `unittest`, `http.server`, `urllib`, `json`, `base64`,
`threading`, `tempfile`, `pathlib`, `math`, `random`). There are no third-party
packages, no network services, no cloud APIs and no downloaded datasets. The
spiral dataset is generated locally. PEACOCK source files are UTF-8; `.बीज` and
`.ज्ञान` artifacts are binary.

## 7. Known deviations and limitations

* **Float32** tensors round on storage but arithmetic uses binary64 before the
  store. This differs from strict IEEE-754 binary32 and is documented in the
  spec.
* **`Int / Int`** truncates toward zero; **`Int % Int`** takes the dividend's
  sign. This is defined, not accidentally Python's floor division.
* **No garbage collector** is implemented for PEACOCK values; the Python host
  owns memory. Cycles are not collected.
* **Capabilities** are enforced by the VM and the host policy, not by the OS.
  `HostPolicy` is a best-effort sandbox and has TOCTOU exposure between path
  resolution and file access.
* **Quantisation** is tested for size/error at the parameter level; quantised
  models are not yet a first-class executable artifact format.
* **Tokenizer parity** currently compares counts and non-string token
  classification; string escape decoding parity is not yet asserted.
* **Parser parity** compares structural AST digests; literal values and source
  spans are deliberately elided, and the self-hosted parser stops at the first
  error with `PE4020` instead of reproducing the bootstrap `PE2xxx` diagnostics.
* **GitHub recognition**: `.gitattributes` maps `.सूत्र` to `linguist-language=Peacock`
  for this repository, but that is a local hint, not upstream recognition.
  `linguist/` contains a prepared submission; it has not been accepted.
* **Benchmark environment** is a small 2-vCPU container; numbers are not
  representative of production hardware.

## 8. Next steps

1. Complete the parser stage (error recovery, diagnostic/span parity, typed AST)
   and port the semantic analyser; add `enum`/`match` only as the port requires.
2. Add a live `--serve`/`ServerBackend` path and input/frame-clock semantics on
   top of the existing `चित्र.प्रदर्शय` contract.
3. Add a native/WASM backend for the verified subset with honest, non-comparative
   benchmark reporting.

See [ROADMAP.md](ROADMAP.md) for phases and acceptance criteria.
