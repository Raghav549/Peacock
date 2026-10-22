"""Token definitions and reserved words for the Sanskrit-native language."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from peacock.sanskrit import INTERNAL_TO_SOURCE, LEGACY_KEYWORDS

from .diagnostics import Span


class TokenKind(str, Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    IDENT = "IDENT"
    EOF = "EOF"

    # Keywords that participate in the implemented grammar.
    MODULE = "प्रकरण"
    USE = "उपयोग"
    AS = "रूपेण"
    FN = "कार्य"
    LET = "स्थापय"
    MUT = "परिवर्तनीय"
    IF = "यदि"
    ELSE = "अन्यथा"
    WHILE = "यावत्"
    FOR = "प्रति"
    IN = "मध्ये"
    RETURN = "प्रत्यानय"
    BREAK = "विच्छिन्दु"
    CONTINUE = "अनुवर्तय"
    STRUCT = "संघटन"
    MODEL = "प्रतिमान"
    TRAINING = "अभ्यास"
    CAPABILITY = "अधिकार"
    TRY = "यत्न"
    CATCH = "गृह्ण"
    THROW = "क्षिप"
    ASSERT = "निश्चिनु"
    TRUE = "सत्य"
    FALSE = "असत्य"
    AND = "तथा"
    OR = "वा"
    NOT = "न"
    # Reserved for future phases; the parser rejects them explicitly.
    ENUM = "सूचीभेद"
    MATCH = "मिलान"
    IMPL = "कार्यान्वयन"
    PUB = "सार्वजनिक"
    CONST = "स्थिर"
    IMPORT = "आयात"
    ASYNC = "असामकालिक"
    AWAIT = "प्रतीक्षा"
    SPAWN = "जनय"
    YIELD = "उत्पादय"

    # Mathematical punctuation and operators are script-independent.
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    POWER = "**"
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    ASSIGN = "="
    PLUS_ASSIGN = "+="
    MINUS_ASSIGN = "-="
    STAR_ASSIGN = "*="
    SLASH_ASSIGN = "/="
    PERCENT_ASSIGN = "%="
    ARROW = "->"
    DOT = "."
    COMMA = ","
    COLON = ":"
    SEMICOLON = ";"
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    LBRACKET = "["
    RBRACKET = "]"
    DOTDOT = ".."
    QUESTION = "?"

    def describe(self) -> str:
        if self in _DISPLAY:
            return _DISPLAY[self]
        return self.value


_DISPLAY = {
    TokenKind.EOF: "सूत्रान्त",
    TokenKind.IDENT: "नाम",
    TokenKind.INT: "पूर्णाङ्कनिधि",
    TokenKind.FLOAT: "दशमलवनिधि",
    TokenKind.STRING: "अक्षरमालानिधि",
}

KEYWORDS: dict[str, TokenKind] = {
    kind.value: kind
    for kind in (
        TokenKind.MODULE, TokenKind.USE, TokenKind.AS, TokenKind.FN,
        TokenKind.LET, TokenKind.MUT, TokenKind.IF, TokenKind.ELSE,
        TokenKind.WHILE, TokenKind.FOR, TokenKind.IN, TokenKind.RETURN,
        TokenKind.BREAK, TokenKind.CONTINUE, TokenKind.STRUCT, TokenKind.MODEL,
        TokenKind.TRAINING, TokenKind.CAPABILITY, TokenKind.TRY, TokenKind.CATCH,
        TokenKind.THROW, TokenKind.ASSERT, TokenKind.TRUE, TokenKind.FALSE,
        TokenKind.AND, TokenKind.OR, TokenKind.NOT, TokenKind.ENUM,
        TokenKind.MATCH, TokenKind.IMPL, TokenKind.PUB, TokenKind.CONST,
        TokenKind.IMPORT, TokenKind.ASYNC, TokenKind.AWAIT, TokenKind.SPAWN,
        TokenKind.YIELD,
    )
}

#: Sanskrit keywords that are lexed but not accepted by the current parser.
RESERVED_FUTURE = {
    TokenKind.ENUM.value,
    TokenKind.MATCH.value,
    TokenKind.IMPL.value,
    TokenKind.PUB.value,
    TokenKind.CONST.value,
    TokenKind.IMPORT.value,
    TokenKind.ASYNC.value,
    TokenKind.AWAIT.value,
    TokenKind.SPAWN.value,
    TokenKind.YIELD.value,
}

# Stable internal capability/namespace names stored in verified bytecode.  The
# corresponding source spellings live in peacock.sanskrit and are never aliases.
KNOWN_CAPABILITIES = ("compute", "fs", "ui")
SOURCE_CAPABILITIES = tuple(INTERNAL_TO_SOURCE[name] for name in KNOWN_CAPABILITIES)
KNOWN_NAMESPACES = (
    "math", "nn", "colour", "graphics", "motion", "vyakarana", "ui",
    "scene3d", "agent",
)

#: Withdrawn English words are recognized only to issue PE1007.
LEGACY_SOURCE_WORDS = LEGACY_KEYWORDS


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    value: object
    span: Span

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.kind.name}({self.text!r})"
