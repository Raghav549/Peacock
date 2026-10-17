# Contributing to PEACOCK

PEACOCK is an evidence-first project. A feature is not "done" because the code
exists; it is done when the specification, positive tests, negative tests,
diagnostics, documentation and status report agree.

## Before you start

* Read [SPECIFICATION.md](SPECIFICATION.md), [ARCHITECTURE.md](ARCHITECTURE.md)
  and [STATUS.md](STATUS.md).
* Check [ROADMAP.md](ROADMAP.md) for the current phase and prerequisites.
* For anything that changes the language, open a design issue first. Explain the
  syntax, semantics, typing rules, capability impact, failure modes, grammar
  delta and compatibility with existing `.pac` files.

## Development setup

Requirements: Python 3.11+ and a POSIX shell. No third-party packages.

```bash
git clone <repository>
cd Peacock
./bin/peacock test
./bin/peacock check examples/hello.pac
./bin/peacock run examples/aurora.pac --grant fs
```

There is no build step and no network access needed for tests.

## Rules for language changes

1. **Specification first.** Every accepted construct must appear in the formal
   grammar in `SPECIFICATION.md` before or with the implementation. Unspecified
   syntax must be rejected.
2. **Tests are mandatory.** Add:
   * a positive test that compiles and, when meaningful, runs;
   * a negative test for each invalid form;
   * a diagnostic test asserting the code, span behaviour and hint;
   * documentation in the specification and, if a subsystem is affected, its
     `docs/` page.
3. **No silent behaviour.** Undefined behaviour is not acceptable in the
   language core. Choose and document semantics (for example, truncated integer
   division and the sign of `%`).
4. **Capabilities are architectural.** Any new native that touches the host MUST
   declare a capability in `builtins.py`, be enforced in the VM, be listed in the
   audit, and have tests for declared/not-granted/not-declared states.
5. **No unchecked arithmetic.** Integer operations are 64-bit and checked; new
   operations must not silently wrap or overflow.
6. **Keep the bootstrap boundary clean.** Compiler/runtime code may not depend on
   a specific platform API except through `HostPolicy` or `peacock/platforms/`.
   Do not add NumPy, PyTorch, TensorFlow, JAX, LLVM, MLIR, Node or framework
   dependencies to the core.

## Code style

* Python 3.11, type hints on public functions; dataclasses for AST and value
  objects; pure functions where practical.
* The lexer must remain hand-written and must not use regular expressions.
* Avoid monolithic files. New compiler stages go in separate modules with tests.
* Errors use the existing `PeacockError` hierarchy and diagnostic codes. Do not
  invent a code without updating this repository's code map and tests.
* Use deterministic seeds for tests and examples. Tests must not depend on wall
  clock time, network access, user home directories or machine performance.
* Do not commit generated artifacts (`__pycache__`, `.pkb`, `examples/out/`,
  `benchmarks/latest.json`). `benchmarks/reference-machine.json` is checked in as
  evidence and must be regenerated only from the documented command.

## Testing

```bash
./bin/peacock test
python3 -m unittest tests.compiler.test_semantic -v   # focused
./bin/peacock fuzz --iterations 1000 --seed 1
./bin/peacock bench --json benchmarks/latest.json
```

If you change the lexer, parser, artifact loader or model loader, run the fuzzers
with several seeds. If you change performance-sensitive code, do not claim a
speedup without a checked-in command, identical workloads, and the machine
specification.

## Documentation and claims

* Never claim a feature works if its only evidence is an example that has not
  been executed. Quote command output, not intentions.
* Never mark a platform target as working unless it was built and run on that
  platform (or a documented emulator) and the result is reproducible.
* Do not call PEACOCK self-hosting until the compiler compiles itself and the
  fixed-point build passes the suite. A tokenizer written in PEACOCK is a
  self-hosted *component*, not self-hosting.
* Do not claim GitHub Linguist recognition until an upstream PR is merged.
* Benchmark results must name the implementation (bootstrap Python, native, GPU),
  hardware and methodology. Do not compare against other engines without an
  equivalent workload.
* Cite external research ideas in `research/references.bib`. Do not copy code
  from other language implementations; describe and implement the idea
  independently.

## AI-assisted contributions

AI-generated code, tests and documentation are welcome only under the same
standards as human-written work: reviewed, executed, tested, and free of
fabricated results or citations. The contributor is responsible for verifying
licensing and provenance of generated assets. Assets in `assets/` must be
original to this project or carry a documented compatible licence.

## Submitting changes

* Keep commits focused and messages descriptive.
* Update `STATUS.md` and any affected documentation in the same change as the
  code. If a test count or benchmark changes, regenerate it rather than editing
  numbers by hand.
* Include the exact commands you ran and their real output in the pull-request
  description when claiming behaviour.
* For security-sensitive changes, follow [SECURITY.md](SECURITY.md) and avoid
  public disclosure of unfixed vulnerabilities.

## Review checklist

- [ ] Grammar and specification updated together
- [ ] Positive, negative and diagnostic tests
- [ ] Capability and resource-limit impact considered
- [ ] No silent numeric/overflow/bounds behaviour
- [ ] Deterministic tests, no network or third-party dependency
- [ ] README/STATUS/ROADMAP claims match reality
- [ ] Fuzzers run if a parser/loader changed
- [ ] No generated artifacts or credentials committed
