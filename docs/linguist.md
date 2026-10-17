# GitHub Linguist support: prepared, not accepted

PEACOCK is **not** a GitHub-recognised language. Nothing has been submitted
upstream. The repository is prepared so a contribution can be made when the
language is stable enough to justify it.

## Files in this repository

```
linguist/
  languages.yml      # proposed language entry (name, type, extensions, tm_scope, ace_mode)
  peacock.tmLanguage.json   # TextMate grammar for .pac
  samples/           # representative .pac programs
  SUBMISSION.md      # submission checklist and current requirements
```

## Proposed registration

* Name: `Peacock`
* Type: `programming`
* Extensions: `.pac`
* `tm_scope`: `source.peacock`
* `ace_mode`: `text`
* `codemirror_mode`/`codemirror_mime_type`: omitted until a mode exists

## Requirements that must be satisfied upstream (checked, not assumed)

Linguist requires a language to be used in real repositories, with a grammar,
samples and a maintainer. A pull request must add the entry to `languages.yml`,
the grammar to `vendor/grammars` or a new submodule, and samples to
`samples/<Language>/`. Requirements change; verify the current CONTRIBUTING guide
and grammar registry before submitting.

## Status

| Step | State |
|---|---|
| Investigate Linguist requirements | done (documented in `linguist/SUBMISSION.md`) |
| Language definition and `.pac` mapping | prepared |
| TextMate grammar | prepared |
| Representative samples | present in `linguist/samples/` (compiled by the real compiler) |
| Distinctive logo/icon | present in `assets/` |
| Upstream pull request | **not opened** |
| Accepted by GitHub | **no** |

Do not claim official recognition, syntax highlighting on GitHub, or inclusion
in the language picker until the upstream change is merged.
