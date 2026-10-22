"""Māheśvara-sūtra pratyāhāra expansion over explicit Devanagari sounds."""

from __future__ import annotations

import unicodedata


class PratyaharaError(ValueError):
    pass


# Each row is (ordinary sounds, final it marker).  The marker is not itself a
# member of the phonetic sequence.  This representation makes expansion a small,
# deterministic algorithm rather than a table of hard-coded pratyāhāra answers.
SHIVA_SUTRAS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("अ", "इ", "उ"), "ण्"),
    (("ऋ", "ऌ"), "क्"),
    (("ए", "ओ"), "ङ्"),
    (("ऐ", "औ"), "च्"),
    (("ह", "य", "व", "र"), "ट्"),
    (("ल",), "ण्"),
    (("ञ", "म", "ङ", "ण", "न"), "म्"),
    (("झ", "भ"), "ञ्"),
    (("घ", "ढ", "ध"), "ष्"),
    (("ज", "ब", "ग", "ड", "द"), "श्"),
    (("ख", "फ", "छ", "ठ", "थ", "च", "ट", "त"), "व्"),
    (("क", "प"), "य्"),
    (("श", "ष", "स"), "र्"),
    (("ह",), "ल्"),
)

MAHESHVARA_TEXT = tuple(" ".join((*sounds, marker)) for sounds, marker in SHIVA_SUTRAS)
_SEQUENCE = tuple(
    (sound, marker if index == len(sounds) - 1 else "")
    for sounds, marker in SHIVA_SUTRAS
    for index, sound in enumerate(sounds)
)
_SOUNDS = frozenset(sound for sound, _ in _SEQUENCE)
_MARKERS = frozenset(marker for _, marker in SHIVA_SUTRAS)


def expand(pratyahara: str) -> tuple[str, ...]:
    """Expand a pratyāhāra such as ``अच्``, ``हल्``, ``यण्`` or ``इक्``.

    The initial sound is included, every following ordinary sound is included,
    and the named final it marker ends the expansion.  Other it markers are
    skipped.  Invalid or reversed ranges are errors, never partial results.
    """

    text = unicodedata.normalize("NFC", pratyahara).replace(" ", "")
    if len(text) < 2:
        raise PratyaharaError("a pratyāhāra needs an initial sound and an it marker")
    start, end = text[0], text[1:]
    if start not in _SOUNDS or end not in _MARKERS:
        raise PratyaharaError(f"'{pratyahara}' is not a valid Māheśvara pratyāhāra")
    result: list[str] = []
    started = False
    for sound, marker in _SEQUENCE:
        if not started:
            if sound != start:
                continue
            started = True
        if sound not in result:
            result.append(sound)
        if marker == end:
            return tuple(result)
    raise PratyaharaError(f"it marker '{end}' does not follow '{start}'")


def is_vowel(sound: str) -> bool:
    return sound in expand("अच्")


def is_consonant(sound: str) -> bool:
    return sound in expand("हल्")
