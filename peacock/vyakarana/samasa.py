"""Samāsa-vigraha: compound analysis per Pāṇinian samāsa prakaraṇa (2.1-2.2).

Implements classification and vigraha for:
 - avyayībhāva (2.1.5-21)
 - tatpuruṣa (2.1.22, 2.2.8 etc., including karmadhāraya, dvigu)
 - bahuvrīhi (2.2.23-24)
 - dvandva (2.2.29)

Each analysis cites sūtra. Offline, deterministic.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

class SamasaError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class SamasaAnalysis:
    samasta_pada: str
    vigraha: str
    samasa_type: str
    sutra: str
    description: str
    members: tuple[str, ...]

SAMASA_TYPES = {
    "अव्ययीभाव": {"sutra": "2.1.5 अव्ययीभावः", "desc": "पूर्वपदार्थप्रधानः, अव्ययपूर्वः"},
    "तत्पुरुष": {"sutra": "2.1.22 तत्पुरुषः", "desc": "उत्तरपदार्थप्रधानः, द्वितीयादि विभक्ति"},
    "कर्मधारय": {"sutra": "1.2.42 तत्पुरुषः समानाधिकरणः कर्मधारयः", "desc": "विशेषण-विशेष्य समासः"},
    "द्विगु": {"sutra": "2.1.52 संख्यापूर्वो द्विगुः", "desc": "संख्यापूर्वकः कर्मधारयः"},
    "बहुव्रीहि": {"sutra": "2.2.23 शेषो बहुव्रीहिः", "desc": "अन्यपदार्थप्रधानः"},
    "द्वन्द्व": {"sutra": "2.2.29 चार्थे द्वन्द्वः", "desc": "उभयपदार्थप्रधानः, च-अर्थे"},
}

# Known compounds with vigraha for deterministic demo
KNOWN_SAMASAS = {
    "राजपुरुषः": {
        "type": "तत्पुरुष", "members": ("राज्ञः", "पुरुषः"), "vigraha": "राज्ञः पुरुषः", "sutra": "2.2.8 षष्ठी (षष्ठीतत्पुरुषः)",
    },
    "महापुरुषः": {
        "type": "कर्मधारय", "members": ("महान्", "पुरुषः"), "vigraha": "महान् चासौ पुरुषः", "sutra": "2.1.57 विशेषणं विशेष्येण बहुलम्",
    },
    "नीलकमलम्": {
        "type": "कर्मधारय", "members": ("नीलम्", "कमलम्"), "vigraha": "नीलं कमलम्", "sutra": "2.1.57 विशेषणं विशेष्येण",
    },
    "पञ्चपात्रम्": {
        "type": "द्विगु", "members": ("पञ्च", "पात्राणि"), "vigraha": "पञ्चानां पात्राणां समाहारः", "sutra": "2.1.52 संख्यापूर्वो द्विगुः",
    },
    "पीताम्बरः": {
        "type": "बहुव्रीहि", "members": ("पीतम्", "अम्बरम्"), "vigraha": "पीतम् अम्बरं यस्य सः", "sutra": "2.2.24 अनेकमन्यपदार्थे",
    },
    "चक्रपाणिः": {
        "type": "बहुव्रीहि", "members": ("चक्रम्", "पाणौ"), "vigraha": "चक्रं पाणौ यस्य सः", "sutra": "2.2.24 अनेकमन्यपदार्थे",
    },
    "रामकृष्णौ": {
        "type": "द्वन्द्व", "members": ("रामः", "कृष्णः"), "vigraha": "रामश्च कृष्णश्च", "sutra": "2.2.29 चार्थे द्वन्द्वः",
    },
    "मातापितरौ": {
        "type": "द्वन्द्व", "members": ("माता", "पिता"), "vigraha": "माता च पिता च", "sutra": "2.2.29 चार्थे द्वन्द्वः",
    },
    "उपराजम्": {
        "type": "अव्ययीभाव", "members": ("उप", "राज्ञः"), "vigraha": "राज्ञः समीपम्", "sutra": "2.1.6 अव्ययं विभक्ति-समीप",
    },
    "यथाशक्ति": {
        "type": "अव्ययीभाव", "members": ("यथा", "शक्तिम्"), "vigraha": "शक्तिम् अनतिक्रम्य", "sutra": "2.1.7 यथासादृश्ये",
    },
    "त्रिभुवनम्": {
        "type": "द्विगु", "members": ("त्रि", "भुवनानि"), "vigraha": "त्रयाणां भुवनानां समाहारः", "sutra": "2.1.52 संख्यापूर्वो द्विगुः",
    },

    "चतुर्भुजः": {
        "type": "बहुव्रीहि", "members": ("चतस्रः", "भुजाः"), "vigraha": "चतस्रो भुजाः यस्य सः", "sutra": "2.2.24 अनेकमन्यपदार्थे",
    },
    "धर्मक्षेत्रम्": {
        "type": "तत्पुरुष", "members": ("धर्मस्य", "क्षेत्रम्"), "vigraha": "धर्मस्य क्षेत्रम्", "sutra": "2.2.8 षष्ठीतत्पुरुषः",
    },
    "विद्यालयः": {
        "type": "तत्पुरुष", "members": ("विद्यायाः", "आलयः"), "vigraha": "विद्यायाः आलयः", "sutra": "2.1.22 तत्पुरुषः (4.3.??)",
    },
    "गिरिराजः": {
        "type": "तत्पुरुष", "members": ("गिरीणाम्", "राजा"), "vigraha": "गिरीणां राजा", "sutra": "2.2.8 षष्ठीतत्पुरुषः (गिरां राजा)",
    },
    "अष्टाध्यायी": {
        "type": "द्विगु", "members": ("अष्ट", "अध्यायाः"), "vigraha": "अष्टानाम् अध्यायानां समाहारः", "sutra": "2.1.52 संख्यापूर्वो द्विगुः",
    },
    "महात्मा": {
        "type": "कर्मधारय", "members": ("महान्", "आत्मा"), "vigraha": "महान् आत्मा", "sutra": "2.1.61 सन्महत्परमोत्तम",
    },
}

def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()

def analyze(samasta_pada: str) -> SamasaAnalysis:
    samasta_pada = normalize(samasta_pada)
    if not samasta_pada:
        raise SamasaError("समस्तपदं आवश्यकम्")
    if samasta_pada in KNOWN_SAMASAS:
        info = KNOWN_SAMASAS[samasta_pada]
        tinfo = SAMASA_TYPES.get(info["type"], {"sutra": info["sutra"], "desc": ""})
        return SamasaAnalysis(
            samasta_pada=samasta_pada,
            vigraha=info["vigraha"],
            samasa_type=info["type"],
            sutra=info["sutra"],
            description=tinfo["desc"],
            members=tuple(info["members"]),
        )
    # Heuristic fallback: try to guess by endings
    # If ends with समाहार-like or number prefix -> dvigu
    # If contains both members with च -> dvandva? Not in single word though
    # For unknown, we provide classification based on simple rules and mark as अनुमान
    guess = "तत्पुरुष"
    if samasta_pada.startswith(("त्रि", "चतुर्", "पञ्च", "द्वि", "सप्त")):
        guess = "द्विगु"
    elif samasta_pada.endswith(("म्", "ः")) and " " not in samasta_pada:
        guess = "तत्पुरुष"
    tinfo = SAMASA_TYPES[guess]
    return SamasaAnalysis(
        samasta_pada=samasta_pada,
        vigraha=f"{samasta_pada} इति (विग्रहः अनिश्चितः — प्रसङ्गं पश्य)",
        samasa_type=guess,
        sutra=tinfo["sutra"],
        description=tinfo["desc"] + " (अनुमानितम्)",
        members=(samasta_pada,),
    )

def vigraha(samasta_pada: str) -> str:
    return analyze(samasta_pada).vigraha

def samasa_type(samasta_pada: str) -> str:
    return analyze(samasta_pada).samasa_type

def generate(members: list[str], samasa_type_name: str) -> str:
    """Generate samasta pada from members (simplified)."""
    members = [normalize(m) for m in members]
    samasa_type_name = normalize(samasa_type_name)
    if samasa_type_name not in SAMASA_TYPES:
        raise SamasaError(f"अज्ञातः समासप्रकारः '{samasa_type_name}'")
    # For known, reverse lookup
    for pada, info in KNOWN_SAMASAS.items():
        if list(info["members"]) == members and info["type"] == samasa_type_name:
            return pada
    # Simplified generation: concatenate and apply tatpurusha sandhi
    # For demo, just join without sandhi
    return "".join(members)

def list_types() -> list[dict]:
    return [{"name": k, "sutra": v["sutra"], "desc": v["desc"]} for k, v in SAMASA_TYPES.items()]

def list_examples() -> list[dict]:
    return [{"pada": k, **v} for k, v in KNOWN_SAMASAS.items()]
