import unittest

from peacock.compiler.pipeline import compile_source
from tests.support import compile_ok, expect_diagnostic


def fn(body: str, return_type: str = "Unit", prelude: str = "") -> str:
    return f"{prelude}\nfn main() -> {return_type} {{\n{body}\n}}\n"


class TypeCheckingTests(unittest.TestCase):
    def test_arithmetic_types(self):
        compile_ok(fn("let a = 1 + 2; let b = 1.5 * 2.0; let c = 'x';".replace("'", '"')))

    def test_no_implicit_int_float_conversion(self):
        expect_diagnostic(fn("let x = 1 + 2.0;"), "PE3003")

    def test_float_and_int_arguments_do_not_coerce(self):
        source = """
        fn scale(x: Float) -> Float { return x * 2.0; }
        fn main() -> Unit { let y = scale(3); }
        """
        expect_diagnostic(source, "PE3003", "expects Float")

    def test_string_concatenation_only_with_strings(self):
        expect_diagnostic(fn('let x = "a" + 1;'), "PE3003", "operator '+'")

    def test_unary_minus_on_string(self):
        expect_diagnostic(fn('let x = -"a";'), "PE3003")

    def test_comparison_of_mismatched_types(self):
        expect_diagnostic(fn("let x = 1 < 2.0;"), "PE3003", "ordering comparison")

    def test_boolean_operators_require_bool(self):
        expect_diagnostic(fn("let x = 1 and true;"), "PE3003", "Bool")

    def test_tensor_operator_types(self):
        compile_ok(
            fn(
                "let a = tensor([[1.0, 2.0]]); let b = tensor([[3.0], [4.0]]); "
                "let c = a + a; let d = a * 2.0; let e = a.matmul(tensor([[1.0], [2.0]]));"
            )
        )

    def test_tensor_broadcast_mismatch(self):
        expect_diagnostic(
            fn("let a = tensor([1.0, 2.0]); let b = tensor([1.0, 2.0, 3.0]); let c = a + b;"),
            "PE3003",
            "broadcast",
        )

    def test_tensor_dtype_mismatch(self):
        expect_diagnostic(
            fn("let a = tensor([1, 2]); let b = tensor([1.0, 2.0]); let c = a + b;"),
            "PE3003",
            "dtype",
        )

    def test_matmul_shape_mismatch(self):
        expect_diagnostic(
            fn(
                "let a = tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]); "
                "let b = tensor([[1.0, 2.0], [3.0, 4.0]]); let c = a.matmul(b);"
            ),
            "PE3003",
            "inner dimensions",
        )

    def test_unknown_dtype(self):
        expect_diagnostic(
            "fn main() -> Unit { let x: Tensor<Float16, [2]> = tensor([1.0, 2.0]); }",
            "PE3003",
            "dtype",
        )

    def test_list_requires_homogeneous_elements(self):
        expect_diagnostic(fn('let xs = [1, 2.0];'), "PE3003", "share one type")

    def test_empty_list_requires_annotation(self):
        expect_diagnostic(fn("let xs = [];"), "PE3003", "empty list")
        compile_ok(fn("let xs: List<Int> = [];"))

    def test_unknown_type_suggests(self):
        diagnostic = expect_diagnostic(
            "fn main() -> Unit { let x: Strng = \"a\"; }", "PE3003", "unknown type"
        )
        self.assertIn("String", diagnostic.hint or "")

    def test_any_cannot_be_written_in_source(self):
        expect_diagnostic("fn main() -> Unit { let x: Any = 1; }", "PE3012", "Any")


class NameResolutionTests(unittest.TestCase):
    def test_unknown_variable(self):
        diagnostic = expect_diagnostic(fn("let x = missing;"), "PE3002", "missing")
        self.assertIsNotNone(diagnostic.span)

    def test_unknown_function(self):
        expect_diagnostic(fn("missing();"), "PE3002")

    def test_immutable_assignment(self):
        expect_diagnostic(fn("let x = 1; x = 2;"), "PE3007", "immutable")

    def test_mutable_assignment(self):
        compile_ok(fn("let mut x = 1; x = 2; x += 3;"))

    def test_duplicate_local(self):
        expect_diagnostic(fn("let x = 1; let x = 2;"), "PE3001", "already declared")

    def test_duplicate_parameter(self):
        expect_diagnostic("fn f(x: Int, x: Int) -> Int { return x; }", "PE3001")

    def test_function_as_value_rejected(self):
        expect_diagnostic(
            "fn f() -> Unit { }\nfn main() -> Unit { let g = f; }", "PE3012", "first-class"
        )

    def test_unused_variable_warning(self):
        result = compile_source(fn("let unused = 1;"))
        self.assertFalse(result.diagnostics.has_errors)
        self.assertTrue(any(d.code == "PE3100" for d in result.diagnostics))

    def test_unreachable_warning(self):
        result = compile_source(fn("return;\nlet x = 1;"))
        self.assertTrue(any(d.code == "PE3102" for d in result.diagnostics))

    def test_break_outside_loop(self):
        expect_diagnostic(fn("break;"), "PE3011")

    def test_struct_fields_and_constructor(self):
        source = """
        struct Point { x: Int, y: Int }
        fn main() -> Unit {
            let p = Point(1, 2);
            let q = p.x + p.y;
            p.x = 5;
        }
        """
        compile_ok(source)

    def test_struct_constructor_wrong_arity(self):
        expect_diagnostic(
            "struct P { x: Int }\nfn main() -> Unit { let p = P(1, 2); }",
            "PE3004",
            "expects 1",
        )

    def test_struct_unknown_field(self):
        expect_diagnostic(
            "struct P { x: Int }\nfn main() -> Unit { let p = P(1); let y = p.z; }",
            "PE3015",
        )

    def test_duplicate_struct_field(self):
        expect_diagnostic("struct P { x: Int, x: Int }", "PE3001", "duplicate field")


class FunctionTests(unittest.TestCase):
    def test_missing_return_path(self):
        expect_diagnostic(
            "fn f(n: Int) -> Int { if n > 0 { return 1; } }\nfn main() -> Unit { let x = f(1); }",
            "PE3008",
            "does not return",
        )

    def test_wrong_return_type(self):
        expect_diagnostic(
            'fn f() -> Int { return "a"; }\nfn main() -> Unit { let x = f(); }',
            "PE3008",
        )

    def test_unit_function_returning_value(self):
        expect_diagnostic(fn("return 1;"), "PE3008")

    def test_call_arity(self):
        expect_diagnostic(
            "fn add(a: Int, b: Int) -> Int { return a + b; }\n"
            "fn main() -> Unit { let x = add(1); }",
            "PE3004",
            "missing argument",
        )

    def test_call_argument_types(self):
        expect_diagnostic(
            'fn echo(s: String) -> String { return s; }\n'
            "fn main() -> Unit { let x = echo(1); }",
            "PE3003",
        )

    def test_user_named_arguments(self):
        compile_ok(
            "fn add(a: Int, b: Int) -> Int { return a + b; }\n"
            "fn main() -> Unit { let x = add(b: 2, a: 1); assert(x == 3); }"
        )

    def test_named_argument_unknown_parameter(self):
        expect_diagnostic(
            "fn add(a: Int) -> Int { return a; }\n"
            "fn main() -> Unit { let x = add(b: 1); }",
            "PE3004",
            "no parameter",
        )

    def test_duplicate_named_argument(self):
        expect_diagnostic(
            "fn add(a: Int, b: Int) -> Int { return a + b; }\n"
            "fn main() -> Unit { let x = add(a: 1, a: 2); }",
            "PE3004",
            "twice",
        )

    def test_non_unit_return_needs_value(self):
        expect_diagnostic(
            "fn f() -> Int { return; }\nfn main() -> Unit { let x = f(); }",
            "PE3008",
        )


class CapabilityTests(unittest.TestCase):
    def test_native_requires_declared_capability(self):
        source = """
        use graphics
        fn main() -> Unit {
            let c = graphics.canvas(4, 4);
            graphics.save(c, "out.png");
        }
        """
        expect_diagnostic(source, "PE3005", "fs")

    def test_declared_capability_allows_call(self):
        source = """
        use graphics
        fn main() -> Unit {
            capability fs;
            let c = graphics.canvas(4, 4);
            graphics.save(c, "out.png");
        }
        """
        compile_ok(source)

    def test_unknown_capability(self):
        expect_diagnostic(fn("capability camera;"), "PE3005", "unknown capability")

    def test_capability_must_be_top_level(self):
        expect_diagnostic(fn("if true { capability fs; }"), "PE3005", "function body")

    def test_duplicate_capability(self):
        expect_diagnostic(fn("capability fs; capability fs;"), "PE3005", "twice")

    def test_model_training_require_compute(self):
        source = """
        use nn
        model Net {
            input x: Tensor<Float32, [2]>
            output y: Tensor<Float32, [2]>
            stack { Dense(units: 2) }
        }
        training Train { epochs: 1 }
        fn main() -> Unit {
            let data = nn.xor();
            let net = Net.init(seed: 1);
            let losses = Train.run(net, data);
        }
        """
        expect_diagnostic(source, "PE3005", "compute")


class ModuleTests(unittest.TestCase):
    def test_namespace_requires_use(self):
        expect_diagnostic(fn("let x = math.pi();"), "PE3006", "not imported")

    def test_unknown_module(self):
        expect_diagnostic("use neural;\nfn main() -> Unit { }", "PE3006", "unknown module")

    def test_duplicate_use(self):
        expect_diagnostic("use nn\nuse nn;\nfn main() -> Unit { }", "PE3001", "more than once")

    def test_unknown_namespace_member(self):
        expect_diagnostic("use nn\nfn main() -> Unit { let x = nn.nope(); }", "PE3006", "no function")

    def test_nested_module_path_rejected(self):
        expect_diagnostic("use nn.train;\nfn main() -> Unit { }", "PE3006", "whole")


class ModelValidationTests(unittest.TestCase):
    def model(self, stack: str, output_shape: str = "[2]", inputs: str = "input x: Tensor<Float32, [2]>"):
        return f"""
        model Net {{
            {inputs}
            output y: Tensor<Float32, {output_shape}>
            stack {{ {stack} }}
        }}
        fn main() -> Unit {{ }}
        """

    def test_valid_model(self):
        compile_ok(self.model("Dense(units: 4, activation: relu) Dense(units: 2)"))

    def test_output_dimension_mismatch(self):
        expect_diagnostic(
            self.model("Dense(units: 4, activation: relu) Dense(units: 2)", "[3]"),
            "PE3009",
            "produces 2",
        )

    def test_unknown_activation(self):
        expect_diagnostic(self.model("Dense(units: 2, activation: gelu)"), "PE3009", "activation")

    def test_unknown_layer(self):
        expect_diagnostic(self.model("Conv2D(filters: 3)"), "PE3009", "unknown layer")

    def test_missing_units(self):
        expect_diagnostic(self.model("Dense(activation: relu)"), "PE3009", "units")

    def test_empty_stack(self):
        expect_diagnostic(self.model(""), "PE3009", "empty stack")

    def test_model_input_requires_static_shape(self):
        expect_diagnostic(
            self.model("Dense(units: 2)", inputs="input x: Tensor<Float32>"),
            "PE3009",
            "static",
        )

    def test_model_input_must_be_tensor(self):
        expect_diagnostic(
            self.model("Dense(units: 2)", inputs="input x: Int"),
            "PE3009",
            "Tensor",
        )

    def test_duplicate_layer_argument(self):
        expect_diagnostic(
            self.model("Dense(units: 2, units: 3)"), "PE3009", "duplicate layer argument"
        )


class TrainingValidationTests(unittest.TestCase):
    def training(self, body: str):
        return f"training Train {{\n{body}\n}}\nfn main() -> Unit {{ }}\n"

    def test_valid_training(self):
        compile_ok(
            self.training(
                'objective: "cross_entropy"\noptimiser: "adam"\nepochs: 10\n'
                "learning_rate: 0.001\nbatch_size: 8\nseed: 3"
            )
        )

    def test_unknown_option(self):
        expect_diagnostic(self.training("momentum: 0.9"), "PE3010", "unknown training option")

    def test_epochs_must_be_positive(self):
        expect_diagnostic(self.training("epochs: 0"), "PE3010")

    def test_learning_rate_must_be_positive(self):
        expect_diagnostic(self.training("learning_rate: -0.1"), "PE3010", "positive")

    def test_unknown_optimiser(self):
        expect_diagnostic(self.training('optimiser: "rmsprop"'), "PE3010", "optimiser")

    def test_unknown_objective(self):
        expect_diagnostic(self.training('objective: "hinge"'), "PE3010", "objective")

    def test_non_literal_value(self):
        expect_diagnostic(self.training("epochs: 1 + 2"), "PE3010", "literal")


class DeclarationConflictTests(unittest.TestCase):
    def test_builtin_name_conflict(self):
        expect_diagnostic("fn print() -> Unit { }", "PE3001", "built-in")

    def test_duplicate_function(self):
        expect_diagnostic("fn f() -> Unit { }\nfn f() -> Unit { }", "PE3001")

    def test_type_name_conflict(self):
        expect_diagnostic("struct Tensor { x: Int }", "PE3001", "built-in type")


if __name__ == "__main__":
    unittest.main()
