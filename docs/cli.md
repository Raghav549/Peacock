# CLI reference

Entry point: `./bin/peacock` (POSIX) or `bin/peacock.cmd` (Windows). The Python
bootstrap requires 3.11+ and no packages.

```
peacock <command> [options]
```

| Command | Purpose |
|---|---|
| `version` | versions, extension, implementation status |
| `check <file.सूत्र>` | full pipeline; `--json`, `--no-opt`, `--quiet`, experimental `--semantic-shadow` |
| `run <file.सूत्र\|file.बीज>` | compile if needed, execute; grants/root/budgets, frame/UI hosts and optional host-configured LLM provider |
| `build <file.सूत्र> [-o file.बीज]` | verified image + SHA-256; optional experimental `--semantic-shadow` |
| `native <file.सूत्र> -o BIN` | compile the documented AOT subset to an executable or `--library` shared library; `--cc`, `--keep-c`, `--max-steps`, `--no-opt` |
| `disasm <file>` | human-readable instructions, models, training declarations |
| `audit <file.सूत्र>` | static capability report; `--json` |
| `tokens <file.सूत्र>` | token dump (debug) |
| `ast <file.सूत्र>` | AST dump (debug) |
| `व्याकरण <operation>` | offline sūtra lookup/search, pratyāhāra, sandhi, literature and coverage |
| `bench` | reproducible benchmark suite; `--json PATH`, `--quick` |
| `fuzz` | deterministic fuzzers; `--iterations`, `--seed`, `--json` |
| `test` | run the unittest suite; `-p PATTERN`, `--quiet` |

## Sanskrit grammar operations

```bash
./bin/peacock व्याकरण सूत्र 1.1.1
./bin/peacock व्याकरण अन्वेषय गुण --अवधि 5
./bin/peacock व्याकरण प्रत्याहार अच्
./bin/peacock व्याकरण संधि राम इन्द्रः
./bin/peacock व्याकरण साहित्य
./bin/peacock व्याकरण आच्छादन
```

These operations use the installed offline corpus and need no capability grant.
Unknown sūtras, invalid pratyāhāras and unsupported sandhi boundaries produce a
controlled error, not a guessed form. Coverage reports 3,983 sūtra texts and the
separate executable-rule count; see [language/vyakarana.md](language/vyakarana.md).

## Semantic shadow checks (experimental)

`check --semantic-shadow` keeps the Python analyser authoritative and then runs
AST-derived checks through `selfhost/type_model.सूत्र` in the PEACOCK VM. It
covers the currently migrated type relations, expression result rules, local
scope/name probes, declarations/assignments, user-function signatures/calls,
conditions and returns. The JSON stats include `selfhost_type_cases`,
`selfhost_semantic_cases`, `selfhost_builtin_cases` and shadow time. A disagreement
is an internal compiler error; the flag does not change ordinary compilation
acceptance or diagnostics. `build` also accepts the flag to require the same
shadow pass before emitting `.बीज`.

This remains experimental: field/method semantics, native overloads,
model/training checks, diagnostics, IR, bytecode and VM are not migrated.

## Grants and sandbox

Nothing is granted by default.

```bash
./bin/peacock run app.सूत्र --grant सञ्चय
./bin/peacock run app.सूत्र --grant गणना --root ./sandbox
./bin/peacock run app.सूत्र --grant सञ्चय,गणना
./bin/peacock run app.सूत्र --grant दृश्य --present out/preview
```

`--root` defaults to the current directory. Paths in a program are resolved under
that root; escapes are rejected. The program itself must also declare the
capability in the function that uses it.

`--present DIR` attaches the static-web presentation backend: every
`चित्र.प्रदर्शय(चित्रपट्ट)` writes `frames/frame_NNNN.png`, updates `latest.png`
and `index.html`, and the run ends with `manifest.json`. The backend is a host
object; the VM only sees a native call. `दृश्य` grants presentation, not input.

```bash
./bin/peacock run examples/present.सूत्र --grant दृश्य --present out/preview
# stdout: presented 4 frames
# out/preview/manifest.json lists four 320x180 frames
```

`--serve PORT` attaches the HTTP host instead of writing files. The server is
available while the program runs; `--linger SECONDS` keeps the last frame
available afterwards (`-1` serves until interrupted). `--serve-host` defaults to
`127.0.0.1`; use `0.0.0.0` only for a deliberate container preview.

```bash
./bin/peacock run examples/present.सूत्र --grant दृश्य --serve 8099 --linger 30
# stderr: serving at http://127.0.0.1:8099/
# routes: /  /frame.png  /manifest.json  /healthz
```

`--present`, `--serve`, `--ui-serve` and `--window` are mutually exclusive
(exit 2). A port that cannot be bound is a host error. The HTTP hosts have no
authentication or TLS.

### Interactive UI and native window

`--ui-serve PORT` lazily attaches the interactive retained-UI host on the first
`दृश्य.प्रदर्शय`; `--serve-host` controls its bind address and `--linger` also
applies after completion. `--window` instead attaches the native X11 host and
requires a working `DISPLAY`. Both deliver events to `दृश्य.अग्रघटना`.

```bash
./bin/peacock run examples/ui_events.सूत्र --grant दृश्य --ui-serve 8080
./bin/peacock run examples/ui_events.सूत्र --grant दृश्य --window
```

### Host-configured LLM agent

`अभिकर्तृ.स्वायत्त` needs both source/host `सञ्जाल` authority and a provider
configured with `--llm-url URL --llm-model NAME`. The URL is an
OpenAI-compatible `/v1` base; remote HTTP is rejected in favour of HTTPS.
`--llm-key-env VAR` optionally reads the bearer key from that environment
variable. The key is not accepted as a source argument or included in traces.

```bash
./bin/peacock run examples/autonomous_agent.सूत्र --grant सञ्जाल \
  --llm-url http://127.0.0.1:8000/v1 --llm-model local-model
```

No provider is contacted unless the program actually invokes the agent. See
[the agent manual](ai-engine/agents.md) and [native AOT](native.md).

## Arguments

Arguments after `--` are passed to `प्रक्रिया.तर्कावली()`:

```bash
./bin/peacock run selfhost/tokenizer.सूत्र --grant सञ्चय -- examples/tour.सूत्र --dump
```

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | success |
| 1 | compilation/grammar operation diagnostics or failing tests |
| 2 | usage error (bad extension, unknown grant/command) |
| 3 | runtime fault, capability denial, invalid artifact |
| 4 | internal compiler error (bug) |
| 5 | fuzzing found a crash |
| 130 | interrupted |

## Machine-readable output

`check --json`, `run --json`, `audit --json` and `bench --json` print stable JSON.
`run --report FILE` writes the last `TrainingReport` plus environment metadata.
For tooling compatibility, audit JSON retains stable internal capability/native IDs;
the human-readable audit and disassembly render their Sanskrit source spellings.

## Notes

* `.बीज` programs run without source; the image is re-verified.
* `check` on a `.pk`/`.peacock` file fails with a usage error: rename to `.सूत्र`.
* The CLI never downloads dependencies or compiler inputs. Network access occurs
  only for explicit server natives or an explicitly configured LLM provider.
  Credentials are read only from the variable named by `--llm-key-env`; do not
  put keys in source, command arguments or committed files.
