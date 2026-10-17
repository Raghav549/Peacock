# PIR and the PEACOCK bytecode

This page documents the compiler's intermediate representation and the stack
machine image. It is a guide for implementers; the specification defines language
semantics.

## PIR

PIR is a linear, typed list of instructions per function with:

* `dest` — a temporary register (integer) or `None`;
* `op` — a mnemonic;
* `args` — a tuple of operands;
* `dest_type` — the static type of the destination, used by the verifier.

Locals and parameters live in numbered **slots** assigned by the semantic
analyser. Temporaries are numbered separately per function and live only between
instructions.

Optimisation passes:

1. constant folding of literal arithmetic and comparisons;
2. constant branch folding (`if true/false`);
3. unreachable code elimination (keeping try-scope markers balanced);
4. dead temporary elimination when a temporary has no uses and no effects;
5. peephole (e.g. `not not`, identity arithmetic where safe).

The verifier runs before and after optimisation and checks register range,
labels, terminators and binop operand types.

## Bytecode image

```json
{
  "format": "peacock-bytecode",
  "format_version": 1,
  "language_version": "0.1",
  "compiler_version": "0.1.0",
  "module": "hello",
  "uses": ["nn"],
  "source_path": "examples/hello.pac",
  "source_sha256": "…",
  "functions": {
    "main": {
      "arity": 0,
      "slots": 0,
      "caps": [],
      "return_type": "Unit",
      "params": [],
      "code": [["PUSH_CONST", "Hello from PEACOCK"], ["CALL_NATIVE", "print", 1], ["RET", 0]],
      "lines": [[6, 5], [6, 5], [6, 5]]
    }
  },
  "structs": {},
  "models": {},
  "trainings": {}
}
```

Images are canonical JSON (sorted keys, compact separators) inside a `.pkb`
container with a SHA-256 digest. The VM verifies the image again on load.

## Instruction set

| Opcode | Operands | Stack effect |
|---|---|---|
| `PUSH_CONST` | value | push |
| `PUSH_SLOT` | slot | push (fault if uninitialised) |
| `STORE_SLOT` | slot | pop |
| `POP` | — | pop |
| `BINOP` | operator | pop 2, push 1 |
| `UNOP` | operator | pop 1, push 1 |
| `CALL` | function, argc | pop args, push result |
| `CALL_NATIVE` | name, argc | pop args, push result |
| `METHOD` | receiver type, name, argc | pop receiver+args, push result |
| `MODEL_INIT` | model, seed-count | pop seed, push Model |
| `TRAINING_METHOD` | training, method, argc | pop args, push result |
| `STRUCT_NEW` | type, field order | pop fields, push struct |
| `FIELD_GET` | field, kind | pop base, push value |
| `FIELD_SET` | field, kind | pop base+value |
| `INDEX_GET` | — | pop base+index, push value |
| `INDEX_SET` | — | pop base+index+value |
| `MAKE_LIST` | count | pop n, push list |
| `MAKE_RANGE` | — | pop end+start, push range |
| `LEN` | — | pop value, push Int |
| `ASSERT` | has message | pop message?, condition |
| `THROW` | — | pop message, unwind |
| `JUMP` | target | — |
| `JUMP_IF_FALSE` | target | pop condition |
| `RET` | has value | pop optional value, return |
| `TRY_BEGIN` | catch target, end | push handler record |
| `TRY_END` | — | pop handler record |
| `CATCH` | — | push pending error message |
| `NOP` | — | — |

## Frame layout and exceptions

A frame owns a fixed slot array and an operand stack. `TRY_BEGIN` records the
current stack depth and the catch/end positions. Raising unwinds to the innermost
handler whose range contains the faulting instruction, truncates the stack to the
recorded depth, sets `pending_error`, and jumps to the handler. A `throw` inside a
catch replaces the pending error and unwinds outward. `PanicError` and
`ResourceLimitError` bypass handlers.

## Verification

`verify_image` is intentionally independent of the emitter. It checks:

* format and version fields;
* every opcode is known and operands have the expected types/arity;
* slot indices are within `slots`;
* jump and catch targets are in range and point at instruction boundaries;
* `CALL`/`CALL_NATIVE`/`METHOD`/`TRAINING_METHOD` names and arities;
* capability names are known;
* struct field order and model/training references;
* `main` exists as a zero-arity function for execution.

Failing verification raises `BytecodeError`; the VM wraps it as an artifact
format error before executing anything.

## Limits and non-goals

The bytecode is not a register machine, has no GC metadata, no debug sections
beyond line/column pairs, no linking, no separate compilation and no dynamic
dispatch. These are deliberate 0.1 constraints; changing them requires a version
bump and an ADR.
