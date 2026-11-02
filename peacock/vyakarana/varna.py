"""Varna-vijnana: phonological classification per Māheśvara & Pāṇinian śikṣā.

Provides deterministic character classification without ML or external data.
All logic is pure Python / stdlib and offline.
"""

from __future__ import annotations

import unicodedata

from .pratyahara import expand

# Explicit sets derived from expand() to avoid circular import at module load
# but we compute lazily for correctness.

# Vowel signs mapping
VOWEL_SIGNS = {
    "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
    "ऋ": "ृ", "ॠ": "ॄ", "ऌ": "ॢ", "ॡ": "ॣ", "ए": "े", "ऐ": "ै",
    "ओ": "ो", "औ": "ौ",
}
SIGN_VOWELS = {v: k for k, v in VOWEL_SIGNS.items() if v}

# Additional Devanagari marks
VIRAMA = "्"
VISARGA = "ः"
ANUSVARA = "ं"
AVAGRAHA = "ऽ"
ANUNASIKA = "ँ"

# Consonant groups per sthāna/prayatna (traditional)
KANTHYA = frozenset(["क", "ख", "ग", "घ", "ङ", "ह"])  # kaṇṭhya (guttural) approx
TALAVYA = frozenset(["च", "छ", "ज", "झ", "ञ", "य", "श"])
MURDHANYA = frozenset(["ट", "ठ", "ड", "ढ", "ण", "र", "ष"])
DANTYA = frozenset(["त", "थ", "द", "ध", "न", "ल", "स"])
OSHTHYA = frozenset(["प", "फ", "ब", "भ", "म", "व"])

# Voicing / aspiration classification
GHOSHA = frozenset(["ग", "घ", "ङ", "ज", "झ", "ञ", "ड", "ढ", "ण", "द", "ध", "न", "ब", "भ", "म", "य", "र", "ल", "व", "ह"])
AGHOSHA = frozenset(["क", "ख", "च", "छ", "ट", "ठ", "त", "थ", "प", "फ", "श", "ष", "स"])
ALPAPRANA = frozenset(["क", "ग", "ङ", "च", "ज", "ञ", "ट", "ड", "ण", "त", "द", "न", "प", "ब", "म", "य", "र", "ल", "व"])
MAHAPRANA = frozenset(["ख", "घ", "छ", "झ", "ठ", "ढ", "थ", "ध", "फ", "भ", "श", "ष", "स", "ह"])

# Broad categories
def is_vowel(ch: str) -> bool:
    return ch in VOWEL_SIGNS

def is_consonant(ch: str) -> bool:
    # Use pratyahara हल् membership
    try:
        return ch in expand("हल्")
    except Exception:
        return False

def is_vowel_sign(ch: str) -> bool:
    return ch in SIGN_VOWELS

def is_anusvara(ch: str) -> bool:
    return ch == ANUSVARA

def is_visarga(ch: str) -> bool:
    return ch == VISARGA

def is_virama(ch: str) -> bool:
    return ch == VIRAMA

def classify_varna(ch: str) -> str:
    """Return Pāṇinian broad class for a single varna."""
    ch = unicodedata.normalize("NFC", ch)
    if ch in VOWEL_SIGNS:
        return "अच्"
    if ch == VISARGA:
        return "विसर्ग"
    if ch == ANUSVARA:
        return "अनुस्वार"
    if ch in expand("हल्"):
        return "हल्"
    if ch in (VIRAMA, AVAGRAHA):
        return "अयोगवाह"
    return "अज्ञात"

def is_savarna(a: str, b: str) -> bool:
    """savarṇa: same sthāna/prayatna (simplified to vowel length pairs + consonant groups)."""
    savarna_pairs = [
        frozenset(["अ", "आ"]), frozenset(["इ", "ई"]), frozenset(["उ", "ऊ"]),
        frozenset(["ऋ", "ॠ"]), frozenset(["ऌ", "ॡ"]),
        frozenset(["ए", "ऐ"]), frozenset(["ओ", "औ"]),
    ]
    # For vowels, check length pairs
    for pair in savarna_pairs:
        if a in pair and b in pair:
            return True
    # For consonants, savarna means same वर्ग and same voicing class (very simplified)
    # Real definition excludes झल् vs अच् interactions already handled by 1.1.10
    if is_consonant(a) and is_consonant(b):
        # Simplified: same place of articulation
        for group in [KANTHYA, TALAVYA, MURDHANYA, DANTYA, OSHTHYA]:
            if a in group and b in group:
                return True
    return False

def get_pratyahara_members(name: str) -> tuple[str, ...]:
    try:
        return expand(name)
    except Exception:
        return ()

# Helper to extract final vowel info (shared with sandhi)
def final_sound(word: str) -> dict:
    """Analyze final sound of a Devanagari word."""
    word = unicodedata.normalize("NFC", word).strip()
    if not word:
        return {"type": "empty", "value": ""}
    last = word[-1]
    if last in VOWEL_SIGNS:
        return {"type": "vowel", "value": last, "base": word[:-1], "implicit": False}
    if last in SIGN_VOWELS:
        return {"type": "vowel", "value": SIGN_VOWELS[last], "base": word[:-1], "implicit": False}
    if last == VIRAMA:
        # ends in halanta
        return {"type": "halanta", "value": word[-2] if len(word) >= 2 else "", "base": word[:-1], "implicit": False}
    if last == VISARGA:
        return {"type": "visarga", "value": VISARGA, "base": word[:-1], "implicit": False}
    if last == ANUSVARA:
        return {"type": "anusvara", "value": ANUSVARA, "base": word[:-1], "implicit": False}
    # consonant with implicit अ
    try:
        if last in expand("हल्"):
            return {"type": "vowel", "value": "अ", "base": word, "implicit": True}
    except Exception:
        pass
    return {"type": "unknown", "value": last, "base": word, "implicit": False}

def initial_sound(word: str) -> dict:
    word = unicodedata.normalize("NFC", word).strip()
    if not word:
        return {"type": "empty", "value": ""}
    first = word[0]
    if first in VOWEL_SIGNS:
        return {"type": "vowel", "value": first, "rest": word[1:]}
    if first in expand("हल्"):
        return {"type": "consonant", "value": first, "rest": word[1:]}
    if first == AVAGRAHA:
        return {"type": "avagraha", "value": first, "rest": word[1:]}
    return {"type": "unknown", "value": first, "rest": word[1:]}
