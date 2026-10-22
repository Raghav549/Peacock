# Aṣṭādhyāyī corpus provenance and scope

`ashtadhyayi.json` is a compact derivative of `sutraani/data.txt` from
https://github.com/ashtadhyayi-com/data.

- Upstream commit: `5744762f010d677cfb43f347a42d02796cf615d6`
- Upstream file blob SHA: `c847b9e41054ec7efb9e63c0fdc093faa0007980`
- Retrieved: 2026-10-22
- Upstream rows preserved: 3,983 (1.1.1 through 8.4.68)
- Fields preserved: sūtra number, Devanagari text, source rule-kind labels,
  anuvṛtti references and adhikāra references.
- Fields omitted: transliteration and commentary-specific ordering metadata.
  No English translation is asserted or redistributed here.

The upstream README says: "You are free to use this data in your own projects
provided that appropriate credits are mentioned wherever applicable." Credit is
therefore retained here and in user-facing grammar documentation. This notice
does not relicense the ancient text or the upstream compilation.

The corpus is complete as **sūtra text and inheritance metadata**, not as an
executable interpretation. `sandhi.EXECUTABLE_RULE_IDS` separately records the
small set of computational rules with tests. No natural-Sanskrit parser, full
Aṣṭādhyāyī interpreter, or complete commentary collection is claimed.

## Connected literature in the same upstream project

The upstream repository also distributes Kāśikā, Mahābhāṣya, Siddhānta-kaumudī,
Laghu-kaumudī, Bālamanoramā, Tattvabodhinī, Nyāsa, Padamañjarī,
Paribhāṣenduśekhara, Vākyapadīya, Dhātu, Gaṇa, Uṇādi, Liṅgānuśāsana, Śikṣā and
other data. Their directories are catalogued in `literature.json`; their full
contents are not vendored or silently presented as locally verified texts.
