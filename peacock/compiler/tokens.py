"""Token definitions and reserved words for PEACOCK 0.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .diagnostics import Span


class TokenKind(str, Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    IDENT = "IDENT"
    EOF = "EOF"

    # Keywords that participate in implemented grammar.
    MODULE = "module"
    USE = "use"
    AS = "as"
    FN = "fn"
    LET = "let"
    MUT = "mut"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    FOR = "for"
    IN = "in"
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    STRUCT = "struct"
    MODEL = "model"
    TRAINING = "training"
    CAPABILITY = "capability"
    TRY = "try"
    CATCH = "catch"
    THROW = "throw"
    ASSERT = "assert"
    TRUE = "true"
    FALSE = "false"
    AND = "and"
    OR = "or"
    NOT = "not"
    # Reserved for future phases. The parser rejects them with an explicit message.
    ENUM = "enum"
    MATCH = "match"
    IMPL = "impl"
    PUB = "pub"
    CONST = "const"
    IMPORT = "import"
    ASYNC = "async"
    AWAIT = "await"
    SPAWN = "spawn"
    YIELD = "yield"

    # Punctuation and operators.
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
    TokenKind.EOF: "end of file",
    TokenKind.IDENT: "identifier",
    TokenKind.INT: "integer literal",
    TokenKind.FLOAT: "floating-point literal",
    TokenKind.STRING: "string literal",
}

KEYWORDS: dict[str, TokenKind] = {
    "module": TokenKind.MODULE,
    "use": TokenKind.USE,
    "as": TokenKind.AS,
    "fn": TokenKind.FN,
    "let": TokenKind.LET,
    "mut": TokenKind.MUT,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "while": TokenKind.WHILE,
    "for": TokenKind.FOR,
    "in": TokenKind.IN,
    "return": TokenKind.RETURN,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
    "struct": TokenKind.STRUCT,
    "model": TokenKind.MODEL,
    "training": TokenKind.TRAINING,
    "capability": TokenKind.CAPABILITY,
    "try": TokenKind.TRY,
    "catch": TokenKind.CATCH,
    "throw": TokenKind.THROW,
    "assert": TokenKind.ASSERT,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    # Reserved for future phases, rejected with a targeted diagnostic.
    "enum": TokenKind.ENUM,
    "match": TokenKind.MATCH,
    "impl": TokenKind.IMPL,
    "pub": TokenKind.PUB,
    "const": TokenKind.CONST,
    "import": TokenKind.IMPORT,
    "async": TokenKind.ASYNC,
    "await": TokenKind.AWAIT,
    "spawn": TokenKind.SPAWN,
    "yield": TokenKind.YIELD,
}

#: Keywords that are lexed but not accepted by the 0.1 parser.
RESERVED_FUTURE = {
    "enum",
    "match",
    "impl",
    "pub",
    "const",
    "import",
    "async",
    "await",
    "spawn",
    "yield",
}

#: Capability names recognised by the 0.1 static checker.
KNOWN_CAPABILITIES = ("compute", "fs", "ui")

#: Standard-library namespaces requiring a matching ``use`` declaration.
KNOWN_NAMESPACES = ("math", "nn", "colour", "graphics", "motion")


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    value: object
    span: Span

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.kind.name}({self.text!r})"
