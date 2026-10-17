# CLI reference

Entry point: `./bin/peacock` (POSIX) or `bin/peacock.cmd` (Windows). The Python
bootstrap requires 3.11+ and no packages.

```
peacock <command> [options]
```

| Command | Purpose |
|---|---|
| `version` | versions, extension, implementation status |
| `check <file.pac>` | full pipeline; `--json`, `--no-opt`, `--quiet` |
| `run <file.pac\|file.pkb>` | compile if needed, execute; `--grant`, `--root`, `--json`, `--report`, `--max-steps`, `--present DIR`, `--serve PORT` |
| `build <file.pac> [-o file.pkb]` | verified image + SHA-256 |
| `disasm <file>` | human-readable instructions, models, training declarations |
| `audit <file.pac>` | static capability report; `--json` |
| `tokens <file.pac>` | token dump (debug) |
| `ast <file.pac>` | AST dump (debug) |
| `bench` | reproducible benchmark suite; `--json PATH`, `--quick` |
| `fuzz` | deterministic fuzzers; `--iterations`, `--seed`, `--json` |
| `test` | run the unittest suite; `-p PATTERN`, `--quiet` |

## Grants and sandbox

Nothing is granted by default.

```bash
./bin/peacock run app.pac --grant fs
./bin/peacock run app.pac --grant compute --root ./sandbox
./bin/peacock run app.pac --grant fs,compute
./bin/peacock run app.pac --grant ui --present out/preview
```

`--root` defaults to the current directory. Paths in a program are resolved under
that root; escapes are rejected. The program itself must also declare the
capability in the function that uses it.

`--present DIR` attaches the static-web presentation backend: every
`graphics.present(canvas)` writes `frames/frame_NNNN.png`, updates `latest.png`
and `index.html`, and the run ends with `manifest.json`. The backend is a host
object; the VM only sees a native call. `ui` grants presentation, not input.

```bash
./bin/peacock run examples/present.pac --grant ui --present out/preview
# stdout: presented 4 frames
# out/preview/manifest.json lists four 320x180 frames
```

`--serve PORT` attaches the HTTP host instead of writing files. The server is
available while the program runs; `--linger SECONDS` keeps the last frame
available afterwards (`-1` serves until interrupted). `--serve-host` defaults to
`127.0.0.1`; use `0.0.0.0` only for a deliberate container preview.

```bash
./bin/peacock run examples/present.pac --grant ui --serve 8099 --linger 30
# stderr: serving at http://127.0.0.1:8099/
# routes: /  /frame.png  /manifest.json  /healthz
```

`--present` and `--serve` are mutually exclusive (exit 2). A port that cannot be
bound is a usage error. The HTTP host has no authentication or TLS.

## Arguments

Arguments after `--` are passed to `process.args()`:

```bash
./bin/peacock run selfhost/tokenizer.pac --grant fs -- examples/tour.pac --dump
```

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | success |
| 1 | compilation diagnostics or failing tests |
| 2 | usage error (bad extension, unknown grant/command) |
| 3 | runtime fault, capability denial, invalid artifact |
| 4 | internal compiler error (bug) |
| 5 | fuzzing found a crash |
| 130 | interrupted |

## Machine-readable output

`check --json`, `run --json`, `audit --json` and `bench --json` print stable JSON.
`run --report FILE` writes the last `TrainingReport` plus environment metadata.

## Notes

* `.pkb` programs run without source; the image is re-verified.
* `check` on a `.pk`/`.peacock` file fails with a usage error: rename to `.pac`.
* The CLI never downloads anything and never reads credentials.
