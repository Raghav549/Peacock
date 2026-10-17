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
'''


class SelfHostedTypeModelTests(unittest.TestCase):
    def test_type_model_checks_execute_in_peacock(self):
        result = run_cli("run", "selfhost/type_model.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PEACOCK type-model checks passed")

    def test_type_model_is_checked_as_pac_source(self):
        result = run_cli("check", "selfhost/type_model.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK selfhost/type_model.pac", result.stdout)

    def test_relations_match_python_for_real_parsed_declaration_types(self):
        result = compile_source(TYPE_CORPUS, "type_parity.pac", semantic_mode="shadow")
        self.assertTrue(result.ok, result.diagnostics.render_all(TYPE_CORPUS))
        self.assertGreater(result.stats["selfhost_type_cases"], 0)

    def test_shadow_mode_preserves_python_accept_reject_and_diagnostics(self):
        cases = [
            TYPE_CORPUS,
            'fn main() -> Unit { let x: Int = "bad"; }',
            "fn main() -> Unit { let x = unknown_name; }",
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


if __name__ == "__main__":
    unittest.main()
