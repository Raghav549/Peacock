# PEACOCK research programme

This directory records the research basis, open questions, design decisions and
measurement methodology behind PEACOCK. It exists so that claims in the
repository can be traced to sources, hypotheses and evidence rather than to
enthusiasm.

## Research stance

PEACOCK is an engineering project informed by research, not a venue for novel
results. The project:

* **cites ideas** and implements them independently; it does not copy source
  code from other language implementations, engines or frameworks;
* **separates borrowed mechanisms from original contributions**; nothing in this
  repository is claimed as a new scientific discovery;
* **records negative and inconclusive results** rather than hiding them;
* **never fabricates** citations, measurements, test output or completed
  features;
* **prefers a small verified system** over a broad unverified one.

The reference implementation is deliberately modest: a Python bootstrap, a
stack VM, a pure-Python tensor engine and a software rasteriser. That is the
honest substrate for these questions.

## Files

| File | Contents |
|---|---|
| [references.bib](references.bib) | 162 bibliographic entries (papers, books, standards, RFCs) covering the areas PEACOCK draws on |
| [literature-review.md](literature-review.md) | What the literature establishes, what PEACOCK adopts or rejects, and where the implementation is thinner than the state of the art |
| [open-questions.md](open-questions.md) | 18 numbered research questions with hypotheses, experiment designs, metrics, decision rules and current status |
| [architecture-decisions.md](architecture-decisions.md) | ADR-0001 … ADR-0021: context, decision, alternatives, consequences, and what would reverse each decision |
| [benchmark-methodology.md](benchmark-methodology.md) | How measurements are taken, what they do and do not mean, and the anti-comparison policy |
| [cpython-architecture.md](cpython-architecture.md) | Live architectural audit of `python/cpython` (`Grammar/`, `Parser/`, `Python/`, `Include/`, `Objects/`, `Modules/`, `Programs/`, `Tools/`, `PC/`, `PCbuild/`, `Mac/`, `Lib/test/`, `.github/workflows/`) and how each principle applies to PEACOCK |

## What research actually influenced what

| Area | Sources used as background | Artifact in this repository | Depth |
|---|---|---|---|
| Recursive-descent parsing, diagnostics | [aho2006compilers], [cooper2011engineering] | `lexer.py`, `parser.py`, `diagnostics.py` | textbook subset |
| Static typing, scopes | [pierce2002types], [milner1978theory], [wright1994syntactic] | `types.py`, `semantic.py` (monomorphic, no inference) | small subset |
| IR and optimisation | [click1995simple], [muchnick1997advanced], [cytron1991ssa] | linear PIR, folding/DCE, verifier | no SSA, no register allocation |
| Stack VM and bytecode | [lindholm2014jvm], [ertl2003interpreters], [smith2005virtual] | `bytecode.py`, `vm.py` | interpreter only |
| Capability security | [dennis1966programming], [saltzer1975protection], [levy1984capability], [miller2006robust], [hardy1988confused] | static + VM + host checks | best-effort confinement, not a kernel sandbox |
| Automatic differentiation | [baydin2018automatic], [griewank2008evaluating], [rumelhart1986learning] | reverse-mode tape in `tensor.py` | dense ops only |
| Optimisers and initialisation | [kingma2015adam], [robbins1951stochastic], [glorot2010understanding], [he2015delving] | SGD/momentum, Adam, Xavier/He | standard algorithms |
| Numerical behaviour | [goldberg1991what], [higham2002accuracy], [ieee754] | checked ints, Float32 storage, binary64 compute | documented deviations |
| Colour | [iec61966], [cie2004colorimetry], [fairchild2013color], [ottosson2020oklab], [w3ccsscolor4] | sRGB/XYZ/Lab/Oklab/Oklch, WCAG contrast | no ICC, no spectral |
| Raster graphics | [porter1984compositing], [crow1977aliasing], [pharr2023pbr] | 4×4 coverage AA, premultiplied source-over | 2-D only, no text shaping |
| Procedural imagery | [perlin1985image], [perlin2002improving], [gustavson2005simplex] | artistic fBm aurora | not a physical sky model |
| Motion and physics | [lasseter1987principles], [penner2001easing], [ogata2010modern], [eberly2010game], [catto2009modeling] | easing, springs, timelines, AABB rigid bodies | no joints/rotation |
| Layout | [cssflexbox], [badros2001cassowary] | one-pass flex stacks | no constraint solver |
| Benchmarking | [georges2007statistically], [mytkowicz2009producing], [hoefler2015scientific], [beyer2019reliable] | `benchmarks.py`, `reference-machine.json` | medians only, no confidence intervals |
| Testing | [claessen2000quickcheck], [miller1990empirical], [jia2011analysis] | deterministic fuzzers, unit/integration suite | no coverage-guided fuzzing |

## Citation status (honest)

The bibliography was compiled from the published literature during this build.
The build environment has **no outbound access** to publisher or arXiv hosts, so
identifiers and URLs could not be fetched or machine-verified here. Entries
contain only standard bibliographic fields; questionable identifiers were
omitted rather than guessed. Before citing this file externally, verify each
entry against the publisher/DOI resolver. If an error is found, correct it in a
pull request — do not add an entry you cannot verify.

This is why the review below says "the literature establishes X" only for
well-established results and labels contested or implementation-specific claims
as such.

## What this programme is not

* It is **not** a claim that PEACOCK has produced research results. Apart from
  measurements of this implementation, there are none.
* It is **not** a claim of AGI capability. The "AGI research tooling" deliverable
  is a planned phase (see [../ROADMAP.md](../ROADMAP.md)); v0.1 provides
  deterministic training/evaluation primitives, seeds, reports and provenance,
  not an AGI system or a novel learning algorithm.
* It is **not** a literature-complete survey. It covers the mechanisms this
  project uses or plans to use; entire fields (compilers for ML, distributed
  training, formal verification, HCI evaluation) are only touched.
* It is **not** a licence to reuse code. Ideas are cited; implementations here
  are original and written for this repository.

## Adding research

1. Add a verified entry to `references.bib` (or mark it `note = {unverified}` and
   do not cite it in a claim).
2. State in the review what the source establishes and what this project does
   differently.
3. If it motivates an experiment, add a numbered question in `open-questions.md`
   with a falsifiable metric and a decision rule.
4. If it changes a design, add an ADR. Do not rewrite an accepted ADR silently;
   supersede it.
5. Never cite a source you have not read enough to characterise accurately.
