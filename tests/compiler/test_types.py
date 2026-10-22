import unittest

from peacock.compiler.types import (
    BoolType,
    NeverType,
    FloatType,
    IntType,
    ListType,
    StringType,
    TensorType,
    UnitType,
    broadcast_shapes,
    common_type,
    is_assignable,
    promote_dtype,
    tensor_binary_result,
)
from tests.support import expect_diagnostic


class TypeModelTests(unittest.TestCase):
    def test_primitive_types_are_singletons(self):
        self.assertIs(IntType, IntType)
        self.assertIsNot(IntType, FloatType)
        self.assertEqual(IntType.name, "Int")
        self.assertEqual(ListType(IntType).display(), "सूची<पूर्णाङ्क>")

    def test_is_assignable(self):
        self.assertTrue(is_assignable(IntType, IntType))
        self.assertFalse(is_assignable(IntType, FloatType))
        self.assertTrue(is_assignable(UnitType, UnitType))
        self.assertFalse(is_assignable(IntType, UnitType))

    def test_never_is_assignable_everywhere(self):
        self.assertTrue(is_assignable(NeverType, IntType))
        self.assertTrue(is_assignable(NeverType, UnitType))
        self.assertFalse(is_assignable(IntType, NeverType))

    def test_common_type(self):
        self.assertIs(common_type(IntType, IntType), IntType)
        self.assertIsNone(common_type(IntType, FloatType))
        self.assertIsNone(common_type(NeverType, BoolType))
        self.assertEqual(common_type(ListType(IntType), ListType(IntType)), ListType(IntType))
        self.assertIsNone(common_type(ListType(IntType), ListType(FloatType)))

    def test_promote_dtype(self):
        self.assertEqual(promote_dtype("Int32", "Float32"), "Float32")
        self.assertEqual(promote_dtype("Float32", "Float64"), "Float64")
        self.assertEqual(promote_dtype("Bool", "Int32"), "Int32")
        self.assertEqual(promote_dtype("Float32", "Float32"), "Float32")

    def test_broadcast_shapes(self):
        self.assertEqual(broadcast_shapes((2, 3), (2, 3)), (2, 3))
        self.assertEqual(broadcast_shapes((2, 1), (2, 3)), (2, 3))
        self.assertEqual(broadcast_shapes((1, 3), (2, 1)), (2, 3))
        self.assertEqual(broadcast_shapes((3,), (2, 3)), (2, 3))
        self.assertIsNone(broadcast_shapes((2,), (3,)))
        self.assertIsNone(broadcast_shapes((2, 3), (4, 3)))

    def test_tensor_binary_result(self):
        left = TensorType("Float32", (2, 1))
        right = TensorType("Float32", (1, 3))
        result, error = tensor_binary_result("+", left, right)
        self.assertIsNone(error)
        self.assertEqual(result.dtype, "Float32")
        self.assertEqual(result.shape, (2, 3))

    def test_tensor_result_dtype_promotion(self):
        result, error = tensor_binary_result("*", TensorType("Int32", (2,)), TensorType("Float32", (2,)))
        self.assertIsNone(error)
        self.assertEqual(result.dtype, "Float32")

    def test_tensor_binary_result_reports_incompatible_shapes(self):
        result, error = tensor_binary_result("+", TensorType("Float32", (2,)), TensorType("Float32", (3,)))
        self.assertIsNone(result)
        self.assertIn("broadcast", error)

    def test_tensor_scalar_result(self):
        result, error = tensor_binary_result("*", TensorType("Float32", (2, 3)), FloatType)
        self.assertIsNone(error)
        self.assertEqual(result.shape, (2, 3))
        self.assertEqual(result.dtype, "Float32")

    def test_tensor_binary_result_non_tensor_returns_none(self):
        result, error = tensor_binary_result("+", IntType, FloatType)
        self.assertIsNone(result)
        self.assertIsNone(error)

    def test_string_list_types(self):
        self.assertNotEqual(ListType(StringType), ListType(IntType))
        self.assertEqual(TensorType("Float32", (2, 3)).display(), "आयाम<दशमलव३२, [2, 3]>")
        self.assertEqual(TensorType("Float32").display(), "आयाम<दशमलव३२>")
        self.assertEqual(BoolType.name, "Bool")


class TypeDiagnosticSurfaceTests(unittest.TestCase):
    def test_annotated_assignment_mismatch(self):
        expect_diagnostic(
            'कार्य मुख्य() -> एकक { स्थापय क्ष: पूर्णाङ्क = "पाठ्य"; }', "PE3003", "cannot initialise"
        )

    def test_list_annotation_mismatch(self):
        expect_diagnostic(
            'कार्य मुख्य() -> एकक { स्थापय xs: सूची<अक्षरमाला> = [1, 2]; }', "PE3003"
        )

    def test_tensor_annotation(self):
        expect_diagnostic(
            'कार्य मुख्य() -> एकक { स्थापय त: आयाम<दशमलव३२, [2]> = आयामीकरण([[1.0, 2.0]]); }',
            "PE3003",
            "आयाम<दशमलव३२, [1, 2]>",
        )

    def test_unit_in_list_rejected(self):
        expect_diagnostic('कार्य मुख्य() -> एकक { स्थापय xs: सूची<एकक> = []; }', "PE3003")

    def test_bool_ordering(self):
        expect_diagnostic('कार्य मुख्य() -> एकक { स्थापय क्ष = सत्य < असत्य; }', "PE3003")

    def test_equality_across_types(self):
        expect_diagnostic('कार्य मुख्य() -> एकक { स्थापय क्ष = 1 == "1"; }', "PE3003")


if __name__ == "__main__":
    unittest.main()
