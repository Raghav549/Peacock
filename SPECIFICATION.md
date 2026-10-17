# PEACOCK Language Specification — version 0.1

Status: **implemented subset**. This document describes what the v0.1 toolchain
actually accepts and executes. It is not a description of every feature PEACOCK
will eventually have. Anything not specified here is either rejected by the
compiler or reserved for a later version.

Canonical source extension: `.pac`. Source files must be UTF-8 and should end
with a newline; the lexer accepts both LF and CRLF endings.

Normative keywords use `MUST`, `MUST NOT`, `SHOULD`. When this document and the
implementation disagree, that is a bug; the tests and this document are updated
together.

---

## 1. Program structure

A program is a sequence of top-level declarations:

```
program        = [ module-decl ] { use-decl | function | struct | model | training } EOF
module-decl    = "module" IDENT
use-decl       = "use" IDENT [ ";" ]
```

* `module` is optional but, if present, MUST be the first item.
* A module name does not create a namespace for values; v0.1 has one flat
  value namespace per program.
* `use` imports a standard-library namespace: `math`, `nn`, `colour`,
  `graphics`, `motion`, `fs`, `text`, or `process`. Aliases (`use nn as n`) are
  rejected (PE2005). A namespace MUST be imported before its members are used.
* There are no user-defined file imports in 0.1. The whole program is one file.
* Declarations are order-independent: a function may call one declared later.
* Names are ASCII identifiers beginning with `_` or a letter. Reserved words may
  not be identifiers.

Reserved for future versions and rejected with a targeted diagnostic (PE2001):
`async await const enum impl import match pub spawn yield`.

---

## 2. Lexical structure

### 2.1 Whitespace and comments

Whitespace separates tokens. Comments are `// line` and nestable
`/* block */` comments. An unterminated block comment is PE1001.

### 2.2 Literals

| Literal | Form | Notes |
|---|---|---|
| Integer | `0`, `42`, `1_000`, `0xFF`, `0b1010`, `0o17` | 64-bit signed range. Underscores separate digits and may not be leading, trailing or doubled. |
| Float | `1.5`, `1e3`, `2.5e-2`, `1_000.5` | binary64. |
| Boolean | `true`, `false` | |
| String | `"text"` | must not span a physical line. |
| List | `[1, 2, 3]`, `[]` | empty lists need a type annotation. |

String escapes: `\n`, `\t`, `\r`, `\\`, `\"`, `\'`, `\0`, and `\u{HEX}` for a
Unicode code point. Unknown escapes are PE1025. Strings are indexed and
measured in Unicode code points, not bytes, and are immutable.

### 2.3 Operators and punctuation

```
**   *   /   %   +   -   <   >   <=   >=   ==   !=
=    +=  -=  *=  /=  %=  ->  ..   .   ,   :   ;   ?
( )  { }  [ ]
```

`!`, `&`, `|`, `^`, `~` and `<<`/`>>` are **not** PEACOCK operators; they
produce PE1003/PE1004 with an explanation. Logical negation is the keyword
`not`, conjunction `and`, disjunction `or`.

---

## 3. Grammar (EBNF)

The following is the complete v0.1 grammar. `[ x ]` is optional, `{ x }` is
repetition, and alternatives are separated by `|`.

```
program        = [ module-decl ] { item } EOF
module-decl    = "module" IDENT
item           = use-decl | function | struct | model | training

use-decl       = "use" IDENT [ ";" ]

function       = "fn" IDENT "(" [ params ] ")" [ "->" type ] block
params         = param { "," param }
param          = IDENT ":" type
block          = "{" { statement } "}"

struct         = "struct" IDENT "{" { field } "}"
field          = IDENT ":" type [ "," | ";" ]

model          = "model" IDENT "{" model-section { model-section } "}"
model-section  = input-section | output-section | stack-section
input-section  = "input" IDENT ":" type
output-section = "output" IDENT ":" type
stack-section  = "stack" "{" { layer } "}"
layer          = IDENT "(" [ layer-args ] ")"
layer-args     = layer-arg { "," layer-arg }
layer-arg      = IDENT ":" ( INT | IDENT | STRING )

training       = "training" IDENT "{" { training-field } "}"
training-field = IDENT ":" literal [ "," | ";" ]

statement      = let-stmt | if-stmt | while-stmt | for-stmt
               | return-stmt | break-stmt | continue-stmt
               | capability-stmt | try-stmt | throw-stmt | assert-stmt
               | block | expr-stmt | assign-stmt

let-stmt       = "let" [ "mut" ] IDENT [ ":" type ] "=" expr ";"
if-stmt        = "if" expr block [ "else" ( if-stmt | block ) ]
while-stmt     = "while" expr block
for-stmt       = "for" IDENT "in" expr block
return-stmt    = "return" [ expr ] ";"
break-stmt     = "break" ";"
continue-stmt  = "continue" ";"
capability-stmt= "capability" IDENT { "," IDENT } ";"
try-stmt       = "try" block "catch" "(" IDENT ")" block
throw-stmt     = "throw" expr ";"
assert-stmt    = "assert" [ "(" ] expr [ "," expr ] [ ")" ] ";"
                (* `assert cond, "msg";` and `assert(cond, "msg");` are both accepted *)
block          = "{" { statement } "}"
expr-stmt      = expr ";"
assign-stmt    = assignable ( "=" | "+=" | "-=" | "*=" | "/=" | "%=" ) expr ";"
assignable     = IDENT | postfix "." IDENT | postfix "[" expr "]"

expr           = or-expr
or-expr        = and-expr { "or" and-expr }
and-expr       = comparison { "and" comparison }
comparison     = additive { ( "==" | "!=" | "<" | ">" | "<=" | ">=" ) additive }
additive       = multiplicative { ( "+" | "-" ) multiplicative }
multiplicative = unary { ( "*" | "/" | "%" ) unary }
unary          = ( "-" | "not" ) unary | power
power          = postfix [ "**" unary ]              (* right associative *)
postfix        = primary { "." IDENT | "(" [ args ] ")" | "[" expr "]" }
args           = arg { "," arg }
arg            = [ IDENT ":" ] expr
primary        = INT | FLOAT | STRING | "true" | "false"
               | IDENT | "(" expr ")" | list-literal | range-expr
list-literal   = "[" [ expr { "," expr } ] "]"
range-expr     = additive ".." additive

type           = "Int" | "Float" | "Bool" | "String" | "Unit" | "Never"
               | "List" "<" type ">"
               | "Tensor" "<" dtype [ "," "[" dims "]" ] ">"
               | "Color" | "Canvas" | "Model" | "Dataset" | "Range"
               | IDENT                               (* a struct name *)
dtype          = "Float32" | "Float64" | "Int32" | "Bool"
dims           = INT { "," INT }
```

Restrictions enforced during parsing or semantic analysis:

* Chained comparisons (`a < b < c`) are rejected (PE2031) because their meaning
  would be ambiguous.
* A positional argument may not follow a named argument (PE2033).
* Struct constructors and built-in methods do not accept named arguments
  (PE3004); native functions and user functions do.
* `Any` is not writable in source. It exists only in native signatures.
* `Never` is the type of `throw`, `panic`, and non-returning expressions; it is
  assignable to every type.

---

## 4. Types

### 4.1 Primitive types

| Type | Values | Notes |
|---|---|---|
| `Int` | signed 64-bit integers | checked arithmetic; overflow is PE4004 |
| `Float` | binary64 | division by zero is PE4005 |
| `Bool` | `true`, `false` | no implicit conversion to or from Int |
| `String` | immutable Unicode text | concatenation only with `+` between Strings |
| `Unit` | the single value `()` | functions without `-> T` return Unit |

There is **no implicit numeric conversion**. `1 + 2.0` is a type error; write
`float(1) + 2.0` or use matching types. `int(x)` truncates toward zero;
`float(x)` widens.

### 4.2 Lists

`List<T>` is an ordered, mutable sequence with reference semantics. Literals must
be homogeneous; mixed numeric literals are not unified (`[1, 2.0]` is an error).
An empty literal needs an annotation: `let xs: List<Int> = [];`.

Indexing `xs[i]` is bounds-checked. Assignment to an index or field mutates the
referenced object even when the binding itself is immutable; `let` prevents
rebinding only.

### 4.3 Tensors

`Tensor<dtype>` has a statically unknown shape; `Tensor<dtype, [d1, d2, ...]>`
has a static shape. Dtypes are `Float32`, `Float64`, `Int32`, `Bool`. Only
floating tensors can require gradients.

* Elementwise arithmetic accepts two tensors of the same dtype and
  broadcast-compatible shapes, or a tensor and a numeric scalar.
* `matmul` requires rank-2 operands whose inner dimensions agree.
* Static shape mismatches that can be proven are compile errors (PE3003).
  Dynamic mismatches are runtime faults (PE6001).
* `Float32` values are rounded to binary32 on construction and storage;
  arithmetic is performed in binary64 before the result is stored. This is a
  documented implementation deviation, not IEEE-754 binary32 arithmetic.

### 4.4 Structs

```
struct Point { x: Int, y: Int }
let p = Point(3, 4);
p.x = 5;
```

Constructors take every field positionally, exactly once. Fields are mutable.
Structs have no methods, inheritance, generics, or visibility modifiers in 0.1.

### 4.5 Opaque host types

`Color`, `Canvas`, `Model`, `Dataset`, and `Range` are values created by native
functions. They can be passed to natives and accessed through the properties and
methods in §8. They cannot be constructed directly.

---

## 5. Expressions and operators

Precedence, from lowest to highest:

| Level | Operators | Associativity | Result |
|---|---|---|---|
| 1 | `or` | left | Bool; short-circuit |
| 2 | `and` | left | Bool; short-circuit |
| 3 | `== != < > <= >=` | non-chaining | Bool |
| 4 | `+ -` | left | Int, Float, or String concatenation (`+` only) |
| 5 | `* / %` | left | Int or Float |
| 6 | unary `-`, `not` | right | operand type / Bool |
| 7 | `**` | right | Int or Float |
| 8 | calls, field access, indexing | left | varies |

Semantics:

* `Int / Int` truncates toward zero; `Int % Int` has the sign of the dividend
  (`-7 / 2 == -3`, `-7 % 2 == -1`). Division or remainder by zero is PE4005.
* `Int ** Int` requires a non-negative exponent and is overflow-checked.
* Integer overflow in `+ - * **` is a runtime fault, never wraparound.
* Comparisons require both operands to have the same primitive type. Ordering is
  defined for Int, Float and String; equality also for Bool.
* `and`/`or` evaluate left-to-right and short-circuit.
* String `+` concatenates. All other operators on Strings are type errors.
* Tensor arithmetic follows §4.3. `tensor op scalar` is permitted for
  `+ - * / **` where the scalar is Int, Float or Bool.
* Conditions in `if`, `while`, and `assert` must be `Bool`.
* Range `a..b` requires Int bounds and is half-open (`0..0` is empty). Ranges
  are iterable but not indexable.

---

## 6. Statements and control flow

* `let` introduces an immutable binding; `let mut` allows rebinding and compound
  assignment. Redeclaration in the same scope is PE3001.
* Assignment targets are variables, fields, or indexes. Assigning to an
  immutable variable is PE3007.
* `if`/`else` and `while` require Bool conditions. `for` iterates a List or a
  Range; the loop variable is immutable per iteration.
* `break` and `continue` are only valid inside loops (PE3011).
* `return` must match the declared return type. A non-Unit function must return
  a value on every path (PE3008); the analysis is conservative and does not
  reason about infinite loops.
* Blocks introduce scopes. Variables are block-scoped.
* Statements after a definite `return`/`throw` are diagnosed as unreachable
  (PE3102) but are still type-checked, so their declarations receive slots.
  Code generation omits them.

### 6.1 Errors

`throw expr;` raises a catchable runtime value; the expression must be a
`String` in 0.1. `try { ... } catch (e) { ... }` binds the message as `String`.
An uncaught `throw` terminates the run with `PE4020`, a stack trace and exit
code 3; this is what a `.pac` program sees when it raises without a handler.
Runtime faults (arithmetic, bounds, assertions, native failures) are catchable
in the same way. Host capability denials (`PE4001`) are catchable but grant no
authority; resource limits (`PE4003`) are **not** catchable and terminate the
program. `panic(message)` is an uncatchable fault.

`assert(cond, "message");` or `assert cond, "message";` raises PE4010 with the
message when `cond` is false. The message defaults to `"assertion failed"`.

---

## 7. Capabilities

A capability is a named authority granted by the embedding host. v0.1 defines:

| Capability | Protects |
|---|---|
| `compute` | tensor parameter creation, autodiff, model init/training, model predict, save/load |
| `fs` | all file reads and writes, including `graphics.save` |
| `ui` | handing rendered frames to a host presentation backend (`graphics.present`) |

Rules:

1. A function that calls a protected native MUST declare the capability inside
   its own body: `capability fs;` or `capability compute, fs;`.
2. Capabilities are not inherited by callees. A helper that reads a file must
   declare `fs` itself, even when its caller declares it.
3. Capabilities must appear directly in the function body, not in nested blocks,
   and may be declared once (PE3005).
4. The host independently grants capabilities at run time. A declared capability
   that the host did not grant fails with PE4001 at the first protected call.
5. `peacock audit` reports declared and statically visible privileged calls. It
   does not replace the runtime check.
6. `ui` governs *presentation*, not input: a program can hand a frame to the
   host, but v0.1 exposes no window, pointer, keyboard or display query. A host
   may grant `ui` while attaching no backend; the call then fails with PE4006
   (a host configuration error, not a capability denial).

The default CLI grants nothing. Use `--grant compute`, `--grant fs`,
`--grant ui`, or a comma-separated combination.

---

## 8. Standard library (natives)

All natives are implemented in the bootstrap runtime, are visible only after the
matching `use`, and carry static signatures checked by the compiler. The full
list with signatures is in `peacock/compiler/builtins.py`; documentation is in
`NATIVE_DOCS`. Summary:

### 8.1 Global

`print(value)`, `str(value)`, `len(value)`, `type_name(value)`, `panic(message)`,
`tensor(nested_list)`, `range(start, end)`, `int(x)`, `float(x)`, `abs(x)`.

### 8.2 `math`

`pi()`, `e()`, `sqrt(x)`, `pow(b, e)`, `exp(x)`, `log(x)`, `log2(x)`, `sin(x)`,
`cos(x)`, `tan(x)`, `atan2(y, x)`, `floor(x)`, `ceil(x)`, `round(x)`, `min(a, b)`,
`max(a, b)`, `clamp(x, low, high)`. Domain errors are runtime faults.

### 8.3 `text`

`char_at(s, i)`, `is_alpha(ch)`, `is_digit(ch)`, `is_alnum(ch)`, `is_space(ch)`,
`ord(ch)`, `chr(code)`, `split_lines(s)`.

### 8.4 `fs` (capability `fs`)

`read_text(path)` → String, `write_text(path, content)` → Unit. Paths are
resolved inside the host sandbox; `..`, absolute paths, symlink escapes, NUL
bytes, and files over the host limit are rejected.

### 8.5 `process`

`args()` → `List<String>`: host-provided arguments (after `--` in the CLI).

### 8.6 `colour`

`srgb(r, g, b, alpha)`, `oklab(l, a, b, alpha)`, `oklch(l, c, h, alpha)`,
`from_hex("#rrggbb[aa]")`, `mix(a, b, t)`, `lighten(c, amount)`, `darken(c, amount)`,
`rotate_hue(c, degrees)`, `complement(c)`, `luminance(c)`, `contrast(a, b)`,
`palette(count, seed)`, `to_css(c)`. Colours are linear-light internally and
Oklab/Oklch-aware.

### 8.7 `graphics` (saving requires `fs`, presenting requires `ui`)

`canvas(width, height)`, `clear(canvas, color)`, `fill(canvas, color)`,
`rect(canvas, x, y, w, h, color)`, `circle(canvas, cx, cy, r, color)`,
`line(canvas, x0, y0, x1, y1, width, color)`, `gradient(canvas, colors, angle)`,
`glow(canvas, cx, cy, radius, color)`, `aurora(canvas, time, seed)`,
`save(canvas, path)`, `present(canvas)`.

`present(canvas)` hands the canvas to the host's attached presentation backend
and returns `Unit`. The program does not learn which backend it is; the host
decides (static-web frames, HTTP server, or an embedding host). Without a host
grant the call fails with PE4001; with a grant but no backend it fails with
PE4006. Both are catchable and neither presents a frame. The native does not
mutate the canvas, so a program may keep drawing and present again (a frame
sequence). There is no frame clock, input or vsync in 0.1.

Canvas properties: `width`, `height`. Methods: `save(path)` (capability `fs`).
Dimensions are 1–4096 per side with a total-pixel safety limit; colours are
premultiplied RGBA in the framebuffer.

### 8.8 `motion`

`ease(name, t)`, `spring_steps(start, target, stiffness, damping, steps, dt)`.
Unknown easing names are runtime faults. Names include `linear`,
`ease_in_quad`, `ease_out_quad`, `ease_in_out_cubic`, `ease_out_back` (see
`frontend/easing.py` for the canonical list).

### 8.9 `nn` (capability `compute`)

`parameter(data)`, `mse(predictions, targets)`, `cross_entropy(logits, labels)`,
`max_abs_diff(a, b)`, `xor()`, `spiral(per_class, noise, seed)`,
`dataset(features, labels)`, `train(model, data, loss:, optimiser:, epochs:,
learning_rate:, batch_size:, seed:)`, `accuracy(model, data)`, `loss(model, data,
loss:)`, `predict(model, x)`, `save(model, path)` and `load(path)` (also `fs`).

Tensor properties: `rank`, `shape`, `dtype`, `size`, `requires_grad`, `grad`.
Tensor methods: `sum`, `mean`, `max`, `min`, `exp`, `log`, `sqrt`, `abs`, `relu`,
`tanh`, `sigmoid`, `softmax`, `reshape(dims)`, `transpose`, `matmul(other)`,
`backward()`, `zero_grad()`, `item()`.

List methods: `len`, `push`, `pop`, `get`, `contains`, `index_of`, `join`,
`sort`, `reverse`. String methods: `len`, `upper`, `lower`, `trim`, `contains`,
`starts_with`, `ends_with`, `split`, `replace`, `substring(start, end)`.

---

## 9. Models and training declarations

```
model Net {
    input x: Tensor<Float32, [2]>
    output y: Tensor<Float32, [2]>
    stack {
        Dense(units: 8, activation: relu)
        Dense(units: 2)
    }
}
```

* Exactly one input and one output are supported in 0.1.
* Inputs/outputs must be floating tensors with a statically known shape. The
  model's feature dimension is the last input dimension.
* The stack must be non-empty. `Dense(units: N, activation: A)` is the only
  layer. `N` is an integer literal > 0. `A` is one of `linear`, `relu`,
  `sigmoid`, `tanh`, `softmax`, or a string with that name; the default is
  `linear`.
* The final layer's `units` must equal the output's last dimension.

`Net.init(seed: Int)` creates a `Model` value and requires `compute`.
`Training.run(model, dataset)` returns `List<Float>` of per-epoch losses.
`Training.evaluate(model, dataset)` returns accuracy as `Float`. Both require
`compute`.

Training fields and defaults:

| Field | Type | Default | Constraint |
|---|---|---|---|
| `objective` | String | `"cross_entropy"` | `"cross_entropy"` or `"mse"` |
| `optimiser` | String | `"adam"` | `"adam"` or `"sgd"` |
| `epochs` | Int | 10 | ≥ 1, ≤ host limit |
| `learning_rate` | Float | 0.01 | > 0 |
| `batch_size` | Int | 16 | ≥ 1 |
| `seed` | Int | 0 | any Int |

Values must be literals in 0.1 (PE3010). Unknown fields are rejected.

---

## 10. Runtime semantics and diagnostics

The compiler produces a verified bytecode image; the VM executes it with an
explicit value stack and a fixed slot frame per call.

* **Arithmetic** is checked. Integer overflow, division by zero, invalid
  exponentiation and invalid math domains raise catchable faults.
* **Bounds** are checked on list, string and tensor indexing.
* **Uninitialised locals** are a runtime fault (the compiler initialises only
  declared parameters and `let` bindings in order).
* **Recursion** is limited by the host call-depth budget.
* **Steps** are limited per run; the limit is not catchable.
* **Output** is limited by the host character budget.
* **Values** are reference values for List, Tensor, structs, Canvas, Model and
  Dataset; Int, Float, Bool, String, Unit and Range are value-like.

Diagnostic classes: PE1xxx lexical, PE2xxx syntactic, PE3xxx semantic,
PE4xxx runtime/security, PE5xxx host/artifact, PE6xxx intelligence engine,
PE7xxx frontend. Every diagnostic carries a code, severity, span, message and
optional hint; the CLI renders a caret line and the source excerpt.

---

## 11. Bytecode and artifacts

A compiled program is a `.pkb` container: magic `PEACOCK\x1a`, format version,
language version, canonical JSON image, and SHA-256. The image contains module
metadata, imports, functions (arity, slots, capabilities, code, source lines),
structs, models and training declarations. Before execution the VM re-verifies
the image, including opcodes, slots, jump targets, native names, arities,
capabilities and model/training references.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the instruction set and container
layout.

---

## 12. Not in 0.1

The following are **not** part of this version and must not be assumed to work:

* user-defined modules/files, generics, traits, enums, pattern matching,
  closures, first-class functions, operator overloading;
* classes/inheritance, interfaces, visibility, `pub`, `const`;
* concurrency, async/await, threads, generators;
* garbage collection tuning, arenas, manual memory management;
* a native code generator, LLVM/Wasm backend, GPU kernels;
* multiple model inputs/outputs, layers other than Dense, convolution/attention
  layers, optimisers other than SGD/Adam;
* a UI widget toolkit, 3D rendering, text shaping, accessibility;
* Android/iOS/desktop native shells;
* self-hosting (the bootstrap compiler is Python; one tokenizer is written in
  PEACOCK).

Anything in this list requires a specification change, positive and negative
tests, diagnostics and documentation before it can be called implemented.

---

## 13. Self-hosted type-model prototype (non-normative)

`selfhost/type_model.pac` is a PEACOCK-written migration prototype. It exercises
primitive/list/declared-nominal equality, `Never` bottom assignment, `<error>`
recovery, tensor dtype and known/unknown-shape assignment, and right-aligned
broadcast compatibility.
Its `TypeDesc` is a prototype representation, not a public source-level type.
The compiler API's opt-in `semantic_mode="shadow"` adapts supported primitive,
simple list, declared nominal and tensor annotations from parsed declarations, generates
relation assertions, and runs those assertions in the PEACOCK VM. Python's
`compiler/types.py` computes the expected results; any disagreement fails the
shadow check. Python semantic analysis then remains authoritative. The prototype
covers neither expression typing nor symbol/scope analysis, and it does not
change normative v0.1 acceptance. It is experimental validation infrastructure,
not a user-facing compiler mode or production replacement.
