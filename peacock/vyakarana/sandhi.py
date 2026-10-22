"""Deterministic external vowel sandhi with explicit Pāṇinian rule traces.

This module deliberately accepts a *left/right word pair*, not ambiguous running
prose.  It implements a tested subset of vowel-boundary rules; it does not claim
to segment Sanskrit or to execute the complete Aṣṭādhyāyī.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from .pratyahara import expand


class SandhiError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SandhiResult:
    left: str
    right: str
    text: str
    rule_id: str
    rule_name: str


VOWEL_SIGNS = {
    "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
    "ऋ": "ृ", "ॠ": "ॄ", "ऌ": "ॢ", "ॡ": "ॣ", "ए": "े", "ऐ": "ै",
    "ओ": "ो", "औ": "ौ",
}
SIGN_VOWELS = {sign: vowel for vowel, sign in VOWEL_SIGNS.items() if sign}
CONSONANTS = frozenset(expand("हल्"))
VOWELS = frozenset(VOWEL_SIGNS)


@dataclass(frozen=True, slots=True)
class _FinalVowel:
    vowel: str
    base: str
    implicit: bool


def _final_vowel(word: str) -> _FinalVowel | None:
    if not word:
        return None
    last = word[-1]
    if last in VOWELS:
        return _FinalVowel(last, word[:-1], False)
    if last in SIGN_VOWELS:
        return _FinalVowel(SIGN_VOWELS[last], word[:-1], False)
    # A non-virāma-final consonant carries the implicit vowel अ.  Keeping the
    # consonant in ``base`` lets a replacement vowel become its mātrā.
    if last in CONSONANTS:
        return _FinalVowel("अ", word, True)
    return None


def _attach_vowel(base: str, vowel: str) -> str:
    if base and base[-1] in CONSONANTS:
        return base + VOWEL_SIGNS[vowel]
    return base + vowel


def _replace_final(final: _FinalVowel, vowel: str) -> str:
    return _attach_vowel(final.base, vowel)


def _join_yana(final: _FinalVowel, substitute: str, right: str, initial: str) -> str:
    # Suppress the preceding consonant's implicit अ before the semivowel, then
    # let that semivowel take the following vowel as its own mātrā.
    base = final.base
    if base and base[-1] in CONSONANTS:
        base += "्"
    return base + substitute + VOWEL_SIGNS[initial] + right[1:]


def join(left: str, right: str) -> SandhiResult:
    left = unicodedata.normalize("NFC", left).strip()
    right = unicodedata.normalize("NFC", right).strip()
    if not left or not right:
        raise SandhiError("sandhi requires two non-empty words")
    final = _final_vowel(left)
    if final is None:
        raise SandhiError("the left word must end in a vowel or an implicit-अ consonant")
    initial = right[0]
    if initial not in VOWELS:
        raise SandhiError("the right word must begin with an independent vowel")
    a, b = final.vowel, initial

    savarna = (
        (("अ", "आ"), ("अ", "आ"), "आ"),
        (("इ", "ई"), ("इ", "ई"), "ई"),
        (("उ", "ऊ"), ("उ", "ऊ"), "ऊ"),
        (("ऋ", "ॠ"), ("ऋ", "ॠ"), "ॠ"),
        (("ऌ", "ॡ"), ("ऌ", "ॡ"), "ॡ"),
    )
    for left_group, right_group, replacement in savarna:
        if a in left_group and b in right_group:
            return SandhiResult(left, right, _replace_final(final, replacement) + right[1:], "6.1.101", "अकः सवर्णे दीर्घः")

    if a in ("अ", "आ"):
        guna = {"इ": "ए", "ई": "ए", "उ": "ओ", "ऊ": "ओ"}
        if b in guna:
            return SandhiResult(left, right, _replace_final(final, guna[b]) + right[1:], "6.1.87", "आद्गुणः")
        if b in ("ऋ", "ॠ", "ऌ", "ॡ"):
            substitute = "र्" if b in ("ऋ", "ॠ") else "ल्"
            text = _replace_final(final, "अ") + substitute + right[1:]
            return SandhiResult(left, right, text, "6.1.87", "आद्गुणः")
        if b in ("ए", "ऐ", "ओ", "औ"):
            replacement = "ऐ" if b in ("ए", "ऐ") else "औ"
            return SandhiResult(left, right, _replace_final(final, replacement) + right[1:], "6.1.88", "वृद्धिरेचि")

    yana = {"इ": "य", "ई": "य", "उ": "व", "ऊ": "व", "ऋ": "र", "ॠ": "र", "ऌ": "ल", "ॡ": "ल"}
    if a in yana:
        return SandhiResult(left, right, _join_yana(final, yana[a], right, b), "6.1.77", "इको यणचि")

    raise SandhiError(f"no implemented vowel-sandhi rule for '{a} + {b}'")


def join_text(left: str, right: str) -> str:
    return join(left, right).text


EXECUTABLE_RULE_IDS = frozenset({"6.1.77", "6.1.87", "6.1.88", "6.1.101"})
