# Self-hosted PEACOCK components

This directory contains programs written in PEACOCK that reimplement parts of the
PEACOCK toolchain. They are compiled and executed by the real compiler and VM.
They are **not** a second toolchain and they do **not** make PEACOCK
self-hosting.

## Components

| Program | Lines | What it does | Evidence |
|---|---:|---|---|
| `tokenizer.pac` | 235 | lexes a `.pac` file into labelled tokens (keywords, identifiers, numbers, strings, operators, comments) | token count and non-string token-label parity with the bootstrap lexer on `examples/tour.pac` (367 tokens) |
| `parser.pac` | 1,085 | lexes and parses the full 0.1 grammar — module/use/struct/fn, statements, expressions, model and training declarations — and prints a canonical AST digest | byte-identical digest with the bootstrap AST on the 14-file core corpus, plus parsing its own source and `tokenizer.pac` |
| `type_model.pac` | — | executable PEACOCK kernel for recursive type relations, unary/binary/list/index inference, lexical bindings, declaration/assignment, user-function signatures/calls, conditions, returns and iterable rules | VM-run assertions plus opt-in typed-AST shadow probes against Python; experimental, incomplete and not a production semantic analyser |
| `fixtures/core_syntax.pac` | 57 | covers else-if, nested blocks, indexing, power associativity, `not/and/or`, `%`, ranges, break/continue, `assert` and generics | included in the parity corpus and executable |
| `fixtures/invalid/*.pac` | — | malformed programs for the negative suite | assert a non-zero exit, a `PE4020` diagnostic, line/column and no stdout AST |

## Running the parser

The parser needs the `fs` capability and a program argument:

```bash
./bin/peacock run selfhost/parser.pac \
  --grant fs --root . --max-steps 100000000 \
  -- examples/tour.pac
```

`--max-steps` is raised because the parser runs on the Python reference VM and
self-parsing (1,085 lines) takes about 5.5 s and tens of millions of VM steps.
The default 2,000,000-step budget is intentionally too small.

The output is one S-expression per declaration in the format implemented by
`tests/integration/ast_digest.py`; the bootstrap AST is the oracle:

```
(module hello)
(fn main (params) (ret (t Unit)) (block (expr (call (name print) (arg _ (str))))))
```

## Parity corpus

`tests/integration/test_selfhost_parser.py` compares the two parsers on:

* all seven `examples/` programs, including `xor.pac` and `spiral.pac` with model
  and training declarations;
* the six `linguist/samples/` programs;
* `selfhost/fixtures/core_syntax.pac`;
* `selfhost/tokenizer.pac` and `selfhost/parser.pac` (self-parse).

Run it directly:

```bash
python3 -m unittest tests.integration.test_selfhost_parser -v
```

## Honest scope

* **Syntax, not semantics.** The parser builds a structural digest for
  differential testing. It does not build a typed AST, resolve names, check
  capabilities or emit IR.
* **Strict errors, different diagnostics.** It stops at the first error and
  reports `PE4020` with line/column. The bootstrap parser recovers and uses the
  `PE2xxx` code taxonomy; diagnostic-code and span parity is future work.
* **No typed AST representation.** Names, literals and operators are preserved,
  but literal values are elided in the digest and source spans are not attached
  to nodes. A real self-hosted AST will need enum/sum types (stage 3).
* **Not self-hosting.** The semantic analyser, IR, optimiser, bytecode emitter
  and VM are still Python. The bootstrap compiler is still required.

## Stage status

| Stage | Status |
|---|---|
| 1. lexer/tokenizer | done (`tokenizer.pac`, plus the lexer inside `parser.pac`) |
| 2. parser and AST | **partial** — full-grammar syntax parity and self-parse; diagnostics/recovery and typed AST pending |
| 3. semantic analyser/type checker | **shadow prototype** (`type_model.pac` executes supported typed-AST expression/scope/name/assignment/call/return/condition/iterable probes; Python remains authoritative and kernel-generated diagnostics are not implemented) |
| 4. IR/optimiser/bytecode emitter | planned |
| 5. VM in PEACOCK | planned |
| 6. fixed point | planned |

See [../docs/compiler/bootstrap.md](../docs/compiler/bootstrap.md) and
[../research/architecture-decisions.md](../research/architecture-decisions.md)
(ADR-0001).
