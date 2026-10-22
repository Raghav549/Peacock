# Linguist submission notes

Status: **prepared only**. No upstream pull request has been opened and nothing
has been accepted by GitHub. This file records the plan and the artefacts that
exist locally.

## Artefacts

| File | Purpose |
|---|---|
| `languages.yml` | proposed entry (`Peacock`, `.सूत्र`, `source.peacock`) |
| `peacock.tmLanguage.json` | TextMate grammar with keywords, types, numbers, strings, capabilities, comments |
| `samples/*.सूत्र` | representative programs (hello, types, tensors, colour, motion, capabilities) |
| `../assets/peacock.svg`, `../assets/peacock-256.png` | logo usable for editor/tooling metadata |
| `../editors/vscode/` | minimal VS Code extension using the grammar |

All samples are compiled by `./bin/peacock check` in CI-style local runs; a
grammar-only repository would not satisfy Linguist's usage expectations.

## Upstream requirements checked (2026-10-17)

The official [Linguist contribution guide](https://github.com/github-linguist/linguist/blob/main/CONTRIBUTING.md)
was inspected on 2026-10-17. It requires an entry in `lib/linguist/languages.yml`
(without `language_id` on initial proposal), grammar integration through the
upstream grammar tooling and an accepted grammar license, and representative
samples in Linguist's `samples/<language>/` tree. Tutorial/"Hello world" samples
are not accepted as representative usage evidence. Its current extension usage
bar is 2,000 indexed files per year for extensions expected multiple times per
repository, or 200 for names/extensions expected once per repository, excluding
forks, with reasonable distribution across distinct user/repository pairs.

This project does **not** currently meet that usage-evidence requirement on the
evidence available in this checkout. The samples here are authored for PEACOCK
and compile, but do not demonstrate independent public usage. `.सूत्र` conflicts
with other ecosystem file types are not yet comprehensively checked against the
upstream language database; check before proposing it. Thus a PR would be
premature even though draft metadata/grammar files are prepared. No upstream
submission or acceptance is claimed.

## Checklist before opening a PR

1. Gather GitHub code-search evidence meeting the live usage thresholds above,
   excluding forks and the project's own concentrated results; establish that
   `.सूत्र` assignment will not misclassify existing formats.
2. Confirm the upstream contribution guide and grammar licensing/tooling again
   at submission time.
3. Provide licensed, representative, non-tutorial PEACOCK samples showing
   genuine usage in the wild; document sample provenance and license.
4. Validate the TextMate grammar with the upstream tooling/editor and put it in
   the upstream-recognised grammar integration path (the local JSON draft alone
   is not sufficient).
5. Add a language entry without a `language_id`; run Linguist's prescribed
   tests/classifier checks in a Linguist checkout.
6. Open a PR against `github/linguist` only when evidence and eligibility exist;
   respond to maintainer review.
7. Only after merge and GitHub deployment, verify language statistics and
   highlighting on a real repository before claiming recognition.

## Risks

* Grammars for languages with few public repositories are often rejected as
  insufficiently used.
* `.सूत्र` is also used by unrelated formats/tools; the entry must not claim or
  break those. GitHub resolves ambiguous extensions by statistics, so PEACOCK
  will not always win.
* Renaming or re-scoping after submission is costly; stabilise keywords first.

## Non-claims

* There is no GitHub language recognition today.
* The presence of these files does not imply acceptance.
* Highlighting in a local editor is not GitHub highlighting.
