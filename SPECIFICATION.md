# PEACOCK Language Specification — version 0.4

Status: **implemented subset**. This document describes what the v0.4 toolchain
actually accepts and executes. It is not a description of every feature PEACOCK
will eventually have. Anything not specified here is either rejected by the
compiler or reserved for a later version.

Canonical source extension: `.सूत्र`. Source files must be UTF-8 and should end
with a newline; the lexer accepts both LF and CRLF endings.

Normative keywords use `MUST`, `MUST NOT`, `SHOULD`. When this document and the
implementation disagree, that is a bug; the tests and this document are updated
together.

---

## 1. Program structure

A program is a sequence of top-level declarations:
```
program        = [ module-decl ] { use-decl | function | struct | model | training } EOF
module-decl    = "प्रकरण" IDENT
use-decl       = "उपयोग" IDENT [ ";" ]
```

* `प्रकरण` is optional but, if present, MUST be the first item.
* A module name does not create a namespace for values; v0.4 has one flat
  value namespace per program.
* `उपयोग` imports a standard-library namespace: `गणित`, `तन्त्रजाल`, `रङ्ग`,
  `चित्र`, `गति`, `सञ्चय`, `पाठ्य`, `प्रक्रिया`, `व्याकरण`, `दृश्य`, `त्रिअयाम`,
  `अभिकर्तृ`, `गणनयन्त्र`, or `सेवक`. Aliases (`उपयोग तन्त्रजाल रूपेण n`) are
  rejected (PE2005). A namespace MUST be imported before its members are used.
* There are no user-defined file imports in 0.4. The whole program is one file.
* Declarations are order-independent: a function may call one declared later.
* Names are Unicode identifiers. The first character is `_` or a Unicode
  letter; later characters may also be Unicode decimal digits or combining
  marks (categories `Mn`, `Mc`, `Me`). Identifier identity is normalised to NFC,
  so canonically equivalent spellings denote the same name. Sanskrit reserved
  words may not be identifiers. Withdrawn English keywords and standard names
  produce PE1007; other user-defined Unicode names are preserved.

Reserved for future versions and rejected with a targeted diagnostic (PE2001):
`असामकालिक प्रतीक्षा स्थिर सूचीभेद कार्यान्वयन आयात मिलान सार्वजनिक जनय उत्पादय`.

---

## 2. Lexical structure

### 2.1 Whitespace and comments

Whitespace separates tokens. Comments are `// line` and nestable
`/* block */` comments. An unterminated block comment is PE1001.

### 2.2 Literals

| Literal | Form | Notes |
|---|---|---|
| Integer | `0`, `42`, `४२`, `1_000`, `१_०००`, `0xFF`, `0b1010`, `0o17` | 64-bit signed range. Underscores separate digits and may not be leading, trailing or doubled. |
| दशमलव | `1.5`, `१.५`, `1e3`, `1e३`, `2.5e-2`, `२.५e-२`, `1_000.5` | binary64. |
| Boolean | `सत्य`, `असत्य` | |
| अक्षरमाला | `"text"` | must not span a physical line. |
| सूची | `[1, 2, 3]`, `[]` | empty lists need a type annotation. |

Decimal literals accept ASCII and other Unicode decimal digits, including
Devanagari. The decimal point, exponent marker (`e`/`E`) and radix prefixes
(`0x`, `0b`, `0o`) remain ASCII punctuation; radix digits follow the selected
base. Numeric values do not depend on the digit script.

अक्षरमाला escapes: `\n`, `\t`, `\r`, `\\`, `\"`, `\'`, `\0`, and `\u{HEX}` for a
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
`न`, conjunction `तथा`, disjunction `वा`.

---

## 3. Grammar (EBNF)

The following is the complete v0.4 grammar. `[ x ]` is optional, `{ x }` is
repetition, and alternatives are separated by `|`.
```
program        = [ module-decl ] { item } EOF
module-decl    = "प्रकरण" IDENT
item           = use-decl | function | struct | model | training

use-decl       = "उपयोग" IDENT [ ";" ]

function       = "कार्य" IDENT "(" [ params ] ")" [ "->" type ] block
params         = param { "," param }
param          = IDENT ":" type
block          = "{" { statement } "}"

struct         = "संघटन" IDENT "{" { field } "}"
field          = IDENT ":" type [ "," | ";" ]

model          = "प्रतिमान" IDENT "{" model-section { model-section } "}"
model-section  = input-section | output-section | stack-section
input-section  = "निवेश" IDENT ":" type
output-section = "निर्गम" IDENT ":" type
stack-section  = "क्रम" "{" { layer } "}"
layer          = IDENT "(" [ layer-args ] ")"
layer-args     = layer-arg { "," layer-arg }
layer-arg      = IDENT ":" ( INT | IDENT | STRING )

training       = "अभ्यास" IDENT "{" { training-field } "}"
training-field = IDENT ":" literal [ "," | ";" ]

statement      = let-stmt | if-stmt | while-stmt | for-stmt
               | return-stmt | break-stmt | continue-stmt
               | capability-stmt | try-stmt | throw-stmt | assert-stmt
               | block | expr-stmt | assign-stmt

let-stmt       = "स्थापय" [ "परिवर्तनीय" ] IDENT [ ":" type ] "=" expr ";"
if-stmt        = "यदि" expr block [ "अन्यथा" ( if-stmt | block ) ]
while-stmt     = "यावत्" expr block
for-stmt       = "प्रति" IDENT "मध्ये" expr block
return-stmt    = "प्रत्यानय" [ expr ] ";"
break-stmt     = "विच्छिन्दु" ";"
continue-stmt  = "अनुवर्तय" ";"
capability-stmt= "अधिकार" IDENT { "," IDENT } ";"
try-stmt       = "यत्न" block ( catch-clause [ finally-clause ] | finally-clause )
catch-clause   = "गृह्ण" "(" IDENT ")" block
finally-clause = "अन्ते" block
throw-stmt     = "क्षिप" expr ";"
assert-stmt    = "निश्चिनु" [ "(" ] expr [ "," expr ] [ ")" ] ";"
                (* `निश्चिनु cond, "msg";` and `निश्चिनु(cond, "msg");` are both accepted *)
block          = "{" { statement } "}"
expr-stmt      = expr ";"
assign-stmt    = assignable ( "=" | "+=" | "-=" | "*=" | "/=" | "%=" ) expr ";"
assignable     = IDENT | postfix "." IDENT | postfix "[" expr "]"

expr           = or-expr
or-expr        = and-expr { "वा" and-expr }
and-expr       = comparison { "तथा" comparison }
comparison     = additive { ( "==" | "!=" | "<" | ">" | "<=" | ">=" ) additive }
additive       = multiplicative { ( "+" | "-" ) multiplicative }
multiplicative = unary { ( "*" | "/" | "%" ) unary }
unary          = ( "-" | "न" ) unary | power
power          = postfix [ "**" unary ]              (* right associative *)
postfix        = primary { "." IDENT | "(" [ args ] ")" | "[" expr "]" }
args           = arg { "," arg }
arg            = [ IDENT ":" ] expr
primary        = INT | FLOAT | STRING | "सत्य" | "असत्य"
               | IDENT | "(" expr ")" | list-literal | range-expr
list-literal   = "[" [ expr { "," expr } ] "]"
range-expr     = additive ".." additive

type           = "पूर्णाङ्क" | "दशमलव" | "सत्यता" | "अक्षरमाला" | "एकक" | "अभाव"
               | "सूची" "<" type ">"
               | "आयाम" "<" dtype [ "," "[" dims "]" ] ">"
               | "वर्ण" | "चित्रपट" | "प्रतिमानप्रकार" | "दत्तसमूह" | "सीमा"
               | IDENT                               (* a struct name *)
dtype          = "दशमलव३२" | "दशमलव६४" | "पूर्णाङ्क३२" | "सत्यता"
dims           = INT { "," INT }
```

Restrictions enforced during parsing or semantic analysis:

* Chained comparisons (`a < b < c`) are rejected (PE2031) because their meaning
  would be ambiguous.
* A positional argument may not follow a named argument (PE2033).
* Struct constructors and built-in methods do not accept named arguments
  (PE3004); native functions and user functions do.
* `सर्व` is not writable in source. It exists only in native signatures.
* `अभाव` is the type of `क्षिप`, `विह्वल`, and non-returning expressions; it is
  assignable to every type.

---

## 4. Types

### 4.1 Primitive types

| Type | Values | Notes |
|---|---|---|
| `पूर्णाङ्क` | signed 64-bit integers | checked arithmetic; overflow is PE4004 |
| `दशमलव` | binary64 | division by zero is PE4005 |
| `सत्यता` | `सत्य`, `असत्य` | no implicit conversion to or from पूर्णाङ्क |
| `अक्षरमाला` | immutable Unicode text | concatenation only with `+` between अक्षरमाला values |
| `एकक` | the single value `()` | functions without `-> T` return एकक |

There is **no implicit numeric conversion**. `1 + 2.0` is a type error; write
`दशमलवीकरण(1) + 2.0` or use matching types. `पूर्णीकरण(x)` truncates toward zero;
`दशमलवीकरण(x)` widens.

### 4.2 Lists

`सूची<T>` is an ordered, mutable sequence with reference semantics. Literals must
be homogeneous; mixed numeric literals are not unified (`[1, 2.0]` is an error).
An empty literal needs an annotation: `स्थापय xs: सूची<पूर्णाङ्क> = [];`.

Indexing `xs[i]` is bounds-checked. Assignment to an index or field mutates the
referenced object even when the binding itself is immutable; `स्थापय` prevents
rebinding only.

### 4.3 Tensors

`आयाम<दत्तप्रकार>` has a statically unknown shape; `आयाम<दत्तप्रकार, [d1, d2, ...]>`
has a static shape. Dtypes are `दशमलव३२`, `दशमलव६४`, `पूर्णाङ्क३२`, `सत्यता`. Only
floating tensors can require gradients.

* Elementwise arithmetic accepts two tensors of the same dtype and
  broadcast-compatible shapes, or a tensor and a numeric scalar.
* `आव्यूहगुणन` requires rank-2 operands whose inner dimensions agree.
* Static shape mismatches that can be proven are compile errors (PE3003).
  Dynamic mismatches are runtime faults (PE6001).
* `दशमलव३२` values are rounded to binary32 on construction and storage;
  arithmetic is performed in binary64 before the result is stored. This is a
  documented implementation deviation, not IEEE-754 binary32 arithmetic.

### 4.4 Structs
```
संघटन Point { x: पूर्णाङ्क, y: पूर्णाङ्क }
स्थापय p = Point(3, 4);
p.x = 5;
```

Constructors take every field positionally, exactly once. Fields are mutable.
Structs have no methods, inheritance, generics, or visibility modifiers in 0.4.

### 4.5 Opaque host types

`वर्ण`, `चित्रपट`, `प्रतिमानप्रकार`, `दत्तसमूह`, `सीमा`, `दृश्यरचना`,
`त्रिअयामदृश्य`, and `अभिकर्तृप्रकार` are values created by native functions.
They can be passed to natives and accessed through the properties and methods in
§8. They cannot be constructed directly with struct literal syntax.

---

## 5. Expressions and operators

Precedence, from lowest to highest:

| Level | Operators | Associativity | Result |
|---|---|---|---|
| 1 | `वा` | left | सत्यता; short-circuit |
| 2 | `तथा` | left | सत्यता; short-circuit |
| 3 | `== != < > <= >=` | non-chaining | सत्यता |
| 4 | `+ -` | left | पूर्णाङ्क, दशमलव, or अक्षरमाला concatenation (`+` only) |
| 5 | `* / %` | left | पूर्णाङ्क or दशमलव |
| 6 | unary `-`, `न` | right | operand type / सत्यता |
| 7 | `**` | right | पूर्णाङ्क or दशमलव |
| 8 | calls, field access, indexing | left | varies |

Semantics:

* `पूर्णाङ्क / पूर्णाङ्क` truncates toward zero; `पूर्णाङ्क % पूर्णाङ्क` has the sign of the dividend
  (`-7 / 2 == -3`, `-7 % 2 == -1`). Division or remainder by zero is PE4005.
* `पूर्णाङ्क ** पूर्णाङ्क` requires a non-negative exponent and is overflow-checked.
* Integer overflow in `+ - * **` is a runtime fault, never wraparound.
* Comparisons require both operands to have the same primitive type. Ordering is
  defined for पूर्णाङ्क, दशमलव and अक्षरमाला; equality also for सत्यता.
* `तथा`/`वा` evaluate left-to-right and short-circuit.
* अक्षरमाला `+` concatenates. All other operators on Strings are type errors.
* आयाम arithmetic follows §4.3. `आयामीकरण op scalar` is permitted for
  `+ - * / **` where the scalar is पूर्णाङ्क, दशमलव or सत्यता.
* Conditions in `यदि`, `यावत्`, and `निश्चिनु` must be `सत्यता`.
* सीमा `a..b` requires पूर्णाङ्क bounds and is half-open (`0..0` is empty). Ranges
  are iterable but not indexable.

---

## 6. Statements and control flow

* `स्थापय` introduces an immutable binding; `स्थापय परिवर्तनीय` allows rebinding and compound
  assignment. Redeclaration in the same scope is PE3001.
* Assignment targets are variables, fields, or indexes. Assigning to an
  immutable variable is PE3007.
* `यदि`/`अन्यथा` and `यावत्` require सत्यता conditions. `प्रति` iterates a सूची or a
  सीमा; the loop variable is immutable per iteration.
* `विच्छिन्दु` and `अनुवर्तय` are only valid inside loops (PE3011).
* `प्रत्यानय` must match the declared return type. A non-एकक function must return
  a value on every path (PE3008); the analysis is conservative and does not
  reason about infinite loops.
* Blocks introduce scopes. Variables are block-scoped.
* Statements after a definite `प्रत्यानय`/`क्षिप` are diagnosed as unreachable
  (PE3102) but are still type-checked, so their declarations receive slots.
  Code generation omits them.

### 6.1 Errors

`क्षिप expr;` raises a catchable runtime value; the expression must be a
`अक्षरमाला` in 0.4. `यत्न { ... } गृह्ण (e) { ... }` binds the message as
`अक्षरमाला`. A `यत्न` MUST have a catch clause, an `अन्ते` cleanup clause, or a
catch followed by cleanup; multiple catch clauses are not supported.

`अन्ते { ... }` runs exactly once when its protected region completes normally,
throws, returns, or transfers control with `विच्छिन्दु`/`अनुवर्तय`. Nested cleanup
regions unwind from inner to outer. The VM saves the pending error/value/jump,
restores it after cleanup, and then resumes that completion. A new throw, return
or loop transfer in cleanup supersedes the saved completion while still
unwinding outer cleanups. A `गृह्ण` handles a protected error before an adjacent
`अन्ते` runs; if the catch itself throws, cleanup still runs.

An uncaught `क्षिप` terminates the run with `PE4020`, a stack trace and exit
code 3. Runtime faults (arithmetic, bounds, assertions, native failures) are
catchable in the same way. Host capability denials (`PE4001`) are catchable but
grant no authority. Resource limits (`PE4003`) and `विह्वल(सन्देश)` are fatal:
they bypass catch and cleanup execution rather than extending a run whose host
budget has been exhausted.

`निश्चिनु(cond, "message");` or `निश्चिनु cond, "message";` raises PE4010 with the
message when `cond` is false. The message defaults to `"assertion failed"`.

---

## 7. Capabilities

A capability is a named authority granted by the embedding host. v0.4 defines:

| Capability | Protects |
|---|---|
| `गणना` | tensor/autodiff/model operations and agent planning/execution |
| `सञ्चय` | all file reads and writes, including `चित्र.रक्ष` and `दृश्य.रक्ष` |
| `दृश्य` | attaching rendered frames or retained UI to a host presentation backend |
| `सञ्जाल` | PEACOCK-controlled HTTP listeners/connections and host-configured LLM providers |

Rules:

1. A function that calls a protected native MUST declare the capability inside
   its own body: `अधिकार सञ्चय;` or `अधिकार गणना, सञ्चय;`.
2. Capabilities are not inherited by callees. A helper that reads a file must
   declare `सञ्चय` itself, even when its caller declares it.
3. Capabilities must appear directly in the function body, not in nested blocks,
   and may be declared once (PE3005).
4. The host independently grants capabilities at run time. A declared capability
   that the host did not grant fails with PE4001 at the first protected call.
5. `peacock audit` reports declared and statically visible privileged calls. It
   does not replace the runtime check.
6. `दृश्य` governs host attachment. `चित्र.प्रदर्शय` presents a canvas and
   `दृश्य.प्रदर्शय` attaches a retained UI to a browser or native-window host.
   Local event binding, queueing and hit-testing do not themselves grant a host
   window or network listener. A host may grant `दृश्य` while attaching no
   backend; presentation then fails with PE4006 (a host configuration error,
   not a capability denial).
7. `सञ्जाल` does not provide a general URL-fetch API. Server natives can bind
   only numeric IP addresses through the bounded server implementation. LLM
   endpoint/model/credentials are configured by the host, not by source-level
   tool arguments; declaring the capability does not choose or grant a provider.

The default CLI grants nothing. Use `--grant गणना`, `--grant सञ्चय`,
`--grant दृश्य`, `--grant सञ्जाल`, or a comma-separated combination.

---

## 8. Standard library (natives)

All natives are implemented in the bootstrap runtime, are visible only after the
matching `उपयोग`, and carry static signatures checked by the compiler. The full
list with signatures is in `peacock/compiler/builtins.py`; documentation is in
`NATIVE_DOCS`. Summary:

### 8.1 Global

`मुद्रय(मूल्य)`, `पाठ्यीकरण(मूल्य)`, `दैर्घ्य(मूल्य)`, `प्रकारनाम(मूल्य)`, `विह्वल(सन्देश)`,
`आयामीकरण(nested_list)`, `परिसर(आरम्भ, अन्त)`, `पूर्णीकरण(x)`, `दशमलवीकरण(x)`, `निरपेक्ष(x)`.

### 8.2 `गणित`

`वृत्तानुपात()`, `घाताधार()`, `वर्गमूल(क्ष)`, `घात(आधार, घाताङ्कः)`, `घाताङ्क(क्ष)`, `लघुगणक(क्ष)`, `द्विलघुगणक(क्ष)`, `ज्या(क्ष)`,
`कोटिज्या(क्ष)`, `स्पर्शज्या(क्ष)`, `द्विस्पर्शज्या(य, क्ष)`, `अधोमूल्य(क्ष)`, `ऊर्ध्वमूल्य(क्ष)`, `पूर्णीत(क्ष)`, `न्यूनतम(अ, ब)`,
`अधिकतम(अ, ब)`, `सीमित(क्ष, अधः, ऊर्ध्व)`. Domain errors are runtime faults.

### 8.3 `पाठ्य`

`अक्षरम्(s, i)`, `वर्णः(ch)`, `अङ्कः(ch)`, `वर्णाङ्कः(ch)`, `चिह्नमात्रा(ch)`, `रिक्तिः(ch)`,
`अक्षरसङ्ख्या(ch)`, `सङ्ख्याक्षर(संकेत)`, `पङ्क्तिविभाजन(s)`.

### 8.4 `सञ्चय` (capability `सञ्चय`)

`पाठ्यपठन(पथ)` → अक्षरमाला, `पाठ्यलेखन(पथ, अन्तर्वस्तु)` → एकक, and
`निधिरचना(पथ)` → एकक (creates a directory tree). Paths are resolved inside
the host sandbox; `..` traversal, absolute paths outside the root, symlink
escapes and NUL bytes are rejected. File reads/writes are subject to the host
file-size limit. Directory creation is capability-gated and sandbox-rooted, but
inherits the documented best-effort/TOCTOU limitations of `HostPolicy`; it is
not an OS-level sandbox.

### 8.5 `प्रक्रिया`

`तर्कावली()` → `सूची<अक्षरमाला>`: host-provided arguments (after `--` in the CLI).

### 8.6 `रङ्ग`

`एसआरजीबी(r, g, b, अपारदर्शिता)`, `ओकलैब(l, a, b, अपारदर्शिता)`, `ओकएलसीएच(l, c, h, अपारदर्शिता)`,
`षोडशात्("#rrggbb[aa]")`, `मिश्रय(a, b, t)`, `दीप्तय(c, परिमाण)`, `मन्दय(c, परिमाण)`,
`वर्णभ्रमय(c, अंश)`, `पूरकवर्ण(c)`, `द्युति(c)`, `विरोधद्युति(a, b)`,
`वर्णावली(संख्या, बीज)`, `शैलीपाठ्य(c)`, `बहुमिश्रय(वर्णावलीः, भारावली, वर्णावकाश)`,
`वर्णान्तर(अ, ब)`, and `वर्णक्षेत्रीकरण(वर्णमूल्य)`. Colours are linear-light
internally and Oklab/Oklch-aware. Weighted mixing supports `रैखिक`, `ओकलैब`,
`ओकएलसीएच`, `एसआरजीबी`, and approximate three-channel `व्यवकलन` modes.
`वर्णान्तर` is CIEDE2000; gamut mapping reduces Oklch chroma. The subtractive
mode is not a spectral or measured-paint simulation.

### 8.7 `चित्र` (saving requires `सञ्चय`, presenting requires `दृश्य`)

`चित्रपट्ट(विस्तार, औन्नत्य)`, `शुद्धय(चित्रपट्ट, color)`, `पूरय(चित्रपट्ट, color)`,
`आयत(चित्रपट्ट, x, y, w, h, color)`, `वृत्त(चित्रपट्ट, केन्द्रक्ष, केन्द्रय, r, color)`,
`रेखा(चित्रपट्ट, x0, y0, x1, y1, विस्तार, color)`, `वर्णक्रम(चित्रपट्ट, वर्णावलीः, कोण)`,
`प्रभा(चित्रपट्ट, केन्द्रक्ष, केन्द्रय, त्रिज्या, color)`, `उषोद्युति(चित्रपट्ट, काल, बीज)`,
`रक्ष(चित्रपट्ट, पथ)`, `प्रदर्शय(चित्रपट्ट)`.

`प्रदर्शय(चित्रपट्ट)` hands the canvas to the host's attached presentation backend
and returns `एकक`. The program does not learn which backend it is; the host
decides (static-web frames, HTTP server, or an embedding host). Without a host
grant the call fails with PE4001; with a grant but no backend it fails with
PE4006. Both are catchable and neither presents a frame. The native does not
mutate the canvas, so a program may keep drawing and present again (a frame
sequence). There is no frame clock, input or vsync in 0.4.

चित्रपट properties: `विस्तार`, `औन्नत्य`. Methods: `रक्ष(पथ)` (capability `सञ्चय`).
Dimensions are 1–4096 per side with a total-pixel safety limit; colours are
premultiplied RGBA in the framebuffer.

### 8.8 `गति`

`गतिशैली(नाम, t)`, `स्पृङ्गचरण(आरम्भ, लक्ष्य, दृढता, अवमन्दन, चरणानि, कालान्तर)`.
Unknown easing names are runtime faults. Names include `रैखिक`,
`आरम्भद्विघात`, `अन्तद्विघात`, `आरम्भान्तत्रिघात`, `अन्तपश्चात्` (see
`frontend/easing.py` for the canonical list).

### 8.9 `तन्त्रजाल` (capability `गणना`)

`प्राचल(दत्त)`, `माध्यवर्गदोष(पूर्वानुमानानि, लक्ष्याणि)`, `अन्तरएन्ट्रॉपी(असंस्कृतमान, चिह्न)`,
`अधिकतमनिरपेक्षान्तर(a, b)`, `असमानयोग()`, `सर्पिल(प्रतिवर्ग, विक्षोभ, बीज)`,
`दत्तरचना(विशेषक, चिह्न)`, `अभ्यासय(प्रतिमानमूल्य, दत्त, दोष:, अनुकूलक:, आवृत्ति:,
अधिगमदर:, समूहमान:, बीज:)`, `शुद्धता(प्रतिमानमूल्य, दत्त)`, `दोष(प्रतिमानमूल्य, दत्त,
दोष:)`, `पूर्वानुमान(प्रतिमानमूल्य, क्ष)`, `रक्ष(प्रतिमानमूल्य, पथ)` and `आहारय(पथ)` (also `सञ्चय`).

आयाम properties: `कोटि`, `आकृति`, `दत्तप्रकार`, `मान`, `अवकलआवश्यक`, `अवकल`.
आयाम methods: `योग`, `माध्य`, `अधिकतम`, `न्यूनतम`, `घाताङ्क`, `लघुगणक`, `वर्गमूल`, `निरपेक्ष`, `धनाङ्क`,
`अतिस्पर्शज्या`, `वक्रसीमा`, `कोमलाधिकतम`, `पुनराकृति(dims)`, `परिवर्त`, `आव्यूहगुणन(other)`,
`पश्चप्रसार()`, `शून्यअवकल()`, `अवयव()`.

सूची methods: `दैर्घ्य`, `योजय`, `निष्कासय`, `प्राप्नु`, `अन्तर्भूत`, `सूचकाङ्क`, `संयोजय`,
`क्रमय`, `विपर्यय`. अक्षरमाला methods: `दैर्घ्य`, `बृहदक्षर`, `लघ्वक्षर`, `शोधय`, `अन्तर्भूत`,
`आरम्भयुक्त`, `अन्तयुक्त`, `विभाजय`, `प्रतिस्थापय`, `उपपाठ्य(आरम्भ, अन्त)`.

### 8.10 `व्याकरण`

`सूत्र(परिचय)`, `सूत्रसंख्या()`, `अन्वेषय(अन्वेषण, अवधि)`, `प्रत्याहार(नाम)`,
`संधि(वाम, दक्षिण)`, `संधिसूत्र(वाम, दक्षिण)`, `अनुवृत्ति(परिचय)`,
`अधिकारविवरण(परिचय)`, `साहित्य()`, and `आच्छादन()` operate offline. The installed
corpus contains all 3,983 sūtra texts and inheritance references. Pratyāhāra
expansion is generic. Four vowel-sandhi rule IDs have explicit computational
implementations; text coverage must not be confused with full Pāṇinian
executable coverage. See [docs/language/vyakarana.md](docs/language/vyakarana.md).

### 8.11 `दृश्य` native UI builder

`सृज` creates `दृश्यरचना`; `पटल`, `पाठ्य`, `नोदक`, and `सम्पर्क` add nodes and
return integer IDs. `प्रवाह` and `जालक` perform native layout; `परिसीमा` and
`स्पर्शपरीक्षा` expose geometry; `अन्वीक्षा` reports overflow, empty labels,
contrast and touch-target findings. `एचटीएमएलपाठ्य` exports responsive escaped
`<html lang="sa">` without JavaScript, and `रक्ष` writes it with capability
`सञ्चय`.

`बन्धन(रचना, ग्रन्थि, घटनाप्रकार, क्रिया)` binds an inspectable action string.
Supported surface events are `स्पर्श`, `अधःस्पर्श`, `उत्सर्ग`, `कुञ्जिका`, `पाठ्य`,
`अवधान`, `प्रेषण`, `पिदध्मि` and wildcard `*` for bindings. Bindings bubble through
enabled ancestors. `घटनाप्रेषय` posts a bounded local/host event,
`अग्रघटना(रचना, विलम्ब)` returns `[]` on timeout or a homogeneous record
`[id, kind, node, x, y, key, text, handler, action]`, and `घटनासंख्या` returns
the queue length. `पाठ्यस्थापय`, `सक्रियतास्थापय`, `अवधान` mutate text, enabled
state and focus. `प्रदर्शय` requires `दृश्य` and an attached interactive host.

The CLI attaches these hosts with `--ui-serve PORT` or `--window`. Browser events
use same-origin `/event` POSTs; the X11 host maps native pointer/key/close events
to the same queue. The event queue is bounded at 1024. Native accessibility APIs,
full complex-script shaping, text-input widgets and a general frame scheduler
remain outside this UI model. See [docs/frontend/ui-builder.md](docs/frontend/ui-builder.md)
and [docs/platforms/README.md](docs/platforms/README.md).

### 8.12 `त्रिअयाम`

`सृज` creates `त्रिअयामदृश्य`. `घन`, `गोलक`, `भ्रमय`, `प्रकाश`,
`त्रिभुजसंख्या`, and `अङ्कन` implement bounded meshes, object rotation, coloured
point lights and CPU perspective rendering into `चित्रपट`. Rasterisation uses
back-face culling and a reciprocal-depth buffer. Smooth normals, textures, ray
tracing and GPU execution are not defined. See
[docs/frontend/scene3d.md](docs/frontend/scene3d.md).

### 8.13 `अभिकर्तृ` (planning/execution requires `गणना`)

`सृज` creates `अभिकर्तृप्रकार` with a goal and step bound. `तथ्य`, `नियम`,
`प्राप्नु`, and `तथ्यावली` manage a string blackboard and positive-cost
condition/action/effect rules. `योजना` performs bounded Dijkstra search;
`चलाय` applies the plan; `स्थिति`, `अनुसरण`, and `तथ्यावली` expose the result.
Planning is deterministic and limited to 1024 steps/rules and 4096 expanded
states. Separately, `स्वायत्त(उद्देश्य, अधिकतमचरण)` requires `सञ्जाल` and a
host-configured LLM runner. It returns `[status, text, steps, trace-json]` for a
bounded chat/tool loop; only host-registered, schema-validated tools are
available. This is neither unrestricted tool execution nor AGI. See
[docs/ai-engine/agents.md](docs/ai-engine/agents.md).

### 8.14 `गणनयन्त्र` (operations require `गणना`)

`पश्चात्तन्त्राणि()` lists usable backends and `विवरण(तन्त्र)` returns
backend/device/vendor/version/hardware strings. `संकलय`, `गुणय`, `धनाङ्क` and
`आव्यूहगुणन` take a backend name (`स्वयम्`, `क्रमक`, or `त्वरक`) plus tensors.
The CPU backend is the reference. `त्वरक` requires an actual OpenCL
GPU/accelerator and never silently falls back; `स्वयम्` may select CPU. OpenCL
supports bounded Float32 addition, multiplication, ReLU and rank-2 matrix
multiplication, not GPU autodiff or general model execution. See
[docs/ai-engine/tensors.md](docs/ai-engine/tensors.md).

### 8.15 `सेवक` (capability `सञ्जाल`)

`श्रृणु(सङ्केत, द्वार)` binds a numeric-IP synchronous HTTP listener and returns
an integer host handle; `द्वार(सेवक)` returns its actual port. `स्वीकुरु(सेवक,
विलम्ब)` accepts one request or returns `[]` on timeout. A request is the
homogeneous record `[id, method, target, headers-json, UTF-8-body]`.
`प्रत्युत्तरय(सेवक, अभिप्राय, स्थितिः, body, content-type)` completes the one
outstanding request; `पिदध्मि(सेवक)` closes the listener/connection. Header,
body, response and handle limits are enforced. Chunked requests, pipelining,
TLS, authentication, concurrency and binary bodies are not implemented. Host
cleanup closes remaining handles. See [docs/platforms/README.md](docs/platforms/README.md).

---

## 9. Models and training declarations
```
प्रतिमान Net {
    निवेश x: आयाम<दशमलव३२, [2]>
    निर्गम y: आयाम<दशमलव३२, [2]>
    क्रम {
        सघन(एककानि: 8, सक्रियण: धनाङ्क)
        सघन(एककानि: 2)
    }
}
```

* Exactly one input and one output are supported in 0.4.
* Inputs/outputs must be floating tensors with a statically known shape. The
  model's feature dimension is the last input dimension.
* The stack must be non-empty. `सघन(एककानि: N, सक्रियण: A)` is the only
  layer. `N` is an integer literal > 0. `A` is one of `रैखिक`, `धनाङ्क`,
  `वक्रसीमा`, `अतिस्पर्शज्या`, `कोमलाधिकतम`, or a string with that name; the default is
  `रैखिक`.
* The final layer's `एककानि` must equal the output's last dimension.

`Net.प्रारम्भ(बीज: पूर्णाङ्क)` creates a `प्रतिमानप्रकार` value and requires `गणना`.
`Training.चलाय(प्रतिमानमूल्य, दत्त)` returns `सूची<दशमलव>` of per-epoch losses.
`Training.मूल्याङ्कय(प्रतिमानमूल्य, दत्त)` returns accuracy as `दशमलव`. Both require
`गणना`.

Training fields and defaults:

| Field | Type | Default | Constraint |
|---|---|---|---|
| `उद्देश्य` | अक्षरमाला | `"अन्तरएन्ट्रॉपी"` | `"अन्तरएन्ट्रॉपी"` or `"माध्यवर्गदोष"` |
| `अनुकूलक` | अक्षरमाला | `"आदम"` | `"आदम"` or `"यादृच्छिकअवरोह"` |
| `आवृत्ति` | पूर्णाङ्क | 10 | ≥ 1, ≤ host limit |
| `अधिगमदर` | दशमलव | 0.01 | > 0 |
| `समूहमान` | पूर्णाङ्क | 16 | ≥ 1 |
| `बीज` | पूर्णाङ्क | 0 | any पूर्णाङ्क |

Values must be literals in 0.4 (PE3010). Unknown fields are rejected.

---

## 10. Runtime semantics and diagnostics

The compiler produces a verified bytecode image; the VM executes it with an
explicit value stack and a fixed slot frame per call.

* **Arithmetic** is checked. Integer overflow, division by zero, invalid
  exponentiation and invalid math domains raise catchable faults.
* **Bounds** are checked on list, string and tensor indexing.
* **Uninitialised locals** are a runtime fault (the compiler initialises only
  declared parameters and `स्थापय` bindings in order).
* **Recursion** is limited by the host call-depth budget.
* **Steps** are limited per run; the limit is not catchable.
* **Output** is limited by the host character budget.
* **Values** are reference values for सूची, आयाम, structs, चित्रपट, प्रतिमानप्रकार,
  दत्तसमूह, दृश्यरचना, त्रिअयामदृश्य and अभिकर्तृप्रकार; पूर्णाङ्क, दशमलव, सत्यता,
  अक्षरमाला, एकक and सीमा are value-like.

Diagnostic classes: PE1xxx lexical, PE2xxx syntactic, PE3xxx semantic,
PE4xxx runtime/security, PE5xxx host/artifact, PE6xxx intelligence engine,
PE7xxx frontend. Every diagnostic carries a code, severity, span, message and
optional hint; the CLI renders a caret line and the source excerpt.

---

## 11. Bytecode and artifacts

A compiled program is a `.बीज` container: magic `PEACOCK\x1a`, format version,
language version, canonical JSON image, and SHA-256. The image contains module
metadata, imports, functions (arity, slots, capabilities, code, source lines),
structs, models and training declarations. Before execution the VM re-verifies
the image, including opcodes, slots, jump targets, native names, arities,
capabilities and model/training references.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the instruction set and container
layout.

---

## 12. Not in 0.4

The following are **not** part of this version and must not be assumed to work:

* user-defined modules/files, generics, traits, enums, pattern matching,
  closures, first-class functions, operator overloading;
* classes/inheritance, interfaces, visibility, `सार्वजनिक`, `स्थिर`;
* general concurrency, async/await, language threads or generators (host HTTP
  and window implementations use bounded implementation threads internally);
* garbage collection tuning, arenas, manual memory management;
* whole-language native AOT, LLVM or Wasm. The separate C backend implements
  only the subset in [docs/native.md](docs/native.md) and rejects other opcodes;
* multiple model inputs/outputs, layers other than सघन, convolution/attention
  layers, optimisers other than SGD/Adam;
* GPU autodiff/training, CUDA/Metal/Vulkan, asynchronous device graphs, or
  GPU/ray-traced 3D; smooth-normal interpolation, textures and mesh formats;
* complete native complex-script text shaping/accessibility, text-input widgets,
  or a general UI frame scheduler. The X11/browser event hosts are concrete but
  limited implementations, not a cross-platform widget framework;
* a complete executable Aṣṭādhyāyī, Sanskrit sentence segmentation, declension,
  conjugation or automatic samāsa analysis;
* AGI, unconstrained autonomy, model-provided authority, or a built-in hosted
  LLM. The bounded agent uses an explicitly configured external/local provider;
* verified Android/iOS packages or devices in this release environment. Shell
  sources exist, but SDK/Xcode execution is still required; only the Linux
  desktop shell was executed here;
* general HTTPS clients/servers, HTTP chunking/pipelining, binary request bodies
  or multi-request concurrent server dispatch;
* self-hosting (the bootstrap compiler is Python; tokenizer, parser and
  experimental semantic-shadow components are PEACOCK programs, not a self-hosted
  compiler).

Anything in this list requires a specification change, positive and negative
tests, diagnostics and documentation before it can be called implemented.

---

## 13. Self-hosted type-model prototype (non-normative)

`selfhost/type_model.सूत्र` is a PEACOCK-written migration prototype, not a
normative source-level type API. Its recursive `TypeDesc` exercises primitive,
list, nominal, opaque and tensor relations; `अभाव` bottom assignment;
`<error>` recovery; broadcasting; unary/binary/list/index rules; a lexical
binding stack; declarations, assignment mutability, function signatures, call
argument/return checks and condition/iterable rules.

The compiler API's opt-in `semantic_mode="shadow"` and CLI
`peacock check --semantic-shadow` first run the Python analyser, then translate
supported typed-AST expressions, local declarations, scopes, names, assignments,
user-function signatures/calls and returns into a generated PEACOCK probe
program. The PEACOCK VM executes the probe; relation and semantic probe counts
are reported in compiler stats. Tests differentially exercise valid/invalid
programs and the current example corpus. Field/member resolution, native
overloads, model/training analysis, diagnostic production/recovery parity, IR
and later compiler phases are still outside the kernel. Python remains the
production authority; there is no production switch and PEACOCK is not
self-hosting.
