# Sanskrit-native grammar and literary foundations

This document explains the linguistic design of PEACOCK 0.4. The
[normative specification](../../SPECIFICATION.md) remains the complete authority
for EBNF, types, evaluation, capabilities, diagnostics, and runtime limits. This
document supplies the vocabulary rationale, the relationship to Sanskrit
grammatical literature, and the boundaries of that relationship.

PEACOCK is a formal programming language written with Sanskrit vocabulary. It is
**not** a parser for unrestricted Sanskrit prose, a computational implementation
of the entire *Aṣṭādhyāyī*, or a claim that classical grammar solves programming
language design. Every analogy below has an explicit implementation boundary.

## 1. Source identity

* The language name is **PEACOCK / मयूर**.
* UTF-8 source files end in **`.सूत्र`**.
* Verified bytecode images end in **`.बीज`**; model files end in **`.ज्ञान`**.
* Reserved source vocabulary is Sanskrit. Mathematical operators and punctuation
  remain conventional ASCII so that precedence and token boundaries are visually
  unambiguous.
* The lexer normalises identifiers to Unicode NFC. A canonically equivalent
  spelling therefore denotes the same source identifier.
* Internal AST, bytecode, artifact, and host-policy identifiers are stable
  implementation IDs. They are not alternative spellings accepted in source.
  The lexer canonicalises native words once, before parsing; the VM does not
  translate strings during execution.

A source file is a *sūtra* in the general sense of a concise, ordered rule text;
the extension does not assert that a program is one of Pāṇini's grammatical
sūtras.

## 2. Complete reserved grammar vocabulary

The following tables list the implemented words. `SPECIFICATION.md` §4 gives
their exact productions and §5–§8 their semantics.

### Declarations and definitions

| Word | Grammatical role |
|---|---|
| `प्रकरण` | optional compilation-unit heading |
| `उपयोग` | standard-namespace import |
| `रूपेण` | import alias marker |
| `कार्य` | function definition |
| `स्थापय` | local binding |
| `परिवर्तनीय` | mutable-binding modifier |
| `संघटन` | product/record definition |
| `प्रतिमान` | neural-model declaration |
| `अभ्यास` | training-configuration declaration |
| `अधिकार` | function-local capability declaration |
| `मुख्य` | canonical entry-point name |

### Control, truth, and failure

| Word | Grammatical role |
|---|---|
| `यदि`, `अन्यथा` | conditional and alternative |
| `यावत्` | condition-controlled loop |
| `प्रति`, `मध्ये` | iteration over a range or collection |
| `प्रत्यानय` | return a result |
| `विच्छिन्दु`, `अनुवर्तय` | break and continue |
| `सत्य`, `असत्य` | Boolean literals |
| `तथा`, `वा`, `न` | short-circuit conjunction/disjunction and negation |
| `यत्न`, `गृह्ण` | protected region and catchable-failure handler |
| `क्षिप` | raise a catchable string fault |
| `निश्चिनु` | checked assertion |
| `विह्वल` | native uncatchable panic operation |

The words `सूचीभेद`, `मिलान`, `कार्यान्वयन`, `सार्वजनिक`, `स्थिर`,
`आयात`, `असामकालिक`, `प्रतीक्षा`, `जनय`, and `उत्पादय` are
reserved for future grammar. They receive targeted diagnostics; reservation is
not an implementation claim.

### Model and training declarations

| Word | Role |
|---|---|
| `निवेश`, `निर्गम` | model input and output tensors |
| `क्रम` | ordered layer stack |
| `सघन` | dense layer |
| `एककानि`, `सक्रियण` | layer width and activation |
| `उद्देश्य`, `अनुकूलक` | training objective and optimiser |
| `आवृत्ति`, `अधिगमदर`, `समूहमान`, `बीज` | epochs, learning rate, batch size, and deterministic seed |
| `प्रारम्भ`, `चलाय`, `मूल्याङ्कय` | model initialisation, training run, and evaluation |

### Native types and authorities

| Category | Source forms |
|---|---|
| Scalar/unit | `पूर्णाङ्क`, `दशमलव`, `सत्यता`, `अक्षरमाला`, `एकक` |
| Compound | `सूची<T>`, `आयाम<दत्तप्रकार, [आकृति]>` |
| Dtype | `दशमलव३२`, `दशमलव६४`, `पूर्णाङ्क३२` |
| Host values | `वर्ण`, `चित्रपट`, `प्रतिमानप्रकार`, `दत्तसमूह`, `सीमा` |
| Recovery/internal signature display | `अभाव`, `सर्व` |
| Capabilities | `गणना`, `सञ्चय`, `दृश्य` |
| Standard namespaces | `गणित`, `तन्त्रजाल`, `रङ्ग`, `चित्र`, `गति`, `पाठ्य`, `प्रक्रिया`, `सञ्चय` |

Algorithm values are native words too: activations include `रैखिक`,
`धनाङ्क`, `वक्रसीमा`, `अतिस्पर्शज्या`, and `कोमलाधिकतम`; losses include
`माध्यवर्गदोष` and `अन्तरएन्ट्रॉपी`; optimisers include
`यादृच्छिकअवरोह` and `आदम`. The motion enumeration is listed centrally in
`peacock/sanskrit.py` and generated into the editor grammars.

## 3. Unicode lexical rules

1. An identifier starts with `_` or a Unicode letter. Subsequent characters may
   also be Unicode decimal digits or combining marks (`Mn`, `Mc`, `Me`). This is
   necessary for Devanagari vowel signs, virāma, anusvāra, and visarga.
2. Identifier comparison uses NFC, not case folding, transliteration, or an
   approximate linguistic comparison.
3. Decimal integer and floating literals accept ASCII digits and other Unicode
   decimal digits, including `०१२३४५६७८९`. Thus `४२`, `१.५`, and `१e२` are
   numeric literals with the same values as `42`, `1.5`, and `1e2`.
4. The decimal point, exponent `e`/`E`, and radix prefixes `0x`, `0b`, `0o`
   remain ASCII. Hexadecimal digits are not replaced by Devanagari letters.
5. A digit cannot begin an identifier. `_` may separate digits, but not lead,
   trail, or occur twice in a numeric literal.
6. Strings retain their contents exactly apart from the specified escapes.
   Native algorithm strings are translated only at the semantic boundary where
   an enumeration is required; arbitrary user text is never machine-translated.
7. English spellings of withdrawn keywords and reserved standard vocabulary are
   rejected with `PE1007` and a Sanskrit replacement hint. Ordinary user names
   such as `net` remain legal identifiers unless they collide with the reserved
   standard vocabulary.

These are deliberately finite lexical rules. They do not invoke sandhi,
lemmatisation, morphology, or an AI model, so compilation remains deterministic
and works offline. A separate native `व्याकरण` library now provides offline
corpus lookup, pratyāhāra expansion and four explicit two-boundary vowel-sandhi
rules; it is not part of tokenisation and does not make the compiler a general
Sanskrit NLP system. See [vyakarana.md](vyakarana.md).

## 4. Pāṇinian design principles, with exact limits

### 4.1 संज्ञा — exact technical designation

*Aṣṭādhyāyī* 1.1.1, **वृद्धिरादैच्**, assigns the technical term `vṛddhi`
to a precisely identified collection. The relevant lesson is not the phonological
operation; it is that a technical vocabulary must have an exact denotation
[panini1x1x1].

PEACOCK therefore keeps one canonical vocabulary in `peacock/sanskrit.py`.
Keyword tokens, native signatures, type display, semantic options, editor
syntax, and documentation derive from that inventory. A Sanskrit word is not
chosen as a decorative label for several unrelated operations, and collisions
in the reverse map are rejected at import time.

### 4.2 उपदेश and इत् — separate metalanguage from object language

*Aṣṭādhyāyī* 1.3.2, **उपदेशेऽजनुनासिक इत्**, defines a marker within the
domain of grammatical instruction [panini1x3x2]. It demonstrates why a marker in
a formal description need not be part of the resulting linguistic form.

PEACOCK makes a smaller but analogous distinction: source spellings, stable
internal symbol IDs, serialized opcodes, and runtime values are different
layers. Canonicalisation occurs before parsing; an internal ID is never exposed
as a second source language. Unlike an `it` marker, a PEACOCK internal name is an
engineering implementation detail, not a Sanskrit morphological operation.

### 4.3 अधिकार and अनुवृत्ति — scope and inherited context

*Aṣṭādhyāyī* 3.1.1, **प्रत्ययः**, is an `adhikāra` heading whose traditional
domain extends through 5.4.160 [panini3x1x1]. Krishna and Goyal's computational
model also uses `anuvṛtti` to organise rule groups and explicitly tracks rule
sequencing [krishna2015derivative].

PEACOCK adopts the general value of a visible domain, not Pāṇini's implicit
inheritance algorithm. `अधिकार गणना;`, for example, applies only in the function
body containing it. It is neither inherited by callees nor a host grant. Block
scopes are explicit in the AST. The compiler does not silently carry context
across unrelated declarations; explicit scope is preferred where hidden
`anuvṛtti` would make diagnostics difficult.

The shared word `अधिकार` therefore means **declared authority** in PEACOCK. It
must not be confused with the technical `adhikāra` heading rule merely because
the same Sanskrit word is used.

### 4.4 यथासंख्यम् — ordered one-to-one correspondence

*Aṣṭādhyāyī* 1.3.10, **यथासंख्यमनुदेशः समानाम्**, states ordered
one-to-one correspondence for equal sequences [panini1x3x10]. This motivates a
design review of positional correspondence, not a direct function-calling
algorithm borrowed from grammar.

In PEACOCK, positional arguments correspond to parameters in source order;
arity is checked, and named arguments use explicit native names. Tensor shape
checks similarly reject incompatible dimensions instead of guessing a
correspondence. Broadcasting has its own specified numerical rules and is not
claimed to follow this sūtra.

### 4.5 विप्रतिषेध and परत्व — deterministic conflict resolution

*Aṣṭādhyāyī* 1.4.2, **विप्रतिषेधे परं कार्यम्**, is a `paribhāṣā`
concerning conflict between rules [panini1x4x2]. Its interpretive role in the
Aṣṭādhyāyī is more specific than programming-language precedence.

PEACOCK takes only the general requirement that conflict resolution be stated,
not left to implementation accident. Its actual rule is a fixed expression
precedence table plus a documented right-associative power operator and rejected
chained comparisons. The recursive-descent parser implements that table
directly; it does not execute a simulation of `vipratiṣedha`.

### 4.6 सामर्थ्य — syntactic presence is not semantic validity

*Aṣṭādhyāyī* 2.1.1, **समर्थः पदविधिः**, belongs to the interpretive
conditions on operations involving complete words [panini2x1x1]. At a high level
it reminds language designers that formal combination requires meaningful
compatibility.

PEACOCK separates parsing from semantic analysis: a call may be syntactically
well formed but still fail type, arity, capability, mutability, or shape checks.
This is an ordinary typed-compiler pipeline, not an implementation of Sanskrit
`sāmarthya`, `kāraka`, or natural-language understanding.

## 5. Wider Sanskrit literary context

Patañjali's *Vyākaraṇa-Mahābhāṣya*, which also preserves and discusses
Kātyāyana's `vārttika` tradition, models a different necessary activity:
examining terse rules through objections, alternatives, and commentary
[patanjalimahabhashya]. The engineering counterpart in this repository is a
normative specification accompanied by positive and negative tests, explicit
diagnostics, and architecture decisions. The tests are not presented as a
formal proof of the whole language.

Bhartṛhari's *Vākyapadīya* investigates language and meaning beyond a mere
sequence of audible units [bhartrharivakyapadiya]. It offers a philosophical
reminder that a token stream is not yet program meaning. PEACOCK's concrete
answer is conventional and implementable: AST structure, scoped names, types,
verified bytecode, and specified VM transitions. No `sphoṭa` theory is embedded
in the runtime, and no metaphysical claim is part of compiler correctness.

These sources inform documentation discipline and distinctions between form,
context, and meaning. They are not quoted as empirical evidence for VM speed,
type soundness, neural performance, or machine intelligence.

## 6. What the arXiv research changes—and what it does not

The Sanskrit-computing papers were read as design constraints, not copied as
implementation code:

* Krishna and Goyal model derivative-noun generation using rule classes,
  `anuvṛtti`-based groups, inheritance, and strict sequencing
  [krishna2015derivative]. This supports making rule domains and order
  inspectable. PEACOCK does not generate Sanskrit derivative nouns.
* Rama and Lakshmanan describe a computational schema for euphonic conjunction
  (`sandhi`) [rama2009sandhi]. This is relevant to possible future Sanskrit
  developer tools, but PEACOCK's lexer uses explicit Unicode character classes
  and fixed token boundaries.
* Dave, Singh, Prathosh, and Lall show that sandhi splitting is non-unique and
  context-dependent [dave2020sandhi]. Consequently, the compiler must not split
  an identifier probabilistically or silently rewrite compounds.
* Li and Girrbach report learned segmentation and morphological parsing,
  including imperfect task scores [li2022segmentation]. Such research is not a
  deterministic substitute for the language's lexical grammar.
* SanskritShala provides neural segmentation, morphology, dependency parsing,
  and compound-identification tools [sandhan2023sanskritshala]. It is a possible
  external annotation aid, not a compiler dependency.
* ByT5-Sanskrit demonstrates byte-level multitask Sanskrit NLP and reports
  strong benchmark results [nehrdich2024byt5]. PEACOCK neither bundles this model
  nor claims its results.
* Gorthi and Mamidi propose studying `kāraka` relations for multimodal grounding
  [gorthi2022karaka]. This is a research direction for structured semantic roles,
  not evidence that the present runtime understands scenes or language.
* Jayanti describes deriving computer-science terminology through Pāṇinian
  productive grammar for original technical writing [jayanti2026indic]. This is
  precedent for an intentional native technical lexicon rather than untranslated
  English keywords; it is not a ready-made PEACOCK dictionary.

The verified abstracts and URLs are recorded in
[`research/references.bib`](../../research/references.bib). No neural Sanskrit
package, network service, or downloaded corpus is needed to compile a program.

## 7. Independent toolchain and native AI boundary

Sanskrit vocabulary does not replace implementation depth. The current pipeline
is a hand-written lexer, recursive-descent parser, semantic analyser, typed PIR,
optimiser, verifier, custom bytecode container, and stack VM. PEACOCK-written
tokenizer/parser components are differentially tested against the bootstrap.
The compiler is **not yet self-hosting**, and the Python bootstrap is still an
external development dependency.

The native AI substrate includes dense tensors, broadcasting, reverse-mode
autodiff, model/training declarations, seeded optimisation, evaluation,
versioned model serialisation, and bounded symbolic agents with explicit rules,
plans and traces. Sanskrit `kāraka`-inspired semantic structures, transformer
architectures, LLM/tool-using agents, broader Sanskrit NLP integration, and AGI
remain research directions unless separately implemented and tested. In
particular, none of the grammatical sources or papers above establishes an AGI
capability, and PEACOCK does not claim one.

## 8. Maintenance rules

1. Add or change a reserved word only in `peacock/sanskrit.py`, then update the
   normative specification, generated grammars, examples, and tests together.
2. Preserve deterministic, total lexical behaviour. Do not add probabilistic
   tokenisation to the compiler.
3. Test decomposed versus precomposed Unicode, combining marks, Devanagari
   digits, invalid legacy spellings, and every changed native call.
4. Keep protocol/storage keys stable unless the artifact format is deliberately
   versioned. Source translation must not silently invalidate verified images.
5. Cite the original sūtra number for grammatical claims and distinguish direct
   textual content from PEACOCK's design interpretation.
6. Record arXiv identifiers only after checking their abstracts. Separate a
   paper's reported result from a feature implemented in this repository.
