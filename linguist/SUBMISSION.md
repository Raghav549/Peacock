# Linguist submission notes

Status: **prepared only**. No upstream pull request has been opened and nothing
has been accepted by GitHub. This file records the plan and the artefacts that
exist locally.

## Artefacts

| File | Purpose |
|---|---|
| `languages.yml` | proposed entry (`Peacock`, `.pac`, `source.peacock`) |
| `peacock.tmLanguage.json` | TextMate grammar with keywords, types, numbers, strings, capabilities, comments |
| `samples/*.pac` | representative programs (hello, types, tensors, colour, motion, capabilities) |
| `../assets/peacock.svg`, `../assets/peacock-256.png` | logo usable for editor/tooling metadata |
| `../editors/vscode/` | minimal VS Code extension using the grammar |

All samples are compiled by `./bin/peacock check` in CI-style local runs; a
grammar-only repository would not satisfy Linguist's usage expectations.

## Checklist before opening a PR

1. Confirm the current Linguist CONTRIBUTING requirements (grammar licensing,
   submodule vs. vendored grammar, sample requirements, language naming).
2. Ensure the TextMate grammar validates and highlights the samples without
   errors in at least one editor.
3. Add `languages.yml` entry with `type: programming`, `extensions: [.pac]`,
   `tm_scope: source.peacock`.
4. Add samples under the project's sample directory and keep them minimal.
5. Provide a maintainer contact and evidence of real-world usage.
6. Open the pull request against `github/linguist`; respond to review.
7. Only after merge: state that GitHub recognises PEACOCK and verify the
   language bar/highlighting on a real repository.

## Risks

* Grammars for languages with few public repositories are often rejected as
  insufficiently used.
* `.pac` is also used by unrelated formats/tools; the entry must not claim or
  break those. GitHub resolves ambiguous extensions by statistics, so PEACOCK
  will not always win.
* Renaming or re-scoping after submission is costly; stabilise keywords first.

## Non-claims

* There is no GitHub language recognition today.
* The presence of these files does not imply acceptance.
* Highlighting in a local editor is not GitHub highlighting.
