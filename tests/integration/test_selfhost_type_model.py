"""Differentially exercise PEACOCK type relations from actual parsed signatures."""

import unittest

from peacock.compiler.pipeline import compile_source
from tests.integration.test_cli import run_cli
TYPE_CORPUS = '''प्रकरण type_parity
संघटन Point { क्ष: पूर्णाङ्क }
कार्य take_int(क्ष: पूर्णाङ्क) -> एकक {}
कार्य take_int_list(क्ष: सूची<पूर्णाङ्क>) -> एकक {}
कार्य take_float_list(क्ष: सूची<दशमलव>) -> एकक {}
कार्य take_point(क्ष: Point) -> एकक {}
कार्य take_float(क्ष: दशमलव) -> एकक {}
कार्य take_bool(क्ष: सत्यता) -> एकक {}
कार्य take_string(क्ष: अक्षरमाला) -> एकक {}
कार्य take_never(क्ष: अभाव) -> एकक {}
कार्य take_tensor_a(क्ष: आयाम<दशमलव३२, [2, 3]>) -> एकक {}
कार्य take_tensor_b(क्ष: आयाम<दशमलव३२, [2, 3]>) -> एकक {}
कार्य take_tensor_other_shape(क्ष: आयाम<दशमलव३२, [3, 2]>) -> एकक {}
कार्य take_tensor_other_dtype(क्ष: आयाम<दशमलव६४, [2, 3]>) -> एकक {}
कार्य take_tensor_dynamic(क्ष: आयाम<दशमलव३२>) -> एकक {}
कार्य take_nested_list(क्ष: सूची<सूची<पूर्णाङ्क>>) -> एकक {}
'''


class SelfHostedTypeModelTests(unittest.TestCase):
    def test_type_model_checks_execute_in_peacock(self):
        result = run_cli("run", "selfhost/type_model.सूत्र")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "PEACOCK type-model checks passed (56 assertions)",
        )

    def test_type_model_is_checked_as_sutra_source(self):
        result = run_cli("check", "selfhost/type_model.सूत्र")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK selfhost/type_model.सूत्र", result.stdout)

    def test_relations_match_python_for_real_parsed_declaration_types(self):
        result = compile_source(TYPE_CORPUS, "type_parity.सूत्र", semantic_mode="shadow")
        self.assertTrue(result.ok, result.diagnostics.render_all(TYPE_CORPUS))
        self.assertGreater(result.stats["selfhost_type_cases"], 0)

    def test_error_iterable_recovery_does_not_add_a_second_diagnostic(self):
        source = 'कार्य मुख्य() -> एकक { प्रति अवयव मध्ये missing {} }'
        python_result = compile_source(source, "error_iterable.सूत्र", semantic_mode="python")
        shadow_result = compile_source(source, "error_iterable.सूत्र", semantic_mode="shadow")
        self.assertFalse(python_result.ok)
        self.assertFalse(shadow_result.ok)
        self.assertEqual([diagnostic.code for diagnostic in python_result.diagnostics], ["PE3002"])
        self.assertEqual(
            [(d.code, d.message) for d in shadow_result.diagnostics],
            [(d.code, d.message) for d in python_result.diagnostics],
        )

    def test_shadow_mode_preserves_python_accept_reject_and_diagnostics(self):
        cases = [
            TYPE_CORPUS,
            'कार्य मुख्य() -> एकक { स्थापय क्ष: पूर्णाङ्क = "bad"; }',
            'कार्य मुख्य() -> एकक { स्थापय क्ष = unknown_name; }',
            # ErrorType is iterable-compatible for recovery only: the
            # unresolved name owns the diagnostic, with no second PE3003.
            'कार्य मुख्य() -> एकक { प्रति अवयव मध्ये missing {} }',
            'कार्य मुख्य() -> एकक { प्रति अवयव मध्ये 42 {} }',
            """कार्य add(left: पूर्णाङ्क, right: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय left + right; }
कार्य मुख्य() -> एकक {
    स्थापय परिवर्तनीय मूल्य: पूर्णाङ्क = 0;
    स्थापय values: सूची<सूची<पूर्णाङ्क>> = [[1], [2, 3]];
    प्रति row मध्ये values {
        स्थापय अवयव = row[0];
        मूल्य += add(right: अवयव, left: मूल्य);
    }
    यदि मूल्य > 0 { स्थापय मूल्य = "shadowed"; मुद्रय(मूल्य); }
    निश्चिनु मूल्य >= 0;
}
""",
            """कार्य expect_int(मूल्य: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय मूल्य; }
कार्य मुख्य() -> एकक { स्थापय result = expect_int(1.0); }
""",
            'कार्य मुख्य() -> एकक { स्थापय मूल्य = 1; मूल्य = 2; }',
            'कार्य मुख्य() -> एकक { यदि 1 { मुद्रय("unreachable"); } }',
            'कार्य मुख्य() -> एकक { स्थापय परिवर्तनीय मूल्य = 1; मूल्य += 1.0; }',
            'कार्य मुख्य() -> एकक { स्थापय duplicate = 1; स्थापय duplicate = 2; }',
        ]
        for source in cases:
            with self.subTest(source=source):
                python_result = compile_source(source, "case.सूत्र", semantic_mode="python")
                shadow_result = compile_source(source, "case.सूत्र", semantic_mode="shadow")
                self.assertEqual(shadow_result.ok, python_result.ok)
                self.assertEqual(
                    [(d.code, d.message) for d in shadow_result.diagnostics],
                    [(d.code, d.message) for d in python_result.diagnostics],
                )
                self.assertGreaterEqual(shadow_result.stats["selfhost_builtin_cases"], 55)

    def test_shadow_semantics_cover_the_compiled_example_corpus(self):
        from pathlib import Path

        paths = sorted(Path("examples").glob("*.सूत्र"))
        paths += sorted(Path("linguist/samples").glob("*.सूत्र"))
        paths.append(Path("selfhost/fixtures/core_syntax.सूत्र"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                result = compile_source(source, str(path), semantic_mode="shadow")
                self.assertTrue(result.ok, result.diagnostics.render_all(source))
                self.assertGreater(result.stats["selfhost_type_cases"], 0)
                self.assertIn("selfhost_semantic_cases", result.stats)


if __name__ == "__main__":
    unittest.main()
