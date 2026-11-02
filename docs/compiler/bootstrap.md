# The Python bootstrap and the path to self-hosting

PEACOCK's long-term implementation must be written in PEACOCK. The current
toolchain is written in Python because a self-hosted compiler cannot exist before
the language and its runtime exist. This document defines the boundary, the
allowed uses of Python, and the staged plan to remove it.

## 1. What "bootstrap" means here

The Python code implements two different things, and they must not be confused:

| Layer | Examples | Long-term owner |
|---|---|---|
| **Language definition and toolchain** | lexer, parser, types, semantics, IR, optimiser, bytecode emitter, disassembler, VM | PEACOCK itself |
| **Host services** | process start, file I/O, time, standard streams, memory allocation, platform window/HTTP | the host platform, behind a small ABI |

Self-hosting means the first layer is written in `.सूत्र` and can compile itself.
It does **not** mean PEACOCK must implement a CPU, kernel or libc. Host services
remain external, as they are for every practical language implementation.

Python is currently used for both layers. Only the second layer is permanently
allowed to depend on a host language.

## 2. Current separation

```
peacock/compiler/      language definition: lexer → parser → types → IR → bytecode
peacock/runtime/       VM + host policy + native library (host ABI)
peacock/intelligence/  tensor engine, autodiff, training (library, called by natives)
peacock/frontend/      colour, rasteriser, PNG, motion (library, called by natives)
peacock/platforms/     presentation hosts (headless/web/server)
selfhost/              PEACOCK programs that reimplement components
```

Rules already enforced by review and tests:

* the compiler has no platform-specific file I/O;
* host access goes through `HostPolicy`/natives, never through compiler code;
* the bytecode format is documented and versioned independently of Python;
* `.सूत्र` examples are compiled by the real pipeline, never translated to Python;
* the language specification does not mention Python types or semantics
  (integer division and remainder are PEACOCK's, not Python's).

## 3. Completed stage: tokenizer

`selfhost/tokenizer.सूत्र` is a PEACOCK tokenizer that:

* is compiled by the actual compiler and executed by the actual VM;
* reads a `.सूत्र` file through the `सञ्चय` capability and arguments through
  `प्रक्रिया.तर्कावली`;
* counts tokens and optionally dumps labels;
* is compared in `tests/integration/test_cli.py` with the bootstrap lexer:
  token count on `examples/tour.सूत्र` is identical (367), and the full non-string
  token label stream on a sample matches.

This is a genuine self-hosted component, not a Python file with a new extension.
It is **not** the compiler and does not establish self-hosting.

## 4. Staged plan

### Stage 1 — Tokenizer (done)

Acceptance: compiles with the real toolchain; parity on count and token classes;
no Python translation layer.

### Stage 2 — Parser and AST (partial)

`selfhost/parser.सूत्र` (1,139 lines, 55 functions) is a recursive-descent parser
written in PEACOCK. It lexes and parses the full 0.4 grammar — प्रकरण/उपयोग/संघटन,
functions, statements including `अन्ते`, expressions, model and training declarations — and prints
a canonical S-expression AST digest.

**Done:**

* byte-identical AST digest with the bootstrap parser on seven core `examples/`,
  all six `linguist/samples/`, `selfhost/fixtures/core_syntax.सूत्र` and
  `selfhost/fixtures/finally.सूत्र`, and on its own source plus
  `selfhost/tokenizer.सूत्र`;
* model, training and layer declarations, including named layer arguments and
  bare symbolic arguments (`activation: relu`);
* strict first-error reporting with `PE4020`, line and column;
* differential tests in `tests/integration/test_selfhost_parser.py`, including
  negative fixtures and a missing-capability test.

**Not done:**

* error recovery and the bootstrap `PE2xxx` diagnostic code/span taxonomy;
* a typed AST. The digest intentionally elides literal values and spans; a real
  self-hosted AST needs sum types/enums or a documented tagged representation;
* user modules/imports beyond the built-in namespaces.

Because 0.4 still lacks sum types, the port currently emits strings. That is sufficient
for syntax parity and self-parsing, but not for the semantic analyser. The
language additions that stage 3 will require are:

* user modules and imports;
* `enum` and `match`, or an explicit tagged-value convention;
* string building efficient enough for diagnostics.

Acceptance for **complete** stage 2: full corpus parity (met) *and* diagnostic
code/span parity on a fixed negative corpus (not met), with no Python translation
layer (met).

### Stage 3 — Semantic analyser and type checker (shadow prototype)

`selfhost/type_model.सूत्र` now implements recursive type relations and selected
expression, lexical-binding, declaration/assignment, user-function signature/
call, condition, return and iterable rules. The opt-in `compile_source(...,
semantic_mode="shadow")` adapter and `--semantic-shadow` CLI flags derive probes
from the Python typed AST, then execute them through the PEACOCK compiler and VM.
Positive/negative programs and the `.सूत्र` example corpus are tested, including
ErrorType iterable recovery. Python semantic analysis and diagnostics remain the
authority; the kernel is not a production replacement and does not yet generate
diagnostics. Field/member resolution, native overloads, model/training analysis,
full diagnostic parity and typed self-hosted AST support remain unported.

The next port is gated on additional differential cases and explicit supported-
domain parity criteria. Porting scopes, capability checking, model/training
validation and definite-return analysis requires a representation expressible in
PEACOCK (structs/enums, lists, maps or parallel arrays).

Acceptance: identical accept/reject decisions and diagnostic codes/messages on
fixed positive/negative corpora for the migrated domain; no change to generated
bytecode for accepted programs; Python stays as a differential oracle until the
parity bar is met.

### Stage 4 — IR, optimiser and bytecode emitter — **done**

`selfhost/ir.सूत्र` (774L, 53 fns, 6376 instrs, 8 checks) builds flat typed PIR
with slots/registers, labels/branches/jumps, const/slot/binop/call/method/make_list/
range/index/field/len/assert/struct/try/catch/finally/model_init/training_method
and verification; IR-digest parity on 16-file corpus (examples + linguist + fixtures +
tokenizer + xor/spiral). `selfhost/bytecode.सूत्र` (635L, 83 fns, 4702 instrs, 8 checks)
emits stack bytecode with label patching and TRY/FINALLY stacks; parity on 9-file core +
3 linguist files. `selfhost/optimizer.सूत्र` (650L, 28 fns, 8516 instrs, 6 checks) is a
5-pass pipeline (const-fold, branch-fold, unreachable, peephole/DCE) with 16-file lenient
IR digest. New attention `is_causal`/`decoder`/`cross_attention` layers are still Python-
authoritative pending IR extension.

Acceptance: byte-for-byte equality of `.बीज` images for the corpus, or a
documented canonicalisation if a representation detail differs — met for the
covered corpus (parser/type_model exceed 256-slot VM limit for the single-`main` shadow wrapper).

### Stage 5 — VM in PEACOCK — **partial**

`selfhost/vm.सूत्र` (845L, 48 fns, 10146 instrs, 9 checks) implements checked
arithmetic, CALL recursion (fact 5=120), FINALLY supersession, MAKE_LIST/LEN/
INDEX/STRUCT_NEW/FIELD_GET, slot/jump/RET/TRY/FINALLY, call-depth and host-grant
budgets. 17-file lenient VM-digest parity (hello/tour/xor/spiral/types/tokenizer
+ fixtures). Host ABI remains `memory.alloc`/`fs.*` via Python natives; Python is
still the process bootstrap.

Acceptance: executes the full integration suite; performance and memory are
measured and reported honestly, including where it is slower than Python —
partial, 10 selfhost kernels + 17 example programs parity, full FINALLY/Cleanup
and native tensor dispatch still Python.

### Stage 6 — Fixed point and retirement

1. Python bootstrap compiles the PEACOCK compiler → stage 1 binary.
2. Stage 1 compiles the compiler source → stage 2 binary.
3. Stage 1 and stage 2 images are identical (or equivalent under documented
   canonicalisation).
4. The PEACOCK-built compiler runs the full test suite.
5. Only then is Python removed from the build path.

The Python implementation remains in the repository as a reference and
differential-testing oracle until the fixed point has been stable for a release.

## 5. What stays in the host

Even after self-hosting, these remain host responsibilities and are exposed
through capabilities:

* file I/O and sandbox enforcement;
* process arguments, standard streams and exit status;
* time and randomness sources (future capability);
* platform windows, input and HTTP serving;
* hardware acceleration (CPU/GPU kernels), if implemented outside PEACOCK.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Language too small to express its compiler | Add enums/match/modules with specs and tests *before* porting |
| Two implementations diverge | Differential tests on corpus, byte-identical images, CI |
| Self-hosted compiler too slow | Measure; allow bootstrap compilation and optimisations |
| Python semantics leak into PEACOCK | Spec asserts PEACOCK semantics; tests pin division, overflow, strings |
| Self-hosting becomes a slogan | STATUS tracks stages; no claim before fixed point |

## 7. Non-goals

* Removing Python before the fixed point is proven.
* Implementing an OS, kernel or libc in PEACOCK.
* Claiming "self-hosting" because one component is written in `.सूत्र`.
* Copying another compiler's architecture or code; borrowed ideas are cited in
  `research/references.bib`.
