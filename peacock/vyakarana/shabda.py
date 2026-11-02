"""Śabda-rūpa: nominal declension (subanta) per Pāṇinian sup-pratyaya.

Implements vibhakti tables for major prātipadika classes:
 - a-kārānta puṃ (राम)
 - ā-kārānta strī (रमा)
 - i-kārānta strī (नदी) and puṃ (हरि)
 - u-kārānta puṃ (गुरु)
 - n-kārānta etc. (simplified)
 - asarvanāmasthāna stems
 - pronoun sarva etc.

Supports 8 vibhakti (including sambodhana as variant of prathamā),
3 vacana (ekavacana, dvivacana, bahuvacana), 3 liṅga.

Each form is tagged with sūtra for sup-ādeśa (e.g., 7.1.12 टाङ्सिङसामिनात्स्याः etc. simplified).

Offline, deterministic, no ML.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .corpus import get_sutra

# Vibhakti names in Sanskrit order
VIBHAKTIS = [
    "प्रथमा",      # nominative
    "द्वितीया",     # accusative
    "तृतीया",     # instrumental
    "चतुर्थी",    # dative
    "पञ्चमी",     # ablative
    "षष्ठी",      # genitive
    "सप्तमी",     # locative
    "संबोधन",     # vocative
]

VACHANAS = ["एकवचनम्", "द्विवचनम्", "बहुवचनम्"]
LINGAS = ["पुंल्लिङ्गम्", "स्त्रीलिङ्गम्", "नपुंसकलिङ्गम्"]

# Normalized keys for API
VIBHAKTI_KEYS = {
    "प्रथमा": 0, "प्रथम": 0, "1": 0,
    "द्वितीया": 1, "द्वितीय": 1, "2": 1,
    "तृतीया": 2, "तृतीय": 2, "3": 2,
    "चतुर्थी": 3, "चतुर्थ": 3, "4": 3,
    "पञ्चमी": 4, "पञ्चम": 4, "5": 4,
    "षष्ठी": 5, "षष्ठ": 5, "6": 5,
    "सप्तमी": 6, "सप्तम": 6, "7": 6,
    "संबोधन": 7, "सम्बोधन": 7, "8": 7,
}

VACHANA_KEYS = {
    "एक": 0, "एकवचन": 0, "एकवचनम्": 0, "singular": 0, "1": 0,
    "द्वि": 1, "द्विवचन": 1, "द्विवचनम्": 1, "dual": 1, "2": 1,
    "बहु": 2, "बहुवचन": 2, "बहुवचनम्": 2, "plural": 2, "3": 2,
}

LINGA_KEYS = {
    "पुं": 0, "पुंल्लिङ्ग": 0, "पुंल्लिङ्गम्": 0, "masculine": 0, "m": 0,
    "स्त्री": 1, "स्त्रीलिङ्ग": 1, "स्त्रीलिङ्गम्": 1, "feminine": 1, "f": 1,
    "नपुं": 2, "नपुंसक": 2, "नपुंसकलिङ्ग": 2, "नपुंसकलिङ्गम्": 2, "neuter": 2, "n": 2,
}

class ShabdaError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class PadaForm:
    pratipadika: str
    vibhakti: str
    vachana: str
    linga: str
    rupa: str
    sutra: str

# Paradigms data: 8 vibhaktis x 3 vachanas = 24 forms per paradigm
# We store as list of lists: vibhakti_index -> [ek, dvi, bahu]

# अकारान्त पुंल्लिङ्ग: राम
RAMA_PARADIGM = [
    ["रामः", "रामौ", "रामाः"],      # प्रथमा
    ["रामम्", "रामौ", "रामान्"],     # द्वितीया
    ["रामेण", "रामाभ्याम्", "रामैः"], # तृतीया
    ["रामाय", "रामाभ्याम्", "रामेभ्यः"], # चतुर्थी
    ["रामात्", "रामाभ्याम्", "रामेभ्यः"], # पञ्चमी
    ["रामस्य", "रामयोः", "रामाणाम्"], # षष्ठी
    ["रामे", "रामयोः", "रामेषु"],     # सप्तमी
    ["हे राम", "हे रामौ", "हे रामाः"], # संबोधन (हें added)
]

# आकारान्त स्त्रीलिङ्ग: रमा
RAMA_STR_PARADIGM = [
    ["रमा", "रमे", "रमाः"],
    ["रमाम्", "रमे", "रमाः"],
    ["रमया", "रमाभ्याम्", "रमाभिः"],
    ["रमायै", "रमाभ्याम्", "रमाभ्यः"],
    ["रमायाः", "रमाभ्याम्", "रमाभ्यः"],
    ["रमायाः", "रमयोः", "रमाणाम्"],
    ["रमायाम्", "रमयोः", "रमासु"],
    ["हे रमे", "हे रमे", "हे रमाः"],
]

# इकारान्त स्त्री (नदी - नदीशब्द नद्यादि)
NADI_PARADIGM = [
    ["नदी", "नद्यौ", "नद्यः"],
    ["नदीम्", "नद्यौ", "नदीः"],
    ["नद्या", "नदीभ्याम्", "नदीभिः"],
    ["नद्यै", "नदीभ्याम्", "नदीभ्यः"],
    ["नद्याः", "नदीभ्याम्", "नदीभ्यः"],
    ["नद्याः", "नद्योः", "नदीनाम्"],
    ["नद्याम्", "नद्योः", "नदीषु"],
    ["हे नदि", "हे नद्यौ", "हे नद्यः"],
]

# हरि (इकारान्त पुं)
HARI_PARADIGM = [
    ["हरिः", "हरी", "हरयः"],
    ["हरिम्", "हरी", "हरीन्"],
    ["हरिणा", "हरिभ्याम्", "हरिभिः"],
    ["हरये", "हरिभ्याम्", "हरिभ्यः"],
    ["हरेः", "हरिभ्याम्", "हरिभ्यः"],
    ["हरेः", "हर्योः", "हरीणाम्"],
    ["हरौ", "हर्योः", "हरिषु"],
    ["हे हरे", "हे हरी", "हे हरयः"],
]

# गुरु (उकारान्त पुं)
GURU_PARADIGM = [
    ["गुरुः", "गुरू", "गुरवः"],
    ["गुरुम्", "गुरू", "गुरून्"],
    ["गुरुणा", "गुरुभ्याम्", "गुरुभिः"],
    ["गुरवे", "गुरुभ्याम्", "गुरुभ्यः"],
    ["गुरोः", "गुरुभ्याम्", "गुरुभ्यः"],
    ["गुरोः", "गुर्वोः", "गुरूणाम्"],
    ["गुरौ", "गुर्वोः", "गुरुषु"],
    ["हे गुरो", "हे गुरू", "हे गुरवः"],
]

# फल (अकारान्त नपुंसक)
PHALA_PARADIGM = [
    ["फलम्", "फले", "फलानि"],
    ["फलम्", "फले", "फलानि"],
    ["फलेन", "फलाभ्याम्", "फलैः"],
    ["फलाय", "फलाभ्याम्", "फलेभ्यः"],
    ["फलात्", "फलाभ्याम्", "फलेभ्यः"],
    ["फलस्य", "फलयोः", "फलानाम्"],
    ["फले", "फलयोः", "फलेषु"],
    ["हे फल", "हे फले", "हे फलानि"],
]

# सर्वनाम: सर्व (सर्वादीनि सर्वनामानि 1.1.27) has special जस् etc
SARVA_PARADIGM = [
    ["सर्वः", "सर्वौ", "सर्वे"],
    ["सर्वम्", "सर्वौ", "सर्वान्"],
    ["सर्वेण", "सर्वाभ्याम्", "सर्वैः"],
    ["सर्वस्मै", "सर्वाभ्याम्", "सर्वेभ्यः"],
    ["सर्वस्मात्", "सर्वाभ्याम्", "सर्वेभ्यः"],
    ["सर्वस्य", "सर्वयोः", "सर्वेषाम्"],
    ["सर्वस्मिन्", "सर्वयोः", "सर्वेषु"],
    ["हे सर्व", "हे सर्वौ", "हे सर्वे"],
]

# अस्मद् (उत्तम पुरुष सर्वनाम)
ASMAD_PARADIGM = [
    ["अहम्", "आवाम्", "वयम्"],
    ["माम्", "आवाम्", "अस्मान्"],
    ["मया", "आवाभ्याम्", "अस्माभिः"],
    ["मह्यम्", "आवाभ्याम्", "अस्मभ्यम्"],
    ["मत्", "आवाभ्याम्", "अस्मत्"],
    ["मम", "आवयोः", "अस्माकम्"],
    ["मयि", "आवयोः", "अस्मासु"],
    ["", "", ""],  # no sambodhana for asmad
]

# युष्मद्
YUSHMAD_PARADIGM = [
    ["त्वम्", "युवाम्", "यूयम्"],
    ["त्वाम्", "युवाम्", "युष्मान्"],
    ["त्वया", "युवाभ्याम्", "युष्माभिः"],
    ["तुभ्यम्", "युवाभ्याम्", "युष्मभ्यम्"],
    ["त्वत्", "युवाभ्याम्", "युष्मत्"],
    ["तव", "युवयोः", "युष्माकम्"],
    ["त्वयि", "युवयोः", "युष्मासु"],
    ["", "", ""],
]


# राजन् (नकारान्त पुं) — n-stem, राजा etc.
RAJAN_PARADIGM = [
    ["राजा", "राजानौ", "राजानः"],
    ["राजानम्", "राजानौ", "राज्ञः"],
    ["राज्ञा", "राजभ्याम्", "राजभिः"],
    ["राज्ञे", "राजभ्याम्", "राजभ्यः"],
    ["राज्ञः", "राजभ्याम्", "राजभ्यः"],
    ["राज्ञः", "राज्ञोः", "राज्ञाम्"],
    ["राज्ञि", "राज्ञोः", "राजसु"],
    ["हे राजन्", "हे राजानौ", "हे राजानः"],
]

# पितृ (ऋकारान्त पुं) — pitṛ stem
PITRI_PARADIGM = [
    ["पिता", "पितरौ", "पितरः"],
    ["पितरम्", "पितरौ", "पितॄन्"],
    ["पित्रा", "पितृभ्याम्", "पितृभिः"],
    ["पित्रे", "पितृभ्याम्", "पितृभ्यः"],
    ["पितुः", "पितृभ्याम्", "पितृभ्यः"],
    ["पितुः", "पित्रोः", "पितॄणाम्"],
    ["पितरि", "पित्रोः", "पितृषु"],
    ["हे पितः", "हे पितरौ", "हे पितरः"],
]

# वाच् (चकारान्त स्त्री) — consonant stem
VAC_PARADIGM = [
    ["वाक्", "वाचौ", "वाचः"],
    ["वाचम्", "वाचौ", "वाचः"],
    ["वाचा", "वाग्भ्याम्", "वाग्भिः"],
    ["वाचे", "वाग्भ्याम्", "वाग्भ्यः"],
    ["वाचः", "वाग्भ्याम्", "वाग्भ्यः"],
    ["वाचः", "वाचोः", "वाचाम्"],
    ["वाचि", "वाचोः", "वाक्षु"],
    ["हे वाक्", "हे वाचौ", "हे वाचः"],
]

PARADIGMS = {
    "राम": (RAMA_PARADIGM, "पुंल्लिङ्गम्", "अकारान्तः"),
    "रमा": (RAMA_STR_PARADIGM, "स्त्रीलिङ्गम्", "आकारान्तः"),
    "हरि": (HARI_PARADIGM, "पुंल्लिङ्गम्", "इकारान्तः"),
    "नदी": (NADI_PARADIGM, "स्त्रीलिङ्गम्", "ईकारान्तः"),
    "गुरु": (GURU_PARADIGM, "पुंल्लिङ्गम्", "उकारान्तः"),
    "फल": (PHALA_PARADIGM, "नपुंसकलिङ्गम्", "अकारान्तः"),
    "सर्व": (SARVA_PARADIGM, "पुंल्लिङ्गम्", "सर्वनाम"),
    "अस्मद्": (ASMAD_PARADIGM, "त्रिलिङ्गम्", "सर्वनाम"),
    "युष्मद्": (YUSHMAD_PARADIGM, "त्रिलिङ्गम्", "सर्वनाम"),
    "राजन्": (RAJAN_PARADIGM, "पुंल्लिङ्गम्", "नकारान्तः"),
    "पितृ": (PITRI_PARADIGM, "पुंल्लिङ्गम्", "ऋकारान्तः"),
    "वाच्": (VAC_PARADIGM, "स्त्रीलिङ्गम्", "चकारान्तः"),
}

# Sūtra citations for sup-pratyayas (simplified mapping)
SUP_SUTRAS = {
    0: "4.1.2 स्वौजसमौट्छष्टाभ्याम्भिस्ङेभ्याम्भ्यस्ङसिभ्याम्भ्यस्ङसोसाम्ङ्योस्सुप्",
    1: "2.3.2 कर्मणि द्वितीया",
    2: "2.3.18 कर्तृकरणयोस्तृतीया",
    3: "2.3.13 चतुर्थी सम्प्रदाने",
    4: "2.3.28 अपादाने पञ्चमी",
    5: "2.3.50 षष्ठी शेषे",
    6: "2.3.36 सप्तम्यधिकरणे च",
    7: "2.3.49 सम्बोधने च",
}

def normalize_pratipadika(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()

def vibhakti_rupa(pratipadika: str, vibhakti: str, vachana: str, linga: str | None = None) -> PadaForm:
    """Return declined form for a known pratipadika.

    vibhakti: 1-8 or Sanskrit name; vachana: 1-3 or name; linga optional validation.
    """
    pratipadika = normalize_pratipadika(pratipadika)
    vibhakti = unicodedata.normalize("NFC", vibhakti).strip()
    vachana = unicodedata.normalize("NFC", vachana).strip()
    # Resolve indices
    vib_key = vibhakti.casefold() if hasattr(vibhakti, 'casefold') else vibhakti.lower()
    # Try direct mapping
    vi = None
    for k, v in VIBHAKTI_KEYS.items():
        if k == vibhakti or k == vib_key:
            vi = v
            break
    if vi is None:
        # Try numeric string
        try:
            num = int(vibhakti)
            vi = num - 1 if 1 <= num <= 8 else None
        except Exception:
            pass
    if vi is None:
        raise ShabdaError(f"अज्ञाता विभक्तिः '{vibhakti}' — प्रयोजय 1-8 वा प्रथमा...संबोधन")
    va = None
    for k, v in VACHANA_KEYS.items():
        if k == vachana or k == vachana.casefold():
            va = v
            break
    if va is None:
        try:
            va = int(vachana) - 1
            if not 0 <= va <= 2:
                va = None
        except Exception:
            pass
    if va is None:
        raise ShabdaError(f"अज्ञातं वचनम् '{vachana}'")

    if pratipadika not in PARADIGMS:
        raise ShabdaError(f"अज्ञातं प्रातिपदिकम् '{pratipadika}' — ज्ञातानि: {', '.join(PARADIGMS.keys())}")

    table, expected_linga, class_name = PARADIGMS[pratipadika]
    # Optional linga check
    if linga:
        linga = unicodedata.normalize("NFC", linga).strip()
        # Not strict, just note
        pass

    rupa = table[vi][va]
    if not rupa:
        raise ShabdaError(f"रूपं नास्ति: {pratipadika} {VIBHAKTIS[vi]} {VACHANAS[va]} (सम्बोधनाभावः)")

    vib_name = VIBHAKTIS[vi]
    vac_name = VACHANAS[va]
    return PadaForm(
        pratipadika=pratipadika,
        vibhakti=vib_name,
        vachana=vac_name,
        linga=expected_linga,
        rupa=rupa,
        sutra=SUP_SUTRAS[vi],
    )

def declension_table(pratipadika: str) -> list[list[str]]:
    """Return full 8x3 table."""
    pratipadika = normalize_pratipadika(pratipadika)
    if pratipadika not in PARADIGMS:
        raise ShabdaError(f"अज्ञातं प्रातिपदिकम् '{pratipadika}'")
    table, linga, cls = PARADIGMS[pratipadika]
    return table

def all_rupas(pratipadika: str) -> list[PadaForm]:
    pratipadika = normalize_pratipadika(pratipadika)
    result = []
    for vi, vib in enumerate(VIBHAKTIS):
        for va, vac in enumerate(VACHANAS):
            try:
                pf = vibhakti_rupa(pratipadika, vib, vac)
                result.append(pf)
            except ShabdaError:
                continue
    return result

def guess_pratipadika(pada: str) -> list[dict]:
    """Given a declined form, guess possible pratipadika+vibhakti+vachana."""
    pada = normalize_pratipadika(pada)
    candidates = []
    for pratipadika, (table, linga, cls) in PARADIGMS.items():
        for vi, row in enumerate(table):
            for va, form in enumerate(row):
                if form and pada == form.replace("हे ", ""):
                    candidates.append({
                        "pratipadika": pratipadika,
                        "vibhakti": VIBHAKTIS[vi],
                        "vachana": VACHANAS[va],
                        "linga": linga,
                        "sutra": SUP_SUTRAS[vi],
                    })
                # Also allow with हे
                if form and pada == form:
                    if not any(c["pratipadika"] == pratipadika and c["vibhakti"] == VIBHAKTIS[vi] and c["vachana"] == VACHANAS[va] for c in candidates):
                        candidates.append({
                            "pratipadika": pratipadika,
                            "vibhakti": VIBHAKTIS[vi],
                            "vachana": VACHANAS[va],
                            "linga": linga,
                            "sutra": SUP_SUTRAS[vi],
                        })
    return candidates
