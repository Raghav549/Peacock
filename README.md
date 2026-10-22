# PEACOCK AI

**An AI-native programming language and computing ecosystem, built from first principles.**

PEACOCK is a long-horizon systems and research project. It aims to unify
differentiable computation, model training and inference, an original compiler and
runtime, a perceptual UI/graphics stack, motion and physics, capability-based
security, and multiple deployment hosts behind one coherent language.

**Canonical source extension: `.सूत्र`.** Compiled programs use `.बीज`; models use
`.ज्ञान`. `.pk` and `.peacock` are **not** accepted by the toolchain.

> **Honest status (v0.2.0; phases 0–4 substantially implemented, 5–7 and 9 partial).**
> The lexer, parser, type checker, typed IR, optimiser, bytecode compiler, stack
> VM, tensor/autodiff engine, small-model trainer, colour pipeline, 2D software
> renderer, PNG codec, motion, layout, physics and web/headless/server
> presentation adapters are exercised by **511 passing tests**. A twelve-route
> static website is also authored in PEACOCK and exported by the actual CLI.
> Native mobile shells, native code generation, GPU kernels, a general UI toolkit,
> 3D rendering and AGI research tooling are **not implemented**. The compiler is
> **not self-hosting**; the tokenizer/parser have parity evidence and an
> experimental semantic-shadow kernel is compared with Python on supported
> cases. Python remains authoritative for production semantics, IR and codegen.
> GitHub does **not** yet recognise `.सूत्र`; a Linguist submission is prepared in
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
| Model save/load, int8 quantisation | Working (custom `.ज्ञान` v1) | `tests/ai/test_training.py` |
| Colour science (sRGB/XYZ/Oklab/Oklch/Lab) | Working | `tests/frontend/test_colour.py` |
| Software 2D rasteriser, PNG encode/decode | Working | `tests/frontend/test_canvas_png.py` |
| Easing, springs, timelines, flex layout, 2D physics | Working | `tests/frontend/test_motion.py` |
| Headless, static-web, HTTP frame hosts | Working library adapters | `tests/frontend/test_platforms.py` |
| Frame presentation from `.सूत्र` (`चित्र.प्रदर्शय`, capability `दृश्य`) | Working; static-web backend via `--present` | `examples/present.सूत्र`, `tests/integration/test_presentation.py` |
| PEACOCK-written tokenizer | Working; parity-tested | `selfhost/tokenizer.सूत्र`, `tests/integration/test_cli.py` |
| PEACOCK-written full-grammar parser | Working (syntax); strict errors, no recovery yet | `selfhost/parser.सूत्र`, `tests/integration/test_selfhost_parser.py` |
| Semantic-shadow kernel | Experimental; typed-AST probes, Python remains authoritative | `selfhost/type_model.सूत्र`, `--semantic-shadow` |
| PEACOCK-authored static website | Working export; 12 HTML routes, CSS and SVG, no JS bundle | `website/site.सूत्र`, `tests/integration/test_website.py` |
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
./bin/peacock check examples/hello.सूत्र
./bin/peacock run examples/hello.सूत्र

# Train an XOR network declared in PEACOCK
./bin/peacock run examples/xor.सूत्र --grant गणना

# Differentiable tensors and an analytic gradient check
./bin/peacock run examples/tensors.सूत्र --grant गणना

# Render a procedural aurora to a real PNG
./bin/peacock run examples/aurora.सूत्र --grant सञ्चय
# -> examples/out/aurora.png

# Present animated frames to a host presentation backend
./bin/peacock run examples/present.सूत्र --grant दृश्य --present out/preview
# -> out/preview/latest.png, manifest.json, frames/frame_0000..0003.png

# Serve frames over HTTP while the program runs (then keep the last one)
./bin/peacock run examples/present.सूत्र --grant दृश्य --serve 8099 --linger 30
# -> http://127.0.0.1:8099/  /frame.png  /manifest.json  /healthz

# Export the PEACOCK-authored twelve-route website (static HTML/CSS/SVG)
./bin/peacock run website/site.सूत्र --grant सञ्चय --root . \
  --max-steps 10000000 -- website/dist

# Build and execute a bytecode artifact
./bin/peacock build examples/hello.सूत्र -o /tmp/hello.बीज
./bin/peacock run /tmp/hello.बीज

# Inspect, audit, benchmark, fuzz, test
./bin/peacock disasm examples/xor.सूत्र
./bin/peacock audit examples/xor.सूत्र --json
./bin/peacock bench --json benchmarks/latest.json
./bin/peacock fuzz --iterations 500
./bin/peacock test
```

Program arguments go after `--`:

```bash
./bin/peacock run selfhost/tokenizer.सूत्र --grant सञ्चय -- examples/tour.सूत्र
```

### A first program

```peacock
// The smallest PEACOCK program.
प्रकरण hello

कार्य मुख्य() -> एकक {
    मुद्रय("Hello from PEACOCK");
}
```

### A model declared in the language

```peacock
// Train a small neural network on XOR, entirely through PEACOCK syntax.
प्रकरण xor_net

उपयोग तन्त्रजाल

प्रतिमान XorNet {
    निवेश क्ष: आयाम<दशमलव३२, [२]>
    निर्गम य: आयाम<दशमलव३२, [२]>
    क्रम {
        सघन(एककानि: ८, सक्रियण: धनाङ्क)
        सघन(एककानि: २)
    }
}

अभ्यास XorTraining {
    उद्देश्य: "अन्तरएन्ट्रॉपी"
    अनुकूलक: "आदम"
    आवृत्ति: ४००
    अधिगमदर: ०.०५
    समूहमान: ४
    बीज: ७
}

कार्य मुख्य() -> एकक {
    अधिकार गणना;
    स्थापय दत्त = तन्त्रजाल.असमानयोग();
    स्थापय net = XorNet.प्रारम्भ(बीज: ७);
    स्थापय losses = XorTraining.चलाय(net, दत्त);
    स्थापय शुद्धता = XorTraining.मूल्याङ्कय(net, दत्त);
    मुद्रय("epochs: " + पाठ्यीकरण(दैर्घ्य(losses)));
    मुद्रय("final loss: " + पाठ्यीकरण(तन्त्रजाल.दोष(net, दत्त, दोष: "अन्तरएन्ट्रॉपी")));
    मुद्रय("accuracy: " + पाठ्यीकरण(शुद्धता));
}
```

`examples/xor.सूत्र` is the executable source of truth. The host must grant
`गणना`; declaring the capability asks the verifier, it does not grant the host
authority.

## Design principles

1. **Sanskrit is the source language.** Keywords, declarations, standard-library
   vocabulary, native types, semantic options, and capability names are Sanskrit;
   identifiers and decimal literals accept Unicode, including Devanagari digits.
   English compatibility spellings are rejected rather than creating two dialects.
   Stable internal opcode and artifact IDs are not a second source syntax.
2. **AI is part of the language.** Tensor types carry dtype and shape; arithmetic
   builds a reverse-mode graph; models and training runs are declarations.
3. **Frontend is a core subsystem.** Colour is a first-class perceptual value; the
   rasteriser is original, deterministic, and documented.
4. **Security is architectural.** Capabilities are declared, statically checked,
   checked again by the VM, and independently granted by the host. Filesystem
   access is confined to a sandbox root and resource budgets are enforced.
5. **Evidence over claims.** Every implemented feature has tests with real
   outputs. Benchmarks are reproducible on the machine recorded in their report.
   Unimplemented features are named as such.
6. **Bootstrap honestly.** Python is the scaffolding, not the product. The lexer,
   parser, type checker, IR, optimiser, bytecode format, VM, tensor engine, and
   renderer are original implementations with no PyTorch/TensorFlow/NumPy/LLVM/
   React/Flutter dependency. Self-hosting is a staged milestone, not a slogan.

## Repository map

```
peacock/compiler/       lexer, parser, AST, types, semantics, IR, optimiser, bytecode
peacock/runtime/        VM, host policy, natives, artifacts, disassembler
peacock/intelligence/   tensors, autodiff, datasets, layers, training, evaluation, .ज्ञान
peacock/frontend/       colour, rasteriser, PNG, easing, spring, timeline, layout, physics
peacock/platforms/      headless, static-web and HTTP frame hosts
peacock/cli.py          run, check, build, disasm, audit, bench, fuzz, test, tokens, ast
selfhost/               PEACOCK tokenizer, parser and semantic-shadow kernel with parity fixtures
website/                PEACOCK-authored static website source and build guide
examples/               canonical .सूत्र programs (all compile and run in tests, incl. presentation)
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
- [Sanskrit grammar and literature](docs/language/sanskrit.md) — native lexical
  design, Pāṇinian inspiration, Unicode rules, and research boundaries.
- [ARCHITECTURE.md](ARCHITECTURE.md) — pipeline, VM, memory model, security,
  subsystem boundaries, external dependencies.
- [ROADMAP.md](ROADMAP.md) — phases 0–10, dependencies, acceptance criteria.
- [AUDIT.md](AUDIT.md) — repository-wide evidence-based audit, subsystem status,
  observed commands, history/configuration findings and Linguist eligibility.
- [STATUS.md](STATUS.md) — works / partial / planned / untested, with real test and
  benchmark results.
- [docs/compiler/bootstrap.md](docs/compiler/bootstrap.md) — how the Python
  bootstrap is separated and how PEACOCK becomes self-hosting.
- [docs/cli.md](docs/cli.md) — every command, grant, argument and exit code.
- [docs/platforms/README.md](docs/platforms/README.md) — host matrix and the
  presentation adapters' honest limitations.
- [website/README.md](website/README.md) — PEACOCK-authored site, twelve-route
  static export, build command and verified limits.
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
  `सञ्चय` grants, a sandbox root, symlink resolution and size limits. `सञ्चय.निधिरचना`
  is sandbox-rooted and has the same documented best-effort confinement.
- **A browser** displays standard HTML/CSS/SVG from the PEACOCK-authored static
  website exporter or the script-free `WebBackend` frame viewer. Neither uses a
  JavaScript UI framework; this does not imply a general browser runtime.

See [ARCHITECTURE.md](ARCHITECTURE.md) § External boundaries and
[SECURITY.md](SECURITY.md) for limitations.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). A feature
is "done" only when its positive tests, negative tests, diagnostics and
documentation exist and the suite passes.

## Licence

MIT. See [LICENSE](LICENSE). Research citations remain the property of their
authors and are recorded in [`research/references.bib`](research/references.bib).
