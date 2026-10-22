"""Attributed, searchable Aṣṭādhyāyī corpus and inheritance metadata.

The corpus contains all 3,983 sūtra *texts*.  It is not represented as a
complete computational interpretation of Pāṇini.  Executable operations live in
``pratyahara.py`` and ``sandhi.py`` and identify their own tested coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
import json
import unicodedata


EXPECTED_SUTRAS = 3983
KIND_NAMES = {
    "S": "संज्ञा",
    "P": "परिभाषा",
    "AT": "अतिदेशः",
    "AD": "आदेशः",
    "V": "विधिः",
}


class CorpusError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Reference:
    term: str
    sutra_id: str | None

    def display(self) -> str:
        return f"{self.term} [{self.sutra_id}]" if self.sutra_id else self.term


@dataclass(frozen=True, slots=True)
class Sutra:
    id: str
    text: str
    kinds: tuple[str, ...]
    labels: tuple[str, ...]
    anuvritti_raw: str
    adhikara_raw: str

    @property
    def kind_names(self) -> tuple[str, ...]:
        return tuple(KIND_NAMES.get(kind, kind) for kind in self.kinds)

    @property
    def anuvritti(self) -> tuple[Reference, ...]:
        return decode_references(self.anuvritti_raw)

    @property
    def adhikara(self) -> tuple[Reference, ...]:
        return decode_references(self.adhikara_raw)

    def display(self) -> str:
        return f"{self.id} {self.text}"


def _numeric_sutra_id(code: str) -> str | None:
    if len(code) == 5 and code.isdecimal():
        return f"{int(code[0])}.{int(code[1])}.{int(code[2:])}"
    return None


def decode_references(raw: str) -> tuple[Reference, ...]:
    """Decode the source corpus' ``term$11001`` and ``term$1$4$1`` forms."""

    refs: list[Reference] = []
    for entry in filter(None, raw.split("##")):
        parts = entry.split("$")
        if len(parts) == 2:
            refs.append(Reference(parts[0], _numeric_sutra_id(parts[1])))
        elif len(parts) == 4 and all(part.isdecimal() for part in parts[1:]):
            refs.append(Reference(parts[0], ".".join(str(int(part)) for part in parts[1:])))
        else:
            # Preserve unexpected source data instead of silently dropping it.
            refs.append(Reference(parts[0] if parts else entry, None))
    return tuple(refs)


@lru_cache(maxsize=1)
def all_sutras() -> tuple[Sutra, ...]:
    path = resources.files("peacock.vyakarana").joinpath("data/ashtadhyayi.json")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("sutras", [])
    if payload.get("count") != EXPECTED_SUTRAS or len(rows) != EXPECTED_SUTRAS:
        raise CorpusError(f"expected {EXPECTED_SUTRAS} sūtras, found {len(rows)}")
    result = tuple(
        Sutra(
            id=row["id"],
            text=row["text"],
            kinds=tuple(row["kinds"]),
            labels=tuple(row["labels"]),
            anuvritti_raw=row["an"],
            adhikara_raw=row["ad"],
        )
        for row in rows
    )
    ids = [sutra.id for sutra in result]
    if len(set(ids)) != len(ids) or any(not sutra.text for sutra in result):
        raise CorpusError("sūtra corpus has duplicate identifiers or empty text")
    return result


@lru_cache(maxsize=1)
def _index() -> dict[str, Sutra]:
    return {sutra.id: sutra for sutra in all_sutras()}


def get_sutra(sutra_id: str) -> Sutra:
    normalized = unicodedata.normalize("NFC", sutra_id).strip()
    try:
        return _index()[normalized]
    except KeyError as exc:
        raise CorpusError(f"unknown Aṣṭādhyāyī sūtra '{sutra_id}'") from exc


def search(query: str, limit: int = 50) -> list[Sutra]:
    query = unicodedata.normalize("NFC", query).strip().casefold()
    if not query:
        raise CorpusError("sūtra search requires non-empty text")
    if not 1 <= limit <= 200:
        raise CorpusError("sūtra search limit must be between 1 and 200")
    matches = []
    for sutra in all_sutras():
        haystack = " ".join((sutra.id, sutra.text, *sutra.labels, *sutra.kind_names)).casefold()
        if query in haystack:
            matches.append(sutra)
            if len(matches) >= limit:
                break
    return matches


def chapter(adhyaya: int, pada: int) -> tuple[Sutra, ...]:
    if not 1 <= adhyaya <= 8 or not 1 <= pada <= 4:
        raise CorpusError("chapter coordinates must be within 1–8 and 1–4")
    prefix = f"{adhyaya}.{pada}."
    return tuple(sutra for sutra in all_sutras() if sutra.id.startswith(prefix))


@lru_cache(maxsize=1)
def literature() -> tuple[str, ...]:
    """Return the attributed connected-literature catalogue with scope labels."""

    path = resources.files("peacock.vyakarana").joinpath("data/literature.json")
    with path.open("r", encoding="utf-8") as handle:
        rows = json.load(handle)
    return tuple(f"{row['name']} — {row['local']} — {row['path']}" for row in rows)
