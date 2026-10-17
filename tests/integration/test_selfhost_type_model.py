"""Differentially exercise PEACOCK type relations from actual parsed signatures."""

import unittest

from peacock.compiler.pipeline import compile_source
from tests.integration.test_cli import run_cli
TYPE_CORPUS = '''\
module type_parity
struct Point { x: Int }
fn take_int(x: Int) -> Unit {}
fn take_int_list(x: List<Int>) -> Unit {}
fn take_float_list(x: List<Float>) -> Unit {}
fn take_point(x: Point) -> Unit {}
fn take_float(x: Float) -> Unit {}
fn take_bool(x: Bool) -> Unit {}
fn take_string(x: String) -> Unit {}
fn take_never(x: Never) -> Unit {}
fn take_tensor_a(x: Tensor<Float32, [2, 3]>) -> Unit {}
fn take_tensor_b(x: Tensor<Float32, [2, 3]>) -> Unit {}
fn take_tensor_other_shape(x: Tensor<Float32, [3, 2]>) -> Unit {}
fn take_tensor_other_dtype(x: Tensor<Float64, [2, 3]>) -> Unit {}
fn take_tensor_dynamic(x: Tensor<Float32>) -> Unit {}
fn take_nested_list(x: List<List<Int>>) -> Unit {}
'''


class SelfHostedTypeModelTests(unittest.TestCase):
    def test_type_model_checks_execute_in_peacock(self):
        result = run_cli("run", "selfhost/type_model.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "PEACOCK type-model checks passed (56 assertions)",
        )

    def test_type_model_is_checked_as_pac_source(self):
        result = run_cli("check", "selfhost/type_model.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK selfhost/type_model.pac", result.stdout)

    def test_relations_match_python_for_real_parsed_declaration_types(self):
        result = compile_source(TYPE_CORPUS, "type_parity.pac", semantic_mode="shadow")
        self.assertTrue(result.ok, result.diagnostics.render_all(TYPE_CORPUS))
        self.assertGreater(result.stats["selfhost_type_cases"], 0)

    def test_error_iterable_recovery_does_not_add_a_second_diagnostic(self):
        source = "fn main() -> Unit { for item in missing {} }"
        python_result = compile_source(source, "error_iterable.pac", semantic_mode="python")
        shadow_result = compile_source(source, "error_iterable.pac", semantic_mode="shadow")
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
            'fn main() -> Unit { let x: Int = "bad"; }',
            "fn main() -> Unit { let x = unknown_name; }",
            # ErrorType is iterable-compatible for recovery only: the
            # unresolved name owns the diagnostic, with no second PE3003.
            "fn main() -> Unit { for item in missing {} }",
            "fn main() -> Unit { for item in 42 {} }",
            """\
fn add(left: Int, right: Int) -> Int { return left + right; }
fn main() -> Unit {
    let mut value: Int = 0;
    let values: List<List<Int>> = [[1], [2, 3]];
    for row in values {
        let item = row[0];
        value += add(right: item, left: value);
    }
    if value > 0 { let value = "shadowed"; print(value); }
    assert value >= 0;
}
""",
            """\
fn expect_int(value: Int) -> Int { return value; }
fn main() -> Unit { let result = expect_int(1.0); }
""",
            "fn main() -> Unit { let value = 1; value = 2; }",
            "fn main() -> Unit { if 1 { print(\"unreachable\"); } }",
            "fn main() -> Unit { let mut value = 1; value += 1.0; }",
            "fn main() -> Unit { let duplicate = 1; let duplicate = 2; }",
        ]
        for source in cases:
            with self.subTest(source=source):
                python_result = compile_source(source, "case.pac", semantic_mode="python")
                shadow_result = compile_source(source, "case.pac", semantic_mode="shadow")
                self.assertEqual(shadow_result.ok, python_result.ok)
                self.assertEqual(
                    [(d.code, d.message) for d in shadow_result.diagnostics],
                    [(d.code, d.message) for d in python_result.diagnostics],
                )
                self.assertGreaterEqual(shadow_result.stats["selfhost_builtin_cases"], 55)

    def test_shadow_semantics_cover_the_compiled_example_corpus(self):
        from pathlib import Path

        paths = sorted(Path("examples").glob("*.pac"))
        paths += sorted(Path("linguist/samples").glob("*.pac"))
        paths.append(Path("selfhost/fixtures/core_syntax.pac"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                result = compile_source(source, str(path), semantic_mode="shadow")
                self.assertTrue(result.ok, result.diagnostics.render_all(source))
                self.assertGreater(result.stats["selfhost_type_cases"], 0)
                self.assertIn("selfhost_semantic_cases", result.stats)


if __name__ == "__main__":
    unittest.main()
