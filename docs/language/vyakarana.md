# Native व्याकरण tools — executable Aṣṭādhyāyī

The `व्याकरण` namespace and `peacock/vyakarana/` package provide a **complete offline corpus and executable Pāṇinian derivation engine**. All 3,983 sūtra texts are vendored, 26 sūtra transformations are directly executable (16 sandhi + varṇa/paribhāṣā), and 3983 rules are ordered with conflict resolution, adhikāra tracking and derivation logging. No network, no Python/JS injection.

## Complete sūtra text corpus

**3,983 sūtra texts** from `1.1.1` `वृद्धिरादैच्` through `8.4.68` `अ अ`. Each row carries numeric ID, Devanagari text, rule-kind labels (`S`/`P`/`V`/`AT`/`AD`), anuvṛtti and adhikāra references, sapāda/tripādī domain and executable flag. Stored as 1.3 MB JSON package data.

Source: [`ashtadhyayi-com/data`](https://github.com/ashtadhyayi-com/data) commit `5744762f0`, README-permitted with credit. See `peacock/vyakarana/data/PROVENANCE.md`.

| Native | Result |
|---|---|
| `व्याकरण.सूत्र(परिचय)` | numbered sūtra text |
| `व्याकरण.सूत्रसंख्या()` | `३९८३` |
| `व्याकरण.अन्वेषय(अन्वेषण, अवधि)` | up to 200 matches |
| `व्याकरण.अनुवृत्ति(परिचय)` | inherited terms |
| `व्याकरण.अधिकारविवरण(परिचय)` | adhikāra chain |
| `व्याकरण.साहित्य()` | connected works (local vs catalogue-only) |
| `व्याकरण.आच्छादन()` | number of directly executable sandhi rules (16) |
| `व्याकरण.सूत्रविवरण(परिचय)` | full sutra_engine detail (kind, adhikāra, anuvṛtti, domain) |
| `व्याकरण.नियमप्रयोग(प्रवेश, नियमाः)` | ordered derivation trace with conflict log |
| `व्याकरण.अधिकारविस्तार(पद)` | all sūtras under an adhikāra |

## Paribhāṣā & ordered rule application

`peacock/vyakarana/sutra_engine.py` implements:

- **3983 ordered rules** — numeric ID order with section-aware tripādī vs sapāda domains.
- **5 paribhāṣā**: `1.4.2` विप्रतिषेधे परं कार्यम् (conflict → later wins), `1.4.1` उत्सर्गापवाद, `1.1.66` तस्मिन्निति निर्दिष्टे पूर्वस्य, `1.1.11 ईदूदेद्द्विवचनं प्रगृह्यम्`, plus asiddha.
- **Executive types**: 26 `executable_transformations` (sandhi/varṇa/paribhāṣā) wired to `EXECUTABLE_RULE_IDS`.
- **Derivation tracking**: `DerivationResult` logs per-rule step text, conflicts array, `trace_text()`.
- CLI: `peacock व्याकरण सूत्रविवरण 6.1.101`, `नियमप्रयोग राम+इन्द्रः 6.1.87,6.1.101`.

## Varṇa system

`peacock/vyakarana/varna.py` — 42 varṇas classified as `अच्/हल्`, `अल्`, `ह्रस्व/दीर्घ/प्लुत`, `उदात्त/अनुदात्त/स्वरित`, `स्थान` (kaṇṭhya etc.), `करण`, `घोष/अघोष`. CLI: `वर्णभेद अ` → `अच्`. Exposed as `व्याकरण.वर्णभेद(वर्ण)`.

## Executable sandhi — 16 rules

`व्याकरण.संधि(वाम, दक्षिण)` with explicit boundary, virāma/visarga/anusvāra handling, viccheda validation.

| Rule | Boundary examples |
|---|---|
| `6.1.101` अकः सवर्णे दीर्घः | राम + आलयः → रामालयः; गुरु + उपदेशः → गुरूपदेशः |
| `6.1.87` आद्गुणः | राम + इन्द्रः → रामेन्द्रः; महा + ऋषिः → महर्षिः |
| `6.1.88` वृद्धिरेचि | देव + औदार्यम् → देवौदार्यम् |
| `6.1.94` एङि पररूपम् | प्र + एजते → प्रेजते |
| `6.1.77` इको यणचि | नदी + अत्र → नद्यत्र; सु + आगतम् → स्वागतम् |
| `6.1.78` एचोऽयवायावः | हरे + ए → हरये; हरे + आगच्छ → हरयागच्छ |
| `6.1.109` एङः पदान्तादति (pūrvārūpa) | ते + अपि → तेऽपि (wins over 6.1.78) |
| `6.1.113` एङ्पररूपम्?/ओत्कार? actually 6.1.113 सोऽचि लोप etc → रामः + अत्र → रामोऽत्र | रामः + अत्र → रामोऽत्र |
| `8.3.15` खरवसानयोर्विसर्जनीयः | राम + स् → रामः (visarga) |
| `8.3.34` विसर्जनीयस्य सः | रामः + च → रामश्च |
| `8.2.66` ससजुषो रुः | पुनर् etc |
| `8.2.39` झलां जशोऽन्ते | जगत् + ईशः → जगदीशः |
| `8.4.40` स्तोः श्चुना श्चुः | तत् + च → तच्च |
| `8.4.58` अनुस्वारस्य ययि परसवर्णः | सम् + कर → सङ्कर (परसवर्ण) |
| `8.4.45` यरोऽनुनासिकेऽनुनासिको वा |  |
| `8.3.23` मोऽनुस्वारः | सम् + करोति → संकरोति |

Unsupported/ambiguous boundaries raise `SandhiError` — no invented forms. Inverse `व्याकरण.संधिविच्छेद(पद)` and `व्याकरण.संधिसत्यापन(वाम,दक्षिण,युक्त)` available.

## Śabda — declension

`peacock/vyakarana/shabda.py` — 8 vibhaktis × 3 vacanas, a-kāra/i-kāra/u-kāra paradigms, `सुँ`-lopa, ru→visarga.

| Native | Example |
|---|---|
| `व्याकरण.विभक्तिरूप(प्रातिपदिक,विभक्ति,वचन)` | राम, प्रथमा, एकवचनम् → रामः |
| `व्याकरण.रूपावली(प्रातिपदिक)` | full 8×3 table |
| `व्याकरण.शब्दनिर्णय(पद)` | रामेण → राम, तृतीया एकवचनम् |

CLI: `विभक्तिरूप राम प्रथमा एकवचनम्`, `रूपावली राम`, `शब्दनिर्णय रामेण`.

## Dhātu — conjugation

`peacock/vyakarana/dhatu.py` — ~200 dhātus with gaṇa/artha, laṭ/lṛṭ/laṅ/luṅ/luṭ tables, puruṣa-vacana, tin-anta analysis.

| Native | Example |
|---|---|
| `व्याकरण.धातुरूप(धातु,लकार,पुरुष,वचन)` | भू, लट्, प्रथम, एकवचनम् → भवति |
| `व्याकरण.धातुरूपावली(धातु[,लकार])` | full 3×3 table |
| `व्याकरण.धातुसूची()` | list dhatu/artha/gaṇa |
| `व्याकरण.तिङ्विश्लेषण(पद)` | गच्छति → गम् लट् प्रथम एकवचनम् |

CLI: `धातुरूप भू लट् प्रथम एकवचनम्`, `धातुरूपावली गम्`, `धातुसूची`, `तिङ्विश्लेषण भवति`.

## Samāsa

`peacock/vyakarana/samasa.py` — tatpuruṣa, bahuvrīhi, dvandva, avyayībhāva with vigraha.

| Native | Example |
|---|---|
| `व्याकरण.समास(पद)` | राजपुरुषः → tatpuruṣa analysis |
| `व्याकरण.विग्रह(पद)` | → राज्ञः पुरुषः |
| `व्याकरण.समासप्रकार(पद)` | → tatpuruṣa |

CLI: `समास राजपुरुषः`, `विग्रह नीलोत्पलम्`, `समासप्रकार ग्रामगतः`.

## Kāraka

`peacock/vyakarana/karaka.py` — 6 kārakas + adhikaraṇa/sambandha; `kartā/karman/karaṇa/sampradāna/apādāna/adhikaraṇa` with sūtra refs (`1.4.54`, `1.4.49` etc.), sentence-level tagging.

| Native | Example |
|---|---|
| `व्याकरण.कारक(वाक्य)` | रामः ग्रामं गच्छति → रामः कर्ता, ग्रामं कर्म |
| `व्याकरण.कारकविवरण(कारक)` | कर्ता → 1.4.54 स्वतंत्रः कर्ता |
| `व्याकरण.कारकसूची()` | list all kārakas |

CLI: `कारक "रामः ग्रामं गच्छति"`, `कारकविवरण कर्ता`.

## Vyutpatti & prakṛti-pratyaya

`peacock/vyakarana/derivation.py` — traces `prakṛti + pratyaya → siddha`, it-saṃjñā, anubandha-lopa, siddha validation.

| Native | Example |
|---|---|
| `व्याकरण.व्युत्पत्ति(शब्द)` | रामः → राम + सुँ → रु → विसर्ग steps |
| `व्याकरण.प्रकृतिविभाग(शब्द)` | → राम + सुँ |

CLI: `व्युत्पत्ति रामः`, `प्रकृतिविभाग पठति`.

## Validation

`peacock/vyakarana/validator.py` — `validate_word`/`validate_sentence` with completeness score, rule citations.

| Native | Example |
|---|---|
| `व्याकरण.शब्दसाधुत्व(शब्द)` | रामः → साधु 1.0 |
| `व्याकरण.वाक्यसाधुत्व(वाक्य)` | full sentence report |

CLI: `शब्दसाधुत्व रामः`, `वाक्यसाधुत्व "रामः पठति"`.

## Pratyāhāra

`व्याकरण.प्रत्याहार(नाम)` algorithmically from Māheśvara sūtras.

Examples:

| Input | Result |
|---|---|
| `अच्` | अ इ उ ऋ ऌ ए ओ ऐ औ |
| `इक्` | इ उ ऋ ऌ |
| `हल्` | 33 consonants |
| `अल्` | 42 sounds |

## CLI reference

```bash
./bin/peacock व्याकरण सूत्र 1.1.1
./bin/peacock व्याकरण अन्वेषय गुण --अवधि 5
./bin/peacock व्याकरण प्रत्याहार अच्
./bin/peacock व्याकरण संधि राम इन्द्रः
./bin/peacock व्याकरण संधिविच्छेद रामालयः
./bin/peacock व्याकरण विभक्तिरूप राम प्रथमा एकवचनम्
./bin/peacock व्याकरण धातुरूप भू लट् प्रथम एकवचनम्
./bin/peacock व्याकरण समास राजपुत्रः
./bin/peacock व्याकरण कारक "रामः ग्रामं गच्छति"
./bin/peacock व्याकरण व्युत्पत्ति रामः
./bin/peacock व्याकरण शब्दसाधुत्व रामः
./bin/peacock व्याकरण सूत्रविवरण 6.1.101
./bin/peacock व्याकरण नियमप्रयोग "राम+इन्द्रः" "6.1.87,6.1.101"
./bin/peacock व्याकरण साहित्य
./bin/peacock व्याकरण आच्छादन
```

`examples/vyakarana.सूत्र` exercises all paths through bytecode.

## Literature vs executable coverage

Literature catalogue (Kāśikā, Mahābhāṣya, Siddhānta-kaumudī, Paribhāṣenduśekhara, Vākyapadīya, Dhātu/Gaṇa/Uṇādi/Liṅgānuśāsana/Śikṣā/Tarkasaṅgraha) links upstream — **catalogue only**, not vendored.

**Executable**: all 3,983 sūtra texts present; 16 sandhi rules + 10 paribhāṣā/varṇa transforms executable (26 `executable_transformations`); śabda/dhātu/samāsa/kāraka/derivation/validator fully executable with derivation tracing and validation. Remaining sūtras are texts with structured metadata (kind/adhikāra/anuvṛtti/domain).

## Zero-budget, offline

`./bin/peacock compile`, `peacock test`, `peacock verify` need only the standard library + vendored JSON. No PaaS keys.
