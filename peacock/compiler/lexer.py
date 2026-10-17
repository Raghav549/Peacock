"""The PEACOCK lexer.

Hand-written scanner, no regular expressions, with precise spans and recovery.
Lexical rules are documented in ``SPECIFICATION.md`` §3.
"""

from __future__ import annotations

from .diagnostics import DiagnosticBag, Span
from .tokens import KEYWORDS, RESERVED_FUTURE, Token, TokenKind

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "0": "\0",
}

_PUNCT2 = {
    "**": TokenKind.POWER,
    "==": TokenKind.EQ,
    "!=": TokenKind.NE,
    "<=": TokenKind.LE,
    ">=": TokenKind.GE,
    "->": TokenKind.ARROW,
    "+=": TokenKind.PLUS_ASSIGN,
    "-=": TokenKind.MINUS_ASSIGN,
    "*=": TokenKind.STAR_ASSIGN,
    "/=": TokenKind.SLASH_ASSIGN,
    "%=": TokenKind.PERCENT_ASSIGN,
    "..": TokenKind.DOTDOT,
}

_PUNCT1 = {
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "%": TokenKind.PERCENT,
    "<": TokenKind.LT,
    ">": TokenKind.GT,
    "=": TokenKind.ASSIGN,
    ".": TokenKind.DOT,
    ",": TokenKind.COMMA,
    ":": TokenKind.COLON,
    ";": TokenKind.SEMICOLON,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "{": TokenKind.LBRACE,
    "}": TokenKind.RBRACE,
    "[": TokenKind.LBRACKET,
    "]": TokenKind.RBRACKET,
    "?": TokenKind.QUESTION,
}


class Lexer:
    def __init__(self, source: str, file: str = "<source>"):
        self.source = source
        self.file = file
        self.diag = DiagnosticBag()
        self.pos = 0
        self.line = 1
        self.column = 1
        self.length = len(source)

    # -- low level ---------------------------------------------------------
    def _peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.source[i] if i < self.length else ""

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _span_from(self, start: int, line: int, col: int) -> Span:
        return Span(start, self.pos, line, col)

    # -- scanning ----------------------------------------------------------
    def scan(self) -> list[Token]:
        tokens: list[Token] = []
        while self.pos < self.length:
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
                continue
            start, line, col = self.pos, self.line, self.column
            if ch == "/" and self._peek(1) == "/":
                self._line_comment()
                continue
            if ch == "/" and self._peek(1) == "*":
                self._block_comment(start, line, col)
                continue
            if ch.isdigit():
                tok = self._number(start, line, col)
                if tok is not None:
                    tokens.append(tok)
                continue
            if ch.isalpha() or ch == "_":
                tokens.append(self._identifier(start, line, col))
                continue
            if ch == '"':
                tok = self._string(start, line, col)
                if tok is not None:
                    tokens.append(tok)
                continue
            two = self.source[self.pos : self.pos + 2]
            if two in _PUNCT2:
                self._advance()
                self._advance()
                tokens.append(Token(_PUNCT2[two], two, None, self._span_from(start, line, col)))
                continue
            if ch in _PUNCT1:
                self._advance()
                tokens.append(Token(_PUNCT1[ch], ch, None, self._span_from(start, line, col)))
                continue
            # Targeted diagnostics for plausible-but-unsupported syntax.
            if ch in "&|":
                self.diag.error(
                    "PE1003",
                    f"bitwise/logical operator {ch!r} is not part of PEACOCK 0.1",
                    self._span_from(start, line, col),
                    hint="use the keywords 'and' and 'or' for boolean logic",
                )
            elif ch == "!":
                self.diag.error(
                    "PE1004",
                    "unexpected '!'; use the keyword 'not' for logical negation",
                    self._span_from(start, line, col),
                )
            elif ch == "=" and self._peek(1) == ">":
                self.diag.error(
                    "PE1005",
                    "match arms ('=>') are reserved but match expressions are not implemented in 0.1",
                    self._span_from(start, line, col),
                )
                self._advance()
                self._advance()
                continue
            elif ch == "@":
                self.diag.error("PE1006", "decorators ('@') are not part of PEACOCK 0.1", self._span_from(start, line, col))
            else:
                self.diag.error(
                    "PE1002",
                    f"invalid character {ch!r}",
                    self._span_from(start, line, col),
                )
            self._advance()
        end = Span(self.pos, self.pos, self.line, self.column)
        tokens.append(Token(TokenKind.EOF, "", None, end))
        return tokens

    def _line_comment(self) -> None:
        while self.pos < self.length and self._peek() != "\n":
            self._advance()

    def _block_comment(self, start: int, line: int, col: int) -> None:
        self._advance()
        self._advance()
        depth = 1
        while self.pos < self.length and depth > 0:
            if self._peek() == "/" and self._peek(1) == "*":
                depth += 1
                self._advance()
                self._advance()
            elif self._peek() == "*" and self._peek(1) == "/":
                depth -= 1
                self._advance()
                self._advance()
            else:
                self._advance()
        if depth > 0:
            self.diag.error(
                "PE1001",
                "unterminated block comment",
                self._span_from(start, line, col),
                hint="close the comment with '*/'; block comments nest",
            )

    def _identifier(self, start: int, line: int, col: int) -> Token:
        while self.pos < self.length and (self._peek().isalnum() or self._peek() == "_"):
            self._advance()
        text = self.source[start : self.pos]
        span = self._span_from(start, line, col)
        kind = KEYWORDS.get(text)
        if kind is not None:
            token = Token(kind, text, None, span)
        else:
            token = Token(TokenKind.IDENT, text, text, span)
        return token

    def _number(self, start: int, line: int, col: int) -> Token | None:
        # Radix prefixes.
        if self._peek() == "0" and self._peek(1) in ("x", "X", "b", "B", "o", "O"):
            prefix = self._peek(1).lower()
            base = {"x": 16, "b": 2, "o": 8}[prefix]
            self._advance()
            self._advance()
            digits_start = self.pos
            while self.pos < self.length and (self._peek().isalnum() or self._peek() == "_"):
                self._advance()
            raw_digits = self.source[digits_start : self.pos]
            if not raw_digits:
                self.diag.error(
                    "PE1010",
                    f"expected digits after '0{prefix}'",
                    self._span_from(start, line, col),
                )
                return None
            if not raw_digits.strip("_") or "__" in raw_digits or raw_digits.startswith("_") or raw_digits.endswith("_"):
                self.diag.error(
                    "PE1012",
                    f"invalid numeric literal '{self.source[start:self.pos]}': underscores must separate digits",
                    self._span_from(start, line, col),
                )
                return None
            digits = raw_digits.replace("_", "")
            if not digits:
                self.diag.error(
                    "PE1010",
                    f"expected digits after '0{prefix}'",
                    self._span_from(start, line, col),
                )
                return None
            try:
                value = int(digits, base)
            except ValueError:
                self.diag.error(
                    "PE1011",
                    f"invalid base-{base} integer literal '0{prefix}{digits}'",
                    self._span_from(start, line, col),
                )
                return None
            return Token(TokenKind.INT, self.source[start : self.pos], value, self._span_from(start, line, col))

        while self.pos < self.length and (self._peek().isdigit() or self._peek() == "_"):
            self._advance()
        is_float = False
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while self.pos < self.length and (self._peek().isdigit() or self._peek() == "_"):
                self._advance()
        if self._peek() in ("e", "E"):
            # Exponent must be followed by an optional sign and at least one digit.
            j = 1
            if self._peek(j) in ("+", "-"):
                j += 1
            if self._peek(j).isdigit():
                is_float = True
                self._advance()
                if self._peek() in ("+", "-"):
                    self._advance()
                while self.pos < self.length and (self._peek().isdigit() or self._peek() == "_"):
                    self._advance()

        text = self.source[start : self.pos]
        clean = text.replace("_", "")
        if (
            "__" in text
            or text.startswith("_")
            or text.endswith("_")
            or "._" in text
            or "_." in text
            or "_e" in text
            or "_E" in text
        ):
            self.diag.error(
                "PE1012",
                f"invalid numeric literal '{text}': underscores must separate digits",
                self._span_from(start, line, col),
            )
            return None
        try:
            if is_float:
                return Token(TokenKind.FLOAT, text, float(clean), self._span_from(start, line, col))
            value = int(clean, 10)
            if not (-(2**63) <= value < 2**63):
                self.diag.error(
                    "PE1013",
                    f"integer literal {value} does not fit in Int (signed 64-bit)",
                    self._span_from(start, line, col),
                )
                return None
            return Token(TokenKind.INT, text, value, self._span_from(start, line, col))
        except ValueError:
            self.diag.error("PE1014", f"invalid numeric literal '{text}'", self._span_from(start, line, col))
            return None

    def _string(self, start: int, line: int, col: int) -> Token | None:
        self._advance()  # opening quote
        parts: list[str] = []
        while True:
            if self.pos >= self.length:
                self.diag.error(
                    "PE1020",
                    "unterminated string literal",
                    self._span_from(start, line, col),
                    hint="add a closing double quote",
                )
                return None
            ch = self._peek()
            if ch == "\n":
                self.diag.error(
                    "PE1021",
                    "string literals may not span lines",
                    self._span_from(start, line, col),
                    hint=r"use the escape sequence \n for a newline",
                )
                return None
            if ch == '"':
                self._advance()
                return Token(
                    TokenKind.STRING,
                    self.source[start : self.pos],
                    "".join(parts),
                    self._span_from(start, line, col),
                )
            if ch == "\\":
                self._advance()
                esc = self._peek()
                if esc == "u":
                    self._advance()
                    if self._peek() != "{":
                        self.diag.error(
                            "PE1022",
                            "expected '{' after '\\u'",
                            self._span_from(start, line, col),
                            hint=r"the form is \u{1F426}",
                        )
                        return None
                    self._advance()
                    hex_start = self.pos
                    while self.pos < self.length and self._peek() != "}":
                        self._advance()
                    hex_digits = self.source[hex_start : self.pos]
                    if self._peek() != "}":
                        self.diag.error("PE1023", "unterminated unicode escape", self._span_from(start, line, col))
                        return None
                    self._advance()
                    try:
                        parts.append(chr(int(hex_digits, 16)))
                    except (ValueError, OverflowError):
                        self.diag.error(
                            "PE1024",
                            f"invalid unicode escape '\\u{{{hex_digits}}}'",
                            self._span_from(start, line, col),
                        )
                        return None
                    continue
                if esc == "":
                    self.diag.error("PE1020", "unterminated string literal", self._span_from(start, line, col))
                    return None
                if esc not in _ESCAPES:
                    self.diag.error(
                        "PE1025",
                        f"unknown escape sequence '\\{esc}'",
                        self._span_from(start, line, col),
                        hint="supported escapes: \\n \\t \\r \\\\ \\\" \\' \\0 \\u{...}",
                    )
                    self._advance()
                    continue
                parts.append(_ESCAPES[esc])
                self._advance()
                continue
            parts.append(ch)
            self._advance()


def lex(source: str, file: str = "<source>") -> tuple[list[Token], DiagnosticBag]:
    """Lex ``source`` and return tokens (always ending with EOF) plus diagnostics."""
    lexer = Lexer(source, file)
    tokens = lexer.scan()
    return tokens, lexer.diag


def tokenize_for_test(source: str) -> list[Token]:
    tokens, diag = lex(source)
    if diag.has_errors:
        raise ValueError(diag.render_all(source))
    return tokens
