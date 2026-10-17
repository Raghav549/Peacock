import unittest

from peacock.compiler.diagnostics import (
    ArtifactError,
    CapabilityError,
    Diagnostic,
    DiagnosticBag,
    HostError,
    LexError,
    ParseError,
    PeacockError,
    ResourceLimitError,
    RuntimeError_,
    SemanticError,
    Severity,
    Span,
)
from peacock.compiler.pipeline import compile_source


class SpanTests(unittest.TestCase):
    def test_merge_covers_both(self):
        a = Span(4, 8, 2, 5)
        b = Span(12, 16, 2, 13)
        merged = a.merge(b)
        self.assertEqual((merged.start, merged.end), (4, 16))
        self.assertEqual((merged.line, merged.column), (2, 5))

    def test_merge_backwards(self):
        a = Span(10, 12, 3, 1)
        b = Span(2, 5, 1, 3)
        merged = a.merge(b)
        self.assertEqual((merged.start, merged.end), (2, 12))


class DiagnosticRenderingTests(unittest.TestCase):
    def test_caret_points_at_span(self):
        source = "fn main() -> Unit { let x = missing; }"
        result = compile_source(source, "demo.pac")
        rendered = result.diagnostics.render_all(source)
        self.assertIn("PE3002", rendered)
        self.assertIn("demo.pac" if "demo.pac" in rendered else "-->", rendered)
        self.assertIn("^", rendered)
        self.assertIn("missing", rendered)

    def test_hint_is_rendered(self):
        source = "fn main() -> Unit { let x = 1; x = 2; }"
        result = compile_source(source, "demo.pac")
        rendered = result.diagnostics.render_all(source)
        self.assertIn("let mut", rendered)

    def test_color_rendering_is_opt_in(self):
        source = "fn main() -> Unit { let x = missing; }"
        result = compile_source(source, "demo.pac")
        self.assertNotIn("\x1b[", result.diagnostics.render_all(source))
        self.assertIn("\x1b[", result.diagnostics.render_all(source, color=True))

    def test_bag_counts_and_iteration(self):
        bag = DiagnosticBag()
        span = Span(0, 1, 1, 1)
        bag.error("PE3001", "one", span)
        bag.warning("PE3100", "two", span)
        bag.warning("PE3100", "three", span)
        self.assertEqual(len(bag), 3)
        self.assertEqual(len(bag.errors()), 1)
        self.assertEqual(len(bag.warnings()), 2)
        self.assertTrue(bag.has_errors)
        self.assertEqual([d.message for d in bag], ["one", "two", "three"])

    def test_severity_ordering(self):
        self.assertTrue(Severity.ERROR.is_error)
        self.assertFalse(Severity.WARNING.is_error)
        self.assertLess(Severity.NOTE.value, Severity.WARNING.value)  # deterministic enum values

    def test_diagnostic_string(self):
        diagnostic = Diagnostic("PE3003", Severity.ERROR, "bad type", Span(2, 5, 1, 3))
        self.assertIn("PE3003", str(diagnostic))
        self.assertIn("bad type", str(diagnostic))


class ErrorClassTests(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(PeacockError.code, "PE0000")
        self.assertEqual(LexError.code, "PE1000")
        self.assertEqual(ParseError.code, "PE2000")
        self.assertEqual(SemanticError.code, "PE3000")
        self.assertEqual(RuntimeError_.code, "PE4000")
        self.assertEqual(CapabilityError.code, "PE4001")
        self.assertEqual(ResourceLimitError.code, "PE4003")
        self.assertEqual(ArtifactError.code, "PE5000")
        self.assertEqual(HostError.code, "PE5001")

    def test_message_and_code_rendering(self):
        error = HostError("blocked", "PE4002")
        self.assertEqual(error.code, "PE4002")
        self.assertEqual(error.message, "blocked")
        self.assertEqual(str(error), "blocked")


if __name__ == "__main__":
    unittest.main()
