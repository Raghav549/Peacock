# PEACOCK AI

**An AI-native programming language and computing ecosystem, built from first principles.**

PEACOCK is a long-horizon systems and research project. It aims to unify
differentiable computation, model training and inference, an original compiler and
runtime, a perceptual UI/graphics stack, motion and physics, capability-based
security, and multiple deployment hosts behind one coherent language.

**Canonical source extension: `.pac`.** Compiled programs use `.pkb`; models use
`.pkm`. `.pk` and `.peacock` are **not** accepted by the toolchain.

> **Honest status (v0.1.0, phase 1–3 of 10).** The lexer, parser, type checker,
> typed IR, optimiser, bytecode compiler, stack VM, tensor/autodiff engine,
> small-model trainer, colour pipeline, 2D software renderer, PNG codec, motion,
> layout, and physics subsystems are implemented and exercised by **490 tests**.
> The web/headless/server presentation adapters are implemented. Native mobile
> shells, a native code generator, GPU kernels, a full UI toolkit, 3D rendering,
> and AGI research tooling are **not implemented**. The compiler is **not
> self-hosting**; a PEACOCK lexer and a full-grammar parser are parity-tested
> against the bootstrap, but semantics, IR and code generation remain Python.
> GitHub does **not** yet recognise `.pac`; a Linguist submission is prepared in
> [`linguist/`](linguist/), not accepted. See [STATUS.md](STATUS.md) for evidence.

## What works today

| Area | Status | Evidence |
|---|---|---|
| Lexer, parser, recovery diagnostics | Working | `tests/compiler/test_lexer.py`, `test_parser.py` |
| Static types, scopes, capability checking | Working subset | `tests/compiler/test_types.py`, `test_semantic.py` |
| Typed IR, verifier, optimiser, bytecode | Working | `tests/compiler/test_ir.py`, `test_pipeline.py` |
| Stack VM, checked arithmetic, try/catch | Working | `tests/compiler/test_vm.py` |
| Capability sandbox and budgets | Working (best effort) | `tests/security/test_capabilities.py` |
| Tensor engine, broadcasting, autodiff | Working (CPU, pure Python) | `tests/ai/test_tensor.py` |
| Dense models, training, evaluation | Working (small models) | `tests/ai/test_training.py` |
| Model save/load, int8 quantisation | Working (custom `.pkm` v1) | `tests/ai/test_training.py` |
| Colour science (sRGB/XYZ/Oklab/Oklch/Lab) | Working | `tests/frontend/test_colour.py` |
| Software 2D rasteriser, PNG encode/decode | Working | `tests/frontend/test_canvas_png.py` |
| Easing, springs, timelines, flex layout, 2D physics | Working | `tests/frontend/test_motion.py` |
| Headless, static-web, HTTP frame hosts | Working library adapters | `tests/frontend/test_platforms.py` |
| Frame presentation from `.pac` (`graphics.present`, capability `ui`) | Working; static-web backend via `--present` | `examples/present.pac`, `tests/integration/test_presentation.py` |
| PEACOCK-written tokenizer | Working; parity-tested | `selfhost/tokenizer.pac`, `tests/integration/test_cli.py` |
| PEACOCK-written full-grammar parser | Working (syntax); strict errors, no recovery yet | `selfhost/parser.pac`, `tests/integration/test_selfhost_parser.py` |
| Native UI toolkit, 3D, GPU, native codegen | **Not implemented** | Roadmap phases 5–8 |
| Android/iOS/desktop shells | **Not implemented** | `docs/platforms/README.md` |
| Official GitHub language recognition | **Not accepted** | `linguist/SUBMISSION.md` |

## Quick start

Requirements: **Python 3.11+**, standard library only. The Python toolchain is a
deliberately temporary bootstrap, separated from the language definition and the
planned self-hosted compiler (ADR-0001 in
[`research/architecture-decisions.md`](research/architecture-decisions.md)).

```bash
./bin/peacock version
./bin/peacock check examples/hello.pac
./bin/peacock run examples/hello.pac

# Train an XOR network declared in PEACOCK
./bin/peacock run examples/xor.pac --grant compute

# Differentiable tensors and an analytic gradient check
./bin/peacock run examples/tensors.pac --grant compute

# Render a procedural aurora to a real PNG
./bin/peacock run examples/aurora.pac --grant fs
# -> examples/out/aurora.png

# Present animated frames to a host presentation backend
./bin/peacock run examples/present.pac --grant ui --present out/preview
# -> out/preview/latest.png, manifest.json, frames/frame_0000..0003.png

# Serve frames over HTTP while the program runs (then keep the last one)
./bin/peacock run examples/present.pac --grant ui --serve 8099 --linger 30
# -> http://127.0.0.1:8099/  /frame.png  /manifest.json  /healthz

# Build and execute a bytecode artifact
./bin/peacock build examples/hello.pac -o /tmp/hello.pkb
./bin/peacock run /tmp/hello.pkb

# Inspect, audit, benchmark, fuzz, test
./bin/peacock disasm examples/xor.pac
./bin/peacock audit examples/xor.pac --json
./bin/peacock bench --json benchmarks/latest.json
./bin/peacock fuzz --iterations 500
./bin/peacock test
```

Program arguments go after `--`:

```bash
./bin/peacock run selfhost/tokenizer.pac --grant fs -- examples/tour.pac
```

### A first program

```peacock
module hello

fn main() -> Unit {
    print("Hello from PEACOCK");
}
```

### A model declared in the language

```peacock
module xor_demo

use nn

model XorNet {
    input features: Tensor<Float32, [2]>
    output scores: Tensor<Float32, [2]>
    stack {
        Dense(units: 8, activation: relu)
        Dense(units: 2)
    }
}

training XorTraining {
    objective: "cross_entropy"
    optimiser: "adam"
    epochs: 400
    learning_rate: 0.05
    batch_size: 4
    seed: 7
}

fn main() -> Unit {
    capability compute;
    let data = nn.xor();
    let net = XorNet.init(seed: 7);
    let losses = XorTraining.run(net, data);
    print("epochs: " + str(len(losses)));
    print("final loss: " + str(nn.loss(net, data, loss: "cross_entropy")));
    print("accuracy: " + str(XorTraining.evaluate(net, data)));
}
```

`examples/xor.pac` is the executable source of truth. The host must grant
`compute`; declaring the capability asks the verifier, it does not grant the host
authority.

## Design principles

1. **AI is part of the language.** Tensor types carry dtype and shape; arithmetic
   builds a reverse-mode graph; models and training runs are declarations.
2. **Frontend is a core subsystem.** Colour is a first-class perceptual value; the
   rasteriser is original, deterministic, and documented.
3. **Security is architectural.** Capabilities are declared, statically checked,
   checked again by the VM, and independently granted by the host. Filesystem
   access is confined to a sandbox root and resource budgets are enforced.
4. **Evidence over claims.** Every implemented feature has tests with real
   outputs. Benchmarks are reproducible on the machine recorded in their report.
   Unimplemented features are named as such.
5. **Bootstrap honestly.** Python is the scaffolding, not the product. The lexer,
   parser, type checker, IR, optimiser, bytecode format, VM, tensor engine, and
   renderer are original implementations with no PyTorch/TensorFlow/NumPy/LLVM/
   React/Flutter dependency. Self-hosting is a staged milestone, not a slogan.

## Repository map

```
peacock/compiler/       lexer, parser, AST, types, semantics, IR, optimiser, bytecode
peacock/runtime/        VM, host policy, natives, artifacts, disassembler
peacock/intelligence/   tensors, autodiff, datasets, layers, training, evaluation, .pkm
peacock/frontend/       colour, rasteriser, PNG, easing, spring, timeline, layout, physics
peacock/platforms/      headless, static-web and HTTP frame hosts
peacock/cli.py          run, check, build, disasm, audit, bench, fuzz, test, tokens, ast
selfhost/               PEACOCK-written tokenizer and parser, parity fixtures and tests
examples/               canonical .pac programs (all compile and run in tests, incl. presentation)
tests/                  unittest suite: compiler, ai, frontend, security, integration, unit, benchmarks
linguist/               prepared GitHub Linguist language definition, grammar and samples (not accepted)
editors/vscode/         prepared TextMate grammar package (not published)
assets/                 original PEACOCK logo and icon
benchmarks/             checked-in reference-machine report and fuzz report
docs/                   CLI, bootstrap, bytecode, language, runtime, security and subsystem notes
research/               literature review, open questions, ADRs, benchmark methodology, references
```

## Documentation

Start with the [documentation index](docs/README.md).

- [SPECIFICATION.md](SPECIFICATION.md) — implemented grammar, type rules,
  capabilities, runtime semantics, and diagnostics.
- [ARCHITECTURE.md](ARCHITECTURE.md) — pipeline, VM, memory model, security,
  subsystem boundaries, external dependencies.
- [ROADMAP.md](ROADMAP.md) — phases 0–10, dependencies, acceptance criteria.
- [STATUS.md](STATUS.md) — works / partial / planned / untested, with real test and
  benchmark results.
- [docs/compiler/bootstrap.md](docs/compiler/bootstrap.md) — how the Python
  bootstrap is separated and how PEACOCK becomes self-hosting.
- [docs/cli.md](docs/cli.md) — every command, grant, argument and exit code.
- [docs/platforms/README.md](docs/platforms/README.md) — host matrix and the
  presentation adapters' honest limitations.
- [research/](research/README.md) — literature review, open questions,
  architecture decisions, benchmark methodology, bibliography.
- [linguist/SUBMISSION.md](linguist/SUBMISSION.md) — prepared, **not accepted**,
  GitHub language submission.

## External dependencies and boundaries

The bootstrap uses **only the Python 3.11 standard library**:

- **CPython** executes the bootstrap toolchain and reference VM. It is a temporary
  development host, not part of the language definition.
- **zlib** supplies DEFLATE for PNG. The PNG container, filtering, CRC framing and
  pixel pipeline are implemented here.
- **hashlib** supplies SHA-256 for artifact and model integrity.
- **The OS filesystem** is reached only through `HostPolicy`, which enforces
  capability grants, a sandbox root, symlink resolution and size limits.
- **A browser** is used only as a presentation boundary by `WebBackend`; the
  viewer is static HTML with no JavaScript or framework.

See [ARCHITECTURE.md](ARCHITECTURE.md) § External boundaries and
[SECURITY.md](SECURITY.md) for limitations.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). A feature
is "done" only when its positive tests, negative tests, diagnostics and
documentation exist and the suite passes.

## Licence

MIT. See [LICENSE](LICENSE). Research citations remain the property of their
authors and are recorded in [`research/references.bib`](research/references.bib).
