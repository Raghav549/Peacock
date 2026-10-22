import unittest

from peacock.compiler.pipeline import compile_source
from tests.support import compile_ok, expect_diagnostic


def fn(body: str, return_type: str = "एकक", prelude: str = "") -> str:
    return f"{prelude}\nकार्य मुख्य() -> {return_type} {{\n{body}\n}}\n"


class TypeCheckingTests(unittest.TestCase):
    def test_arithmetic_types(self):
        compile_ok(fn("स्थापय अ = 1 + 2; स्थापय ब = 1.5 * 2.0; स्थापय च = 'क्ष';".replace("'", '"')))

    def test_no_implicit_int_float_conversion(self):
        expect_diagnostic(fn('स्थापय क्ष = 1 + 2.0;'), "PE3003")

    def test_float_and_int_arguments_do_not_coerce(self):
        source = """
        कार्य scale(क्ष: दशमलव) -> दशमलव { प्रत्यानय क्ष * 2.0; }
        कार्य मुख्य() -> एकक { स्थापय य = scale(3); }
        """
        expect_diagnostic(source, "PE3003", "expects दशमलव")

    def test_string_concatenation_only_with_strings(self):
        expect_diagnostic(fn('स्थापय क्ष = "a" + 1;'), "PE3003", "operator '+'")

    def test_unary_minus_on_string(self):
        expect_diagnostic(fn('स्थापय क्ष = -"a";'), "PE3003")

    def test_comparison_of_mismatched_types(self):
        expect_diagnostic(fn('स्थापय क्ष = 1 < 2.0;'), "PE3003", "ordering comparison")

    def test_boolean_operators_require_bool(self):
        expect_diagnostic(fn('स्थापय क्ष = 1 तथा सत्य;'), "PE3003", "Bool")

    def test_tensor_operator_types(self):
        compile_ok(
            fn(
                'स्थापय अ = आयामीकरण([[1.0, 2.0]]); स्थापय ब = आयामीकरण([[3.0], [4.0]]); '
                'स्थापय च = अ + अ; स्थापय d = अ * 2.0; स्थापय घाताधार = अ.आव्यूहगुणन(आयामीकरण([[1.0], [2.0]]));'
            )
        )

    def test_tensor_broadcast_mismatch(self):
        expect_diagnostic(
            fn('स्थापय अ = आयामीकरण([1.0, 2.0]); स्थापय ब = आयामीकरण([1.0, 2.0, 3.0]); स्थापय च = अ + ब;'),
            "PE3003",
            "broadcast",
        )

    def test_tensor_dtype_mismatch(self):
        expect_diagnostic(
            fn('स्थापय अ = आयामीकरण([1, 2]); स्थापय ब = आयामीकरण([1.0, 2.0]); स्थापय च = अ + ब;'),
            "PE3003",
            "dtype",
        )

    def test_matmul_shape_mismatch(self):
        expect_diagnostic(
            fn(
                'स्थापय अ = आयामीकरण([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]); '
                'स्थापय ब = आयामीकरण([[1.0, 2.0], [3.0, 4.0]]); स्थापय च = अ.आव्यूहगुणन(ब);'
            ),
            "PE3003",
            "inner dimensions",
        )

    def test_unknown_dtype(self):
        expect_diagnostic(
            'कार्य मुख्य() -> एकक { स्थापय क्ष: आयाम<Float16, [2]> = आयामीकरण([1.0, 2.0]); }',
            "PE3003",
            "dtype",
        )

    def test_list_requires_homogeneous_elements(self):
        expect_diagnostic(fn('स्थापय xs = [1, 2.0];'), "PE3003", "share one type")

    def test_empty_list_requires_annotation(self):
        expect_diagnostic(fn('स्थापय xs = [];'), "PE3003", "empty list")
        compile_ok(fn('स्थापय xs: सूची<पूर्णाङ्क> = [];'))

    def test_unknown_type_suggests(self):
        diagnostic = expect_diagnostic(
            'कार्य मुख्य() -> एकक { स्थापय क्ष: Strng = "a"; }', "PE3003", "unknown type"
        )
        self.assertIn("String", diagnostic.hint or "")

    def test_any_cannot_be_written_in_source(self):
        expect_diagnostic('कार्य मुख्य() -> एकक { स्थापय क्ष: सर्व = 1; }', "PE3012", "Any")


class NameResolutionTests(unittest.TestCase):
    def test_unknown_variable(self):
        diagnostic = expect_diagnostic(fn('स्थापय क्ष = missing;'), "PE3002", "missing")
        self.assertIsNotNone(diagnostic.span)

    def test_unknown_function(self):
        expect_diagnostic(fn("missing();"), "PE3002")

    def test_immutable_assignment(self):
        expect_diagnostic(fn('स्थापय क्ष = 1; क्ष = 2;'), "PE3007", "immutable")

    def test_mutable_assignment(self):
        compile_ok(fn('स्थापय परिवर्तनीय क्ष = 1; क्ष = 2; क्ष += 3;'))

    def test_duplicate_local(self):
        expect_diagnostic(fn('स्थापय क्ष = 1; स्थापय क्ष = 2;'), "PE3001", "already declared")

    def test_duplicate_parameter(self):
        expect_diagnostic('कार्य f(क्ष: पूर्णाङ्क, क्ष: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय क्ष; }', "PE3001")

    def test_function_as_value_rejected(self):
        expect_diagnostic(
            'कार्य f() -> एकक { }\nकार्य मुख्य() -> एकक { स्थापय ग = f; }', "PE3012", "first-class"
        )

    def test_unused_variable_warning(self):
        result = compile_source(fn('स्थापय unused = 1;'))
        self.assertFalse(result.diagnostics.has_errors)
        self.assertTrue(any(d.code == "PE3100" for d in result.diagnostics))

    def test_unreachable_warning(self):
        result = compile_source(fn('प्रत्यानय;\nस्थापय क्ष = 1;'))
        self.assertTrue(any(d.code == "PE3102" for d in result.diagnostics))

    def test_break_outside_loop(self):
        expect_diagnostic(fn("विच्छिन्दु;"), "PE3011")

    def test_struct_fields_and_constructor(self):
        source = """
        संघटन Point { क्ष: पूर्णाङ्क, य: पूर्णाङ्क }
        कार्य मुख्य() -> एकक {
            स्थापय p = Point(1, 2);
            स्थापय q = p.क्ष + p.य;
            p.क्ष = 5;
        }
        """
        compile_ok(source)

    def test_struct_constructor_wrong_arity(self):
        expect_diagnostic(
            'संघटन P { क्ष: पूर्णाङ्क }\nकार्य मुख्य() -> एकक { स्थापय p = P(1, 2); }',
            "PE3004",
            "expects 1",
        )

    def test_struct_unknown_field(self):
        expect_diagnostic(
            'संघटन P { क्ष: पूर्णाङ्क }\nकार्य मुख्य() -> एकक { स्थापय p = P(1); स्थापय य = p.z; }',
            "PE3015",
        )

    def test_duplicate_struct_field(self):
        expect_diagnostic('संघटन P { क्ष: पूर्णाङ्क, क्ष: पूर्णाङ्क }', "PE3001", "duplicate field")


class FunctionTests(unittest.TestCase):
    def test_missing_return_path(self):
        expect_diagnostic(
            'कार्य f(n: पूर्णाङ्क) -> पूर्णाङ्क { यदि n > 0 { प्रत्यानय 1; } }\nकार्य मुख्य() -> एकक { स्थापय क्ष = f(1); }',
            "PE3008",
            "does not return",
        )

    def test_wrong_return_type(self):
        expect_diagnostic(
            'कार्य f() -> पूर्णाङ्क { प्रत्यानय "a"; }\nकार्य मुख्य() -> एकक { स्थापय क्ष = f(); }',
            "PE3008",
        )

    def test_unit_function_returning_value(self):
        expect_diagnostic(fn('प्रत्यानय 1;'), "PE3008")

    def test_call_arity(self):
        expect_diagnostic(
            'कार्य add(अ: पूर्णाङ्क, ब: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ + ब; }\n'
            'कार्य मुख्य() -> एकक { स्थापय क्ष = add(1); }',
            "PE3004",
            "missing argument",
        )

    def test_call_argument_types(self):
        expect_diagnostic(
            'कार्य echo(s: अक्षरमाला) -> अक्षरमाला { प्रत्यानय s; }\n'
            'कार्य मुख्य() -> एकक { स्थापय क्ष = echo(1); }',
            "PE3003",
        )

    def test_user_named_arguments(self):
        compile_ok(
            'कार्य add(अ: पूर्णाङ्क, ब: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ + ब; }\n'
            'कार्य मुख्य() -> एकक { स्थापय क्ष = add(ब: 2, अ: 1); निश्चिनु(क्ष == 3); }'
        )

    def test_named_argument_unknown_parameter(self):
        expect_diagnostic(
            'कार्य add(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ; }\n'
            'कार्य मुख्य() -> एकक { स्थापय क्ष = add(ब: 1); }',
            "PE3004",
            "no parameter",
        )

    def test_duplicate_named_argument(self):
        expect_diagnostic(
            'कार्य add(अ: पूर्णाङ्क, ब: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ + ब; }\n'
            'कार्य मुख्य() -> एकक { स्थापय क्ष = add(अ: 1, अ: 2); }',
            "PE3004",
            "twice",
        )

    def test_non_unit_return_needs_value(self):
        expect_diagnostic(
            'कार्य f() -> पूर्णाङ्क { प्रत्यानय; }\nकार्य मुख्य() -> एकक { स्थापय क्ष = f(); }',
            "PE3008",
        )


class CapabilityTests(unittest.TestCase):
    def test_native_requires_declared_capability(self):
        source = """
        उपयोग चित्र
        कार्य मुख्य() -> एकक {
            स्थापय च = चित्र.चित्रपट्ट(4, 4);
            चित्र.रक्ष(च, "out.png");
        }
        """
        expect_diagnostic(source, "PE3005", "सञ्चय")

    def test_declared_capability_allows_call(self):
        source = """
        उपयोग चित्र
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            स्थापय च = चित्र.चित्रपट्ट(4, 4);
            चित्र.रक्ष(च, "out.png");
        }
        """
        compile_ok(source)

    def test_unknown_capability(self):
        expect_diagnostic(fn('अधिकार camera;'), "PE3005", "unknown capability")

    def test_capability_must_be_top_level(self):
        expect_diagnostic(fn('यदि सत्य { अधिकार सञ्चय; }'), "PE3005", "function body")

    def test_duplicate_capability(self):
        expect_diagnostic(fn('अधिकार सञ्चय; अधिकार सञ्चय;'), "PE3005", "twice")

    def test_model_training_require_compute(self):
        source = """
        उपयोग तन्त्रजाल
        प्रतिमान Net {
            निवेश क्ष: आयाम<दशमलव३२, [2]>
            निर्गम य: आयाम<दशमलव३२, [2]>
            क्रम { सघन(एककानि: 2) }
        }
        अभ्यास Train { आवृत्ति: 1 }
        कार्य मुख्य() -> एकक {
            स्थापय दत्त = तन्त्रजाल.असमानयोग();
            स्थापय net = Net.प्रारम्भ(बीज: 1);
            स्थापय losses = Train.चलाय(net, दत्त);
        }
        """
        expect_diagnostic(source, "PE3005", "गणना")


class ModuleTests(unittest.TestCase):
    def test_namespace_requires_use(self):
        expect_diagnostic(fn('स्थापय क्ष = गणित.वृत्तानुपात();'), "PE3006", "not imported")

    def test_unknown_module(self):
        expect_diagnostic('उपयोग neural;\nकार्य मुख्य() -> एकक { }', "PE3006", "unknown module")

    def test_duplicate_use(self):
        expect_diagnostic('उपयोग तन्त्रजाल\nउपयोग तन्त्रजाल;\nकार्य मुख्य() -> एकक { }', "PE3001", "more than once")

    def test_unknown_namespace_member(self):
        expect_diagnostic('उपयोग तन्त्रजाल\nकार्य मुख्य() -> एकक { स्थापय क्ष = तन्त्रजाल.nope(); }', "PE3006", "no function")

    def test_nested_module_path_rejected(self):
        expect_diagnostic('उपयोग तन्त्रजाल.अभ्यासय;\nकार्य मुख्य() -> एकक { }', "PE3006", "whole")


class ModelValidationTests(unittest.TestCase):
    def model(self, stack: str, output_shape: str = "[2]", inputs: str = "निवेश क्ष: आयाम<दशमलव३२, [2]>"):
        return f"""
        प्रतिमान Net {{
            {inputs}
            निर्गम य: आयाम<दशमलव३२, {output_shape}>
            क्रम {{ {stack} }}
        }}
        कार्य मुख्य() -> एकक {{ }}
        """

    def test_valid_model(self):
        compile_ok(self.model("सघन(एककानि: 4, सक्रियण: धनाङ्क) सघन(एककानि: 2)"))

    def test_output_dimension_mismatch(self):
        expect_diagnostic(
            self.model("सघन(एककानि: 4, सक्रियण: धनाङ्क) सघन(एककानि: 2)", "[3]"),
            "PE3009",
            "produces 2",
        )

    def test_unknown_activation(self):
        expect_diagnostic(self.model("सघन(एककानि: 2, सक्रियण: gelu)"), "PE3009", "activation")

    def test_unknown_layer(self):
        expect_diagnostic(self.model("Conv2D(filters: 3)"), "PE3009", "unknown layer")

    def test_missing_units(self):
        expect_diagnostic(self.model("सघन(सक्रियण: धनाङ्क)"), "PE3009", "एककानि")

    def test_empty_stack(self):
        expect_diagnostic(self.model(""), "PE3009", "empty stack")

    def test_model_input_requires_static_shape(self):
        expect_diagnostic(
            self.model("सघन(एककानि: 2)", inputs="निवेश क्ष: आयाम<दशमलव३२>"),
            "PE3009",
            "static",
        )

    def test_model_input_must_be_tensor(self):
        expect_diagnostic(
            self.model("सघन(एककानि: 2)", inputs="निवेश क्ष: पूर्णाङ्क"),
            "PE3009",
            "Tensor",
        )

    def test_duplicate_layer_argument(self):
        expect_diagnostic(
            self.model("सघन(एककानि: 2, एककानि: 3)"), "PE3009", "duplicate layer argument"
        )


class TrainingValidationTests(unittest.TestCase):
    def training(self, body: str):
        return f"अभ्यास Train {{\n{body}\n}}\nकार्य मुख्य() -> एकक {{ }}\n"

    def test_valid_training(self):
        compile_ok(
            self.training(
                'उद्देश्य: "अन्तरएन्ट्रॉपी"\nअनुकूलक: "आदम"\nआवृत्ति: 10\n'
                "अधिगमदर: 0.001\nसमूहमान: 8\nबीज: 3"
            )
        )

    def test_unknown_option(self):
        expect_diagnostic(self.training("momentum: 0.9"), "PE3010", "unknown training option")

    def test_epochs_must_be_positive(self):
        expect_diagnostic(self.training("आवृत्ति: 0"), "PE3010")

    def test_learning_rate_must_be_positive(self):
        expect_diagnostic(self.training("अधिगमदर: -0.1"), "PE3010", "positive")

    def test_unknown_optimiser(self):
        expect_diagnostic(self.training('अनुकूलक: "rmsprop"'), "PE3010", "optimiser")

    def test_unknown_objective(self):
        expect_diagnostic(self.training('उद्देश्य: "hinge"'), "PE3010", "objective")

    def test_non_literal_value(self):
        expect_diagnostic(self.training("आवृत्ति: 1 + 2"), "PE3010", "literal")


class DeclarationConflictTests(unittest.TestCase):
    def test_builtin_name_conflict(self):
        expect_diagnostic('कार्य मुद्रय() -> एकक { }', "PE3001", "built-in")

    def test_duplicate_function(self):
        expect_diagnostic('कार्य f() -> एकक { }\nकार्य f() -> एकक { }', "PE3001")

    def test_type_name_conflict(self):
        expect_diagnostic('संघटन आयाम { क्ष: पूर्णाङ्क }', "PE3001", "built-in type")


if __name__ == "__main__":
    unittest.main()
