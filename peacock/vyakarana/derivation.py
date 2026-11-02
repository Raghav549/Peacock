"""Vyutpatti-krama: derivation tracking (prakriyā) with sūtra citations.

Provides stepwise derivation from prakṛti (prātipadika/dhātu) + pratyaya to
surface form, showing each Pāṇinian operation.

Example: राम + सुँ (prathamā ekavacana) → रामः
  1. प्रातिपदिकम् 1.2.45 अर्थवदधातुरप्रत्ययः
  2. स्वौजस् 4.1.2 prathamā sup
  3. ससजुषो रुः 8.2.66 s → ru
  4. खरवसानयोः 8.3.15 ru → visarga

Offline, deterministic.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from .corpus import get_sutra
from .sutra_engine import get_engine, Derivation, DerivationStep

@dataclass
class VyutpattiStep:
    kramah: int
    avastha: str
    sutra_id: str
    sutra_text: str
    prakriya: str
    vritti: str = ""

@dataclass
class Vyutpatti:
    shabda: str
    prakriti: str
    pratyaya: str
    steps: list[VyutpattiStep] = field(default_factory=list)
    siddha_rupa: str = ""
    it_samjna: list[str] = field(default_factory=list)

    def trace(self) -> str:
        lines = [f"प्रकृतिः: {self.prakriti} + प्रत्ययः: {self.pratyaya} → {self.shabda}"]
        for s in self.steps:
            lines.append(f"{s.kramah}. [{s.sutra_id}] {s.sutra_text} : {s.avastha} → {s.prakriya} — {s.vritti}")
        lines.append(f"सिद्धरूपम्: {self.siddha_rupa}")
        if self.it_samjna:
            lines.append(f"इत्संज्ञा: {', '.join(self.it_samjna)}")
        return "\n".join(lines)

# Hand-crafted derivations for major forms
DERIVATIONS = {
    # Nominal
    "रामः": {
        "prakriti": "राम", "pratyaya": "सुँ (प्रथमा एकवचन)",
        "steps": [
            ("राम + सुँ", "1.2.45", "अर्थवदधातुरप्रत्ययः प्रातिपदिकम्", "राम इति प्रातिपदिकसंज्ञा", "संज्ञा"),
            ("राम + स्", "4.1.2", "स्वौजसमौट्छष्टा", "सुँ → स् (सुँ-प्रत्ययः, अनुबन्धलोपः 1.3.2)", "प्रत्यय-आदेश"),
            ("राम + स्", "1.4.14", "सुप्तिङन्तं पदम्", "सुप्प्रत्ययान्तं पदसंज्ञम्", "संज्ञा"),
            ("राम + स्", "8.2.66", "ससजुषो रुः", "पदान्त-स् → रु (रुँ)", "आदेश"),
            ("रामरुँ", "8.3.15", "खरवसानयोर्विसर्जनीयः", "रुँ → विसर्ग (ः)", "आदेश"),
            ("रामः", "-", "सिद्धम्", "रामः इति सिद्धम्", "सिद्धिः"),
        ],
        "siddha": "रामः",
        "it": ["सुँ → उ इत् (1.3.2 उपदेशेऽजनुनासिक इत्)", "स् → सकारः शेषः"],
    },
    "रामेण": {
        "prakriti": "राम", "pratyaya": "टा (तृतीया एकवचन)",
        "steps": [
            ("राम + टा", "4.1.2", "स्वौजसमौट्", "टाप्रत्ययः", "प्रत्यय"),
            ("राम + टा", "1.3.7", "चुटू", "टकारः इत्", "इत्संज्ञा"),
            ("राम + आ", "1.3.9", "तस्य लोपः", "इत्-लोपः → आ शेषः", "लोप"),
            ("राम + आ → रामे", "7.3.120", "आङि चापः", "आ → ए? राम + आ → रामेण (णत्वं च)", "आदेश + णत्व"),
            ("रामेण", "-", "सिद्धम्", "रामेण इति", "सिद्धिः"),
        ],
        "siddha": "रामेण",
    },
    "गच्छति": {
        "prakriti": "गम्", "pratyaya": "तिप् (लट् प्रथम एक)",
        "steps": [
            ("गम् + तिप्", "1.3.1", "भूवादयो धातवः", "गम् इति धातुसंज्ञा", "संज्ञा"),
            ("गम् + तिप्", "3.1.68", "कर्तरि शप्", "शप् विकरणः (अ)", "विकरण"),
            ("गम् + शप् + ति", "7.3.77", "इषुगमियमां छः", "गम् → गच्छ (छ आदेशः)", "आदेश"),
            ("गच्छ + अ + ति", "1.3.3", "हलन्त्यम्", "प् इत्, लोपः", "इत्संज्ञा"),
            ("गच्छति", "-", "सिद्धम्", "गच्छति", "सिद्धिः"),
        ],
        "siddha": "गच्छति",
    },
    "भवति": {
        "prakriti": "भू", "pratyaya": "तिप्",
        "steps": [
            ("भू + तिप्", "1.3.1", "भूवादयो धातवः", "धातुसंज्ञा", ""),
            ("भू + शप् + ति", "3.1.68", "कर्तरि शप्", "शप् (अ)", ""),
            ("भो + अ + ति", "7.3.84", "सार्वधातुकार्धधातुकयोः", "गुणः भू → भो", "गुण"),
            ("भव् + अ + ति", "6.1.78", "एचोऽयवायावः", "ओ → अव् (भो + अ → भव)", "संधि"),
            ("भवति", "-", "सिद्धम्", "", ""),
        ],
        "siddha": "भवति",
    },
    "महापुरुषः": {
        "prakriti": "महान् + पुरुष", "pratyaya": "समासः",
        "steps": [
            ("महान् + पुरुषः", "2.1.57", "विशेषणं विशेष्येण बहुलम्", "कर्मधारयः (महान् विशेषणम्)", "समास"),
            ("महा + पुरुषः", "6.3.46", "आन्महतः समानाधिकरणजातीययोः", "महान् → महा", "आदेश"),
            ("महापुरुषः", "-", "सिद्धम्", "", ""),
        ],
        "siddha": "महापुरुषः",
    },
    "राजपुरुषः": {
        "prakriti": "राजन् + पुरुष", "pratyaya": "षष्ठी तत्पुरुषः",
        "steps": [
            ("राज्ञः पुरुषः", "2.2.8", "षष्ठी", "षष्ठी-तत्पुरुषः", "समास"),
            ("राज + पुरुष", "6.1.68", "हल्ङ्याब्भ्यो दीर्घात् सुतिस्यपृक्तं हल् (लोप?)", "सुप्-लुक्", "लुक्"),
            ("राजपुरुषः", "-", "सिद्धम्", "", ""),
        ],
        "siddha": "राजपुरुषः",
    },

    "रामस्य": {
        "prakriti": "राम", "pratyaya": "ङस् (षष्ठी एकवचन)",
        "steps": [
            ("राम + ङस्", "4.1.2", "स्वौजस्", "ङस् प्रत्ययः", "प्रत्यय"),
            ("राम + अस्", "1.3.7", "चुटू", "ङकारः इत्, लोपः", "इत्संज्ञा"),
            ("राम + अस् → रामस्य", "7.1.12", "टाङसिङसामिनात्स्याः", "अस् → स्य आदेशः", "आदेश"),
            ("रामस्य", "-", "सिद्धम्", "रामस्य", "सिद्धिः"),
        ],
        "siddha": "रामस्य",
    },
    "गच्छन्ति": {
        "prakriti": "गम्", "pratyaya": "झि (लट् प्रथम बहु)",
        "steps": [
            ("गम् + झि", "3.1.68", "कर्तरि शप्", "शप् विकरणः", "विकरण"),
            ("गम् + शप् + अन्ति", "7.3.77", "इषुगमियमां छः", "गम् → गच्छ", "आदेश"),
            ("गच्छन्ति", "-", "सिद्धम्", "गच्छन्ति", "सिद्धिः"),
        ],
        "siddha": "गच्छन्ति",
    },
    "विद्यालयः": {
        "prakriti": "विद्या + आलय", "pratyaya": "तत्पुरुष समास",
        "steps": [
            ("विद्यायाः आलयः", "2.1.22", "तत्पुरुषः", "षष्ठी तत्पुरुषः", "समास"),
            ("विद्या + आलयः → विद्यालयः", "6.1.101", "अकः सवर्णे दीर्घः", "आ + आ → आ", "संधि"),
            ("विद्यालयः", "-", "सिद्धम्", "विद्यालयः", "सिद्धिः"),
        ],
        "siddha": "विद्यालयः",
    },
    "नीलकमलम्": {
        "prakriti": "नील + कमल", "pratyaya": "कर्मधारयः",
        "steps": [
            ("नीलम् कमलम्", "2.1.57", "विशेषणं विशेष्येण", "कर्मधारयः", ""),
            ("नीलकमलम्", "-", "सिद्धम्", "", ""),
        ],
        "siddha": "नीलकमलम्",
    },
}

def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()

def vyutpatti(shabda: str) -> Vyutpatti:
    shabda = _norm(shabda)
    if not shabda:
        raise ValueError("शब्दः आवश्यकः")
    if shabda not in DERIVATIONS:
        # Generic fallback: try to infer from known paradigms
        # For unknown, provide template with note
        from .shabda import guess_pratipadika
        from .dhatu import tinanta_analyze
        guesses = guess_pratipadika(shabda)
        if guesses:
            g = guesses[0]
            return Vyutpatti(
                shabda=shabda,
                prakriti=g["pratipadika"],
                pratyaya=f"{g['vibhakti']} {g['vachana']} ({g['sutra']})",
                steps=[
                    VyutpattiStep(1, shabda, g["pratipadika"], shabda, f"{g['pratipadika']} + सुप्", "अनुमानितम्"),
                ],
                siddha_rupa=shabda,
            )
        t_guesses = tinanta_analyze(shabda)
        if t_guesses:
            g = t_guesses[0]
            return Vyutpatti(
                shabda=shabda,
                prakriti=g["dhatu"],
                pratyaya=f"{g['lakara']} {g['purusha']} {g['vachana']}",
                steps=[
                    VyutpattiStep(1, shabda, g["dhatu"], shabda, g["sutra"], "अनुमानितम्"),
                ],
                siddha_rupa=shabda,
            )
        # Completely unknown
        return Vyutpatti(
            shabda=shabda,
            prakriti="अज्ञाता",
            pratyaya="अज्ञातः",
            steps=[
                VyutpattiStep(1, shabda, "-", shabda, "शब्दः कोशे नास्ति — प्रसङ्गं पश्य", "अनिर्धारितम्"),
            ],
            siddha_rupa=shabda,
        )
    info = DERIVATIONS[shabda]
    steps = []
    for idx, (avastha, sid, stext, prakriya, vritti) in enumerate(info["steps"], start=1):
        # Try to fetch real sutra text if possible
        try:
            sutra_obj = get_sutra(sid) if sid != "-" else None
            text = sutra_obj.text if sutra_obj else stext
        except Exception:
            text = stext
        steps.append(VyutpattiStep(idx, avastha, sid, text, prakriya, vritti))
    return Vyutpatti(
        shabda=shabda,
        prakriti=info["prakriti"],
        pratyaya=info["pratyaya"],
        steps=steps,
        siddha_rupa=info["siddha"],
        it_samjna=info.get("it", []),
    )

def list_derivations() -> list[str]:
    return list(DERIVATIONS.keys())

def prakriti_pratyaya_vibhaga(shabda: str) -> dict:
    v = vyutpatti(shabda)
    return {
        "shabda": v.shabda,
        "prakriti": v.prakriti,
        "pratyaya": v.pratyaya,
        "siddha": v.siddha_rupa,
        "steps": [{"sutra": s.sutra_id, "text": s.sutra_text, "prakriya": s.prakriya} for s in v.steps],
    }
