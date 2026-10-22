#!/usr/bin/env python3
"""Generate the shared Sanskrit TextMate grammar from compiler vocabulary.

Run from the repository root after changing ``peacock/sanskrit.py`` or token
definitions.  ``--check`` is suitable for CI and never rewrites files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from peacock.compiler.builtins import NATIVES, NAMESPACES
from peacock.compiler.tokens import RESERVED_FUTURE, TokenKind
from peacock.sanskrit import INTERNAL_TO_SOURCE

TARGETS = (
    ROOT / "linguist" / "peacock.tmLanguage.json",
    ROOT / "editors" / "vscode" / "syntaxes" / "peacock.tmLanguage.json",
)

IDENTIFIER = r"[\p{L}_][\p{L}\p{M}\p{N}_]*"
NOT_WORD_BEFORE = r"(?<![\p{L}\p{M}\p{N}_])"
NOT_WORD_AFTER = r"(?![\p{L}\p{M}\p{N}_])"
DIGIT = r"\p{Nd}"


def _alternation(words) -> str:
    return "|".join(re.escape(word) for word in sorted(set(words), key=lambda w: (-len(w), w)))


def _words(words, *, capture: bool = False) -> str:
    body = _alternation(words)
    group = f"({body})" if capture else f"(?:{body})"
    return NOT_WORD_BEFORE + group + NOT_WORD_AFTER


def _native(internal: str) -> str:
    return INTERNAL_TO_SOURCE.get(internal, internal)


def build_grammar() -> dict:
    control = [TokenKind[name].value for name in (
        "IF", "ELSE", "WHILE", "FOR", "IN", "RETURN", "BREAK", "CONTINUE",
        "TRY", "CATCH", "THROW", "ASSERT",
    )]
    other = [TokenKind[name].value for name in (
        "MODULE", "USE", "AS", "FN", "LET", "MUT", "STRUCT", "MODEL",
        "TRAINING", "CAPABILITY", "AND", "OR", "NOT",
    )]
    primitive = [_native(name) for name in ("Int", "Float", "Bool", "String", "Unit", "Never", "Any")]
    compound = [_native(name) for name in (
        "Tensor", "List", "Color", "Canvas", "Model", "Dataset", "Range",
        "Float32", "Float64", "Int32",
    )]
    contextual = [_native(name) for name in (
        "input", "output", "stack", "Dense", "units", "activation", "objective",
        "optimiser", "epochs", "learning_rate", "batch_size", "seed",
    )]
    capabilities = [_native(name) for name in ("compute", "fs", "ui")]
    namespaces = [_native(name) for name in NAMESPACES]
    globals_ = [_native(name) for name in NATIVES if "." not in name]

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "Peacock",
        "scopeName": "source.peacock",
        "fileTypes": ["सूत्र"],
        "patterns": [
            {"include": "#comments"},
            {"include": "#declarations"},
            {"include": "#capabilities"},
            {"include": "#keywords"},
            {"include": "#reserved"},
            {"include": "#contextuals"},
            {"include": "#types"},
            {"include": "#constants"},
            {"include": "#namespaces"},
            {"include": "#builtins"},
            {"include": "#strings"},
            {"include": "#numbers"},
            {"include": "#methods"},
            {"include": "#operators"},
            {"include": "#punctuation"},
        ],
        "repository": {
            "comments": {"patterns": [
                {"name": "comment.line.double-slash.peacock", "match": "//.*$"},
                {
                    "name": "comment.block.peacock", "begin": r"/\*", "end": r"\*/",
                    "patterns": [{"include": "#comments"}],
                },
            ]},
            "declarations": {"patterns": [
                {
                    "name": "meta.function.peacock",
                    "match": _words([TokenKind.FN.value], capture=True) + r"\s+(" + IDENTIFIER + ")",
                    "captures": {
                        "1": {"name": "storage.type.function.peacock"},
                        "2": {"name": "entity.name.function.peacock"},
                    },
                },
                {
                    "match": _words([TokenKind[k].value for k in ("STRUCT", "MODEL", "TRAINING")], capture=True)
                    + r"\s+(" + IDENTIFIER + ")",
                    "captures": {
                        "1": {"name": "storage.type.peacock"},
                        "2": {"name": "entity.name.type.peacock"},
                    },
                },
            ]},
            "capabilities": {"patterns": [{
                "name": "meta.capability.peacock",
                "match": _words([TokenKind.CAPABILITY.value], capture=True) + r"\s+" + _words(capabilities, capture=True),
                "captures": {
                    "1": {"name": "storage.modifier.capability.peacock"},
                    "2": {"name": "support.constant.capability.peacock"},
                },
            }]},
            "keywords": {"patterns": [
                {"name": "keyword.control.peacock", "match": _words(control)},
                {"name": "keyword.other.peacock", "match": _words(other)},
            ]},
            "reserved": {"patterns": [
                {"name": "keyword.other.reserved.peacock", "match": _words(RESERVED_FUTURE)},
            ]},
            "contextuals": {"patterns": [
                {"name": "support.constant.contextual.peacock", "match": _words(contextual)},
            ]},
            "types": {"patterns": [
                {"name": "support.type.primitive.peacock", "match": _words(primitive)},
                {"name": "support.type.peacock", "match": _words(compound)},
            ]},
            "constants": {"patterns": [{
                "name": "constant.language.peacock",
                "match": _words([TokenKind.TRUE.value, TokenKind.FALSE.value]),
            }]},
            "namespaces": {"patterns": [{
                "name": "support.namespace.peacock",
                "match": _words(namespaces) + r"(?=\s*\.)",
            }]},
            "builtins": {"patterns": [{
                "name": "support.function.builtin.peacock",
                "match": _words(globals_) + r"(?=\s*\()",
            }]},
            "strings": {"patterns": [{
                "name": "string.quoted.double.peacock", "begin": '"', "end": '"',
                "patterns": [{"name": "constant.character.escape.peacock", "match": r"\\."}],
            }]},
            "numbers": {"patterns": [
                {
                    "name": "constant.numeric.float.peacock",
                    "match": NOT_WORD_BEFORE + DIGIT + "[" + DIGIT + r"_]*(?:\." + DIGIT + "[" + DIGIT + r"_]+)?(?:[eE][+-]?" + DIGIT + "[" + DIGIT + r"_]+)" + NOT_WORD_AFTER,
                },
                {
                    "name": "constant.numeric.float.peacock",
                    "match": NOT_WORD_BEFORE + DIGIT + "[" + DIGIT + r"_]*\." + DIGIT + "[" + DIGIT + r"_]*" + NOT_WORD_AFTER,
                },
                {
                    "name": "constant.numeric.integer.peacock",
                    "match": NOT_WORD_BEFORE + r"(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|" + DIGIT + "[" + DIGIT + r"_]*)" + NOT_WORD_AFTER,
                },
            ]},
            "methods": {"patterns": [{
                "name": "meta.method-call.peacock",
                "match": r"(?<=\.)(" + IDENTIFIER + r")\s*(?=\()",
                "captures": {"1": {"name": "entity.name.function.method.peacock"}},
            }]},
            "operators": {"patterns": [{
                "name": "keyword.operator.peacock",
                "match": r"\*\*|==|!=|<=|>=|->|\+=|-=|\*=|/=|%=|\.\.|[-+*/%<>=]",
            }]},
            "punctuation": {"patterns": [
                {"name": "punctuation.separator.peacock", "match": r"[(),;?]"},
                {"name": "punctuation.accessor.peacock", "match": r"\."},
                {"name": "punctuation.section.peacock", "match": r"[{}\[\]]"},
                {"name": "punctuation.definition.peacock", "match": ":"},
            ]},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    rendered = json.dumps(build_grammar(), ensure_ascii=False, indent=2) + "\n"
    stale = [path for path in TARGETS if not path.exists() or path.read_text(encoding="utf-8") != rendered]
    if args.check:
        for path in stale:
            print(f"stale grammar: {path.relative_to(ROOT)}")
        return bool(stale)
    for path in TARGETS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
