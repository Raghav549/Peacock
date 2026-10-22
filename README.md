# PEACOCK AI

**An AI-native programming language and computing ecosystem, built from first principles.**

PEACOCK is a long-horizon systems and research project. It aims to unify
differentiable computation, model training and inference, an original compiler and
runtime, a perceptual UI/graphics stack, motion and physics, capability-based
security, and multiple deployment hosts behind one coherent language.

**Canonical source extension: `.सूत्र`.** Compiled programs use `.बीज`; models use
`.ज्ञान`. `.pk` and `.peacock` are **not** accepted by the toolchain.

> **Honest status (v0.4.0; substantial working subsets, not a finished ecosystem).**
> The compiler/VM now includes `अन्ते` finalization; native C AOT and an
> embeddable ABI, bounded LLM/tool agents, CPU/OpenCL compute operations,
> interactive browser/X11 UI hosts, PEACOCK-controlled HTTP servers, and native
> desktop/Android/iOS shell sources join the existing AI, colour, 2D/3D and
> grammar engines. The Linux native library/desktop paths and real HTTP/event
> tests execute successfully; Android/iOS and actual OpenCL/X11 hardware remain
> unverified in this environment. Native AOT covers only its documented opcode
> subset. The grammar package contains all **3,983 sūtra texts**, generic
> pratyāhāra expansion and four explicitly traced sandhi rules—not a complete
> executable Aṣṭādhyāyī. Agents are bounded, not AGI. The compiler is **not
> self-hosting**; Python remains authoritative for production semantics, IR and
> codegen. GitHub does **not** yet recognise `.सूत्र`; a Linguist submission is
> prepared in [`linguist/`](linguist/), not accepted. See [STATUS.md](STATUS.md)
> for the current verified test count and evidence.

## What works today

| Area | Status | Evidence |
|---|---|---|
| Lexer, parser, recovery diagnostics | Working | `tests/compiler/test_lexer.py`, `test_parser.py` |
| Static types, scopes, capability checking | Working subset | `tests/compiler/test_types.py`, `test_semantic.py` |
| Typed IR, verifier, optimiser, bytecode | Working | `tests/compiler/test_ir.py`, `test_pipeline.py` |
| Stack VM, checked arithmetic, try/catch/`अन्ते` | Working; nested completion unwinding | `tests/compiler/test_vm.py`, `tests/integration/test_finally.py` |
| Capability sandbox and budgets | Working (best effort) | `tests/security/test_capabilities.py` |
| Tensor engine, broadcasting, autodiff | Working (CPU, pure Python) | `tests/ai/test_tensor.py` |
| Dense models, training, evaluation | Working (small models) | `tests/ai/test_training.py` |
| Model save/load, int8 quantisation | Working (custom `.ज्ञान` v1) | `tests/ai/test_training.py` |
| Colour science (sRGB/XYZ/Oklab/Oklch/Lab) | Working | `tests/frontend/test_colour.py` |
| CIEDE2000, weighted/pigment mixing, gamut mapping | Working | `tests/frontend/test_colour_advanced.py`, `examples/colour_lab.सूत्र` |
| Bounded rule agents, Dijkstra plans, traces | Working deterministic planner | `tests/ai/test_agent.py`, `examples/agents.सूत्र` |
| Bounded LLM/tool agents | Working host/provider loop; not AGI | `tests/ai/test_llm_agent.py`, `examples/autonomous_agent.सूत्र` |
| CPU/OpenCL tensor operations | CPU tested; OpenCL hardware test environment-dependent | `tests/ai/test_gpu.py`, `examples/gpu.सूत्र` |
| Sūtra corpus, pratyāhāra, traced vowel sandhi | Working; 3,983 texts, 4 sandhi rules | `tests/unit/test_vyakarana.py`, `examples/vyakarana.सूत्र` |
| Retained Sanskrit UI, layout, events, audits, HTML | Working; browser and X11 hosts | `tests/frontend/test_ui.py`, `tests/integration/test_native_window.py` |
| CPU 3D meshes, perspective, depth and lights | Working | `tests/frontend/test_scene3d.py`, `examples/scene3d.सूत्र` |
| Software 2D rasteriser, PNG encode/decode | Working | `tests/frontend/test_canvas_png.py` |
| Easing, springs, timelines, flex layout, 2D physics | Working | `tests/frontend/test_motion.py` |
| Headless, static-web, HTTP frame hosts | Working library adapters | `tests/frontend/test_platforms.py` |
| Frame presentation from `.सूत्र` (`चित्र.प्रदर्शय`, capability `दृश्य`) | Working; static-web backend via `--present` | `examples/present.सूत्र`, `tests/integration/test_presentation.py` |
| PEACOCK-owned synchronous HTTP server | Working bounded UTF-8 request/response subset | `tests/integration/test_server_language.py`, `examples/http_server.सूत्र` |
| Native C executable/shared-library AOT | Working verified subset; real C builds and ABI tests | `peacock/native/`, `tests/integration/test_native_aot.py` |
| Native desktop shell | Executed on Linux x86-64; VM-identical output | `shells/desktop/`, `docs/platforms/README.md` |
| Android/iOS shells | Source/generated-C only here; SDK/Xcode execution pending | `shells/android/`, `shells/ios/` |
| PEACOCK-written tokenizer | Working; parity-tested | `selfhost/tokenizer.सूत्र`, `tests/integration/test_cli.py` |
| PEACOCK-written full-grammar parser | Working (syntax); strict errors, no recovery yet | `selfhost/parser.सूत्र`, `tests/integration/test_selfhost_parser.py` |
| Semantic-shadow kernel | Experimental; typed-AST probes, Python remains authoritative | `selfhost/type_model.सूत्र`, `--semantic-shadow` |
| PEACOCK-authored static website | Working export; 12 HTML routes, CSS and SVG, no JS bundle | `website/site.सूत्र`, `tests/integration/test_website.py` |
| Complete executable Pāṇini and AGI | **Not implemented** | Grammar/agent manuals and roadmap |
| Whole-language AOT, GPU training, mobile hardware validation | **Not implemented/verified** | `docs/native.md`, `docs/platforms/README.md` |
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

# Grammar corpus/pratyāhāra/sandhi, bounded agents and advanced colour
./bin/peacock run examples/vyakarana.सूत्र
./bin/peacock व्याकरण संधि राम इन्द्रः
./bin/peacock run examples/agents.सूत्र --grant गणना
./bin/peacock run examples/colour_lab.सूत्र

# Export a Sanskrit UI document and a lit, depth-buffered 3-D scene
./bin/peacock run examples/ui_builder.सूत्र --grant सञ्चय --root .
./bin/peacock run examples/scene3d.सूत्र --grant सञ्चय --root .

# Interactive UI events through a browser or native X11 window
./bin/peacock run examples/ui_events.सूत्र --grant दृश्य --ui-serve 8080
# ./bin/peacock run examples/ui_events.सूत्र --grant दृश्य --window

# CPU/OpenCL operation selection (explicit त्वरक requires actual hardware)
./bin/peacock run examples/gpu.सूत्र --grant गणना

# Build a standalone native executable from the supported AOT subset
./bin/peacock native examples/native.सूत्र -o /tmp/peacock-native
/tmp/peacock-native

# Run a PEACOCK-owned one-request HTTP server (POST to the printed port)
./bin/peacock run examples/http_server.सूत्र --grant सञ्जाल

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
   builds a reverse-mode graph; models and training runs are declarations;
   bounded agents expose explicit rules, costs, plans and traces.
3. **Frontend is a core subsystem.** Colour is a first-class perceptual value;
   retained UI, 2-D and CPU 3-D renderers are original, deterministic and
   documented, with native-host/GPU boundaries stated explicitly.
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
peacock/intelligence/   tensors, autodiff, training, agents, CPU/OpenCL operations, .ज्ञान
peacock/frontend/       advanced colour, 2D/CPU-3D, retained UI/events, PNG, motion, physics
peacock/vyakarana/      attributed sūtra corpus, pratyāhāra, sandhi, literature catalogue
peacock/platforms/      headless/web/interactive/X11 hosts and bounded HTTP server
peacock/native/         verified-subset C generation, runtime and executable/library builder
peacock/cli.py          compiler/VM/native tools, व्याकरण, bench, fuzz and test commands
shells/                 native desktop, Android and iOS host sources/build scripts
selfhost/               PEACOCK tokenizer, parser and semantic-shadow kernel with parity fixtures
website/                PEACOCK-authored static website source and build guide
examples/               canonical .सूत्र programs, including grammar/agents/UI/3-D demonstrations
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
- Native manuals: [व्याकरण](docs/language/vyakarana.md),
  [agents](docs/ai-engine/agents.md), [UI/events](docs/frontend/ui-builder.md),
  [CPU/OpenCL](docs/ai-engine/tensors.md), [native AOT](docs/native.md),
  [3-D](docs/frontend/scene3d.md), and [advanced colour](docs/frontend/colour.md).
- [CPython capability audit](docs/CPYTHON_AUDIT.md) — pinned upstream inspection,
  the resulting `अन्ते` implementation and explicit remaining gaps.
- [ARCHITECTURE.md](ARCHITECTURE.md) — pipeline, VM, memory model, security,
  subsystem boundaries, external dependencies.
- [ROADMAP.md](ROADMAP.md) — phases 0–11, dependencies, acceptance criteria.
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
- **A browser** displays standard HTML/CSS/SVG from the static website exporter
  or `WebBackend`. The explicit `UIWebBackend` adds small same-origin event and
  fragment-refresh scripts, with no JavaScript framework or general browser VM.
- **A host C11 compiler** builds the optional native AOT executable/library. The
  resulting desktop program does not require Python; the compiler still does.
- **X11** is dynamically loaded only for `--window`; **OpenCL** is dynamically
  loaded only for accelerator discovery/execution. Absence is an explicit or
  reported fallback condition, not successful hardware validation.
- **OS sockets** serve bounded frame/UI/PEACOCK HTTP hosts. An LLM provider is
  contacted only when explicitly configured and invoked; remote provider HTTP is
  rejected in favour of HTTPS and redirects are not followed.

See [ARCHITECTURE.md](ARCHITECTURE.md) § External boundaries and
[SECURITY.md](SECURITY.md) for limitations.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). A feature
is "done" only when its positive tests, negative tests, diagnostics and
documentation exist and the suite passes.

## Licence

MIT. See [LICENSE](LICENSE). Research citations remain the property of their
authors and are recorded in [`research/references.bib`](research/references.bib).
