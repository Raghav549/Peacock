# Native व्याकरण tools

The `व्याकरण` namespace and `peacock/vyakarana/` package provide working corpus,
pratyāhāra and sandhi operations to `.सूत्र` programs and the CLI. They run
offline with the standard library only.

## Complete sūtra text corpus

The installed package contains **3,983 Aṣṭādhyāyī sūtra texts**, from `1.1.1`
`वृद्धिरादैच्` through `8.4.68` `अ अ`. Each row preserves its numeric ID,
Devanagari text, source rule-kind labels, anuvṛtti references and adhikāra
references. The 1.3 MB JSON is included as package data, so it remains available
after wheel installation.

Source and permission are recorded in
`peacock/vyakarana/data/PROVENANCE.md`: the compact data derives from
[`ashtadhyayi-com/data`](https://github.com/ashtadhyayi-com/data), commit
`5744762f010d677cfb43f347a42d02796cf615d6`, whose README permits project use
with appropriate credit. No unverified English translation is included.

| Native | Result |
|---|---|
| `व्याकरण.सूत्र(परिचय)` | numbered sūtra text |
| `व्याकरण.सूत्रसंख्या()` | `३९८३` |
| `व्याकरण.अन्वेषय(अन्वेषण, अवधि)` | up to 200 matching IDs/texts/labels |
| `व्याकरण.अनुवृत्ति(परिचय)` | inherited terms with source references |
| `व्याकरण.अधिकारविवरण(परिचय)` | adhikāra terms with source references |
| `व्याकरण.साहित्य()` | connected works, clearly labelled local vs catalogue-only |
| `व्याकरण.आच्छादन()` | number of separately executable sandhi rules |

## Executable pratyāhāra

`व्याकरण.प्रत्याहार(नाम)` interprets the fourteen Māheśvara rows algorithmically.
It includes the initial sound, skips intermediate it markers, stops after the
row carrying the requested final marker, and removes the repeated `ह` from
membership results. Examples:

| Input | Result |
|---|---|
| `अच्` | `अ इ उ ऋ ऌ ए ओ ऐ औ` |
| `इक्` | `इ उ ऋ ऌ` |
| `यण्` | `य व र ल` |
| `एङ्` | `ए ओ` |
| `हल्` | 33 distinct consonants |
| `अल्` | 42 distinct sounds |

Invalid sounds, unknown markers and reversed ranges are controlled errors.

## Executable vowel sandhi

`व्याकरण.संधि(वाम, दक्षिण)` accepts an explicit two-word boundary, not ambiguous
running prose. `व्याकरण.संधिसूत्र(वाम, दक्षिण)` returns the applied rule ID.
Devanagari independent vowels, mātrās, virāma and implicit final `अ` are handled.

| Rule | Implemented boundary examples |
|---|---|
| `6.1.101` — `अकः सवर्णे दीर्घः` | `राम + आलयः → रामालयः`; `गुरु + उपदेशः → गुरूपदेशः` |
| `6.1.87` — `आद्गुणः` | `राम + इन्द्रः → रामेन्द्रः`; `महा + ऋषिः → महर्षिः` |
| `6.1.88` — `वृद्धिरेचि` | `देव + औदार्यम् → देवौदार्यम्` |
| `6.1.77` — `इको यणचि` | `नदी + अत्र → नद्यत्र`; `सु + आगतम् → स्वागतम्` |

Unsupported boundaries fail instead of receiving an invented substitution.
There is no automatic sandhi splitting or claim that a Sanskrit sentence can be
unambiguously segmented without context.

## CLI

```bash
./bin/peacock व्याकरण सूत्र 1.1.1
./bin/peacock व्याकरण अन्वेषय गुण --अवधि 5
./bin/peacock व्याकरण प्रत्याहार अच्
./bin/peacock व्याकरण संधि नदी अत्र
./bin/peacock व्याकरण साहित्य
./bin/peacock व्याकरण आच्छादन
```

`examples/vyakarana.सूत्र` exercises the same operations through bytecode.

## Literature and executable coverage are different

The literature catalogue connects Kāśikā, Mahābhāṣya, Siddhānta-kaumudī,
Laghu-siddhānta-kaumudī, Bālamanoramā, Tattvabodhinī, Nyāsa, Padamañjarī,
Paribhāṣenduśekhara, Vākyapadīya, Dhātu, Gaṇa, Uṇādi, Liṅgānuśāsana, Śikṣā and
Tarkasaṅgraha to their upstream locations. Their full texts are **not** claimed
to be vendored or locally verified.

All 3,983 sūtra **texts** are present. Four sandhi rule IDs are currently
**computationally executable**, and the generic pratyāhāra algorithm is
executable. This is not yet a complete Pāṇinian derivation engine: dhātu
conjugation, nominal declension, kṛt/taddhita derivation, samāsa, the full
rule-conflict system and all commentaries still require explicit implementations
and linguistic tests.
