"""Native Sanskrit grammar tools: corpus, pratyāhāra, sandhi and full Pāṇinian engine."""

from .corpus import EXPECTED_SUTRAS, CorpusError, Reference, Sutra, all_sutras, chapter, get_sutra, literature, search
from .pratyahara import MAHESHVARA_TEXT, PratyaharaError, expand
from .sandhi import EXECUTABLE_RULE_IDS, SandhiError, SandhiResult, join, join_text, viccheda, validate_sandhi
from .varna import classify_varna, is_vowel, is_consonant
from .sutra_engine import (
    Derivation, DerivationStep, Rule, RuleEngine, get_engine,
    rule_detail, apply_rules, adhikara_info, coverage as engine_coverage,
)
from .shabda import (
    ShabdaError, PadaForm, vibhakti_rupa, declension_table, all_rupas, guess_pratipadika,
    PARADIGMS, VIBHAKTIS, VACHANAS,
)
from .dhatu import (
    DhatuError, DhatuRupa, dhatu_rupa, conjugation_table, list_dhatus, tinanta_analyze,
    LAKARAS, PURUSHAS,
)
from .samasa import SamasaError, SamasaAnalysis, analyze as samasa_analyze, vigraha, list_types as samasa_types
from .karaka import KarakaError, KarakaLabel, analyze_sentence, karaka_info, list_karakas, list_examples as karaka_examples
from .derivation import Vyutpatti, VyutpattiStep, vyutpatti, list_derivations, prakriti_pratyaya_vibhaga
from .validator import ValidationResult, ValidationIssue, validate_word, validate_sentence, validate_sutra_application

__all__ = [
    "EXPECTED_SUTRAS", "CorpusError", "Reference", "Sutra", "all_sutras", "chapter",
    "get_sutra", "literature", "search", "MAHESHVARA_TEXT", "PratyaharaError", "expand",
    "EXECUTABLE_RULE_IDS", "SandhiError", "SandhiResult", "join", "join_text", "viccheda", "validate_sandhi",
    "classify_varna", "is_vowel", "is_consonant",
    "Derivation", "DerivationStep", "Rule", "RuleEngine", "get_engine", "rule_detail", "apply_rules", "adhikara_info", "engine_coverage",
    "ShabdaError", "PadaForm", "vibhakti_rupa", "declension_table", "all_rupas", "guess_pratipadika", "PARADIGMS", "VIBHAKTIS", "VACHANAS",
    "DhatuError", "DhatuRupa", "dhatu_rupa", "conjugation_table", "list_dhatus", "tinanta_analyze", "LAKARAS", "PURUSHAS",
    "SamasaError", "SamasaAnalysis", "samasa_analyze", "vigraha", "samasa_types",
    "KarakaError", "KarakaLabel", "analyze_sentence", "karaka_info", "list_karakas", "karaka_examples",
    "Vyutpatti", "VyutpattiStep", "vyutpatti", "list_derivations", "prakriti_pratyaya_vibhaga",
    "ValidationResult", "ValidationIssue", "validate_word", "validate_sentence", "validate_sutra_application",
]
