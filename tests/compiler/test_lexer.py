import unittest

from peacock.compiler.lexer import lex
from peacock.compiler.tokens import TokenKind
from tests.support import expect_diagnostic


def kinds(source):
    tokens, diag = lex(source)
    assert not diag.has_errors, diag.render_all(source)
    return [t.kind for t in tokens]


class LexerTests(unittest.TestCase):
    def test_basic_tokens(self):
        tokens, diag = lex('module m\nfn main() -> Unit { let x = 1; }')
        self.assertEqual(len(diag), 0)
        self.assertEqual(tokens[0].kind, TokenKind.MODULE)
        self.assertEqual(tokens[1].value, "m")
        self.assertEqual(tokens[-1].kind, TokenKind.EOF)

    def test_keywords_and_identifiers(self):
        tokens, _ = lex("let mut if else while for in return break continue struct model training capability try catch throw assert true false and or not")
        expected = [
            TokenKind.LET, TokenKind.MUT, TokenKind.IF, TokenKind.ELSE, TokenKind.WHILE,
            TokenKind.FOR, TokenKind.IN, TokenKind.RETURN, TokenKind.BREAK,
            TokenKind.CONTINUE, TokenKind.STRUCT, TokenKind.MODEL, TokenKind.TRAINING,
            TokenKind.CAPABILITY, TokenKind.TRY, TokenKind.CATCH, TokenKind.THROW,
            TokenKind.ASSERT, TokenKind.TRUE, TokenKind.FALSE, TokenKind.AND,
            TokenKind.OR, TokenKind.NOT,
        ]
        self.assertEqual([t.kind for t in tokens[:-1]], expected)
        tokens, _ = lex("letting astructure")
        self.assertEqual(tokens[0].kind, TokenKind.IDENT)
        self.assertEqual(tokens[1].kind, TokenKind.IDENT)

    def test_integer_forms(self):
        tokens, _ = lex("0 42 1_000 0xFF 0b1010 0o17 9223372036854775807")
        values = [t.value for t in tokens[:-1]]
        self.assertEqual(values, [0, 42, 1000, 255, 10, 15, 2**63 - 1])

    def test_float_forms(self):
        tokens, _ = lex("1.5 0.25 1e3 2.5e-2 3E+4 1_000.5")
        values = [t.value for t in tokens[:-1]]
        self.assertEqual(values, [1.5, 0.25, 1000.0, 0.025, 30000.0, 1000.5])
        self.assertTrue(all(t.kind is TokenKind.FLOAT for t in tokens[:-1]))

    def test_strings_and_escapes(self):
        tokens, _ = lex(r'"hello" "line\nbreak" "tab\there" "quote\"inside" "\u{1F426}" "back\\slash"')
        values = [t.value for t in tokens[:-1]]
        self.assertEqual(values[0], "hello")
        self.assertEqual(values[1], "line\nbreak")
        self.assertEqual(values[2], "tab\there")
        self.assertEqual(values[3], 'quote"inside')
        self.assertEqual(values[4], "\U0001F426")
        self.assertEqual(values[5], "back\\slash")

    def test_spans_line_and_column(self):
        source = "fn main() {\n    print(1);\n}\n"
        tokens, _ = lex(source)
        print_tok = next(t for t in tokens if t.text == "print")
        self.assertEqual(print_tok.span.line, 2)
        self.assertEqual(print_tok.span.column, 5)
        self.assertEqual(print_tok.span.end - print_tok.span.start, 5)
        number = next(t for t in tokens if t.kind is TokenKind.INT)
        self.assertEqual(number.span.line, 2)
        self.assertEqual(number.span.column, 11)

    def test_comments_are_skipped_including_nested_blocks(self):
        source = "/* outer /* inner */ still outer */ let x = 1; // tail\nlet y = 2;"
        tokens, diag = lex(source)
        self.assertFalse(diag.has_errors)
        self.assertEqual(
            [t.text for t in tokens[:-1]], ["let", "x", "=", "1", ";", "let", "y", "=", "2", ";"]
        )

    def test_operators(self):
        tokens, _ = lex("** == != <= >= -> += -= *= /= %= .. + - * / % < > = . , : ; ( ) { } [ ] ?")
        self.assertEqual(tokens[0].kind, TokenKind.POWER)
        self.assertEqual(tokens[1].kind, TokenKind.EQ)
        self.assertEqual(tokens[2].kind, TokenKind.NE)
        self.assertEqual(tokens[11].kind, TokenKind.DOTDOT)
        self.assertEqual(tokens[-2].kind, TokenKind.QUESTION)

    def test_unterminated_string(self):
        expect_diagnostic('let s = "abc', "PE1020", "unterminated string")

    def test_newline_in_string(self):
        expect_diagnostic('let s = "abc\ndef";', "PE1021", "may not span lines")

    def test_unknown_escape(self):
        expect_diagnostic('let s = "\\q";', "PE1025", "unknown escape")

    def test_unterminated_block_comment(self):
        expect_diagnostic("/* never closed", "PE1001", "unterminated block comment")

    def test_invalid_character(self):
        expect_diagnostic("let x = 1 § 2;", "PE1002", "invalid character")

    def test_integer_overflow(self):
        expect_diagnostic("let x = 9223372036854775808;", "PE1013", "does not fit")

    def test_bad_radix_literal(self):
        expect_diagnostic("let x = 0x;", "PE1010", "expected digits")
        expect_diagnostic("let x = 0b102;", "PE1011", "invalid base-2")

    def test_bad_underscores(self):
        expect_diagnostic("let x = 1__0;", "PE1012", "underscores")

    def test_bang_and_bitwise_are_targeted_errors(self):
        expect_diagnostic("let x = !true;", "PE1004", "not")
        expect_diagnostic("let x = 1 & 2;", "PE1003", "not part of PEACOCK")

    def test_error_recovery_reports_multiple_lex_errors(self):
        tokens, diag = lex('"unterminated\nlet x = 1 § 2;')
        self.assertGreaterEqual(len(diag.errors()), 2)
        self.assertTrue(any(t.kind is TokenKind.LET for t in tokens))

    def test_eof_only_for_empty_source(self):
        tokens, diag = lex("")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].kind, TokenKind.EOF)
        self.assertFalse(diag.has_errors)


if __name__ == "__main__":
    unittest.main()
