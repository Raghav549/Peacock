import unittest

from peacock.compiler.ast_nodes import (
    AssignStmt,
    Binary,
    Call,
    ExprStmt,
    IfStmt,
    LetStmt,
    ListLit,
    ReturnStmt,
    Unary,
    WhileStmt,
)
from peacock.compiler.lexer import lex
from peacock.compiler.parser import parse


def parse_ok(source):
    tokens, lex_diag = lex(source)
    assert not lex_diag.has_errors, lex_diag.render_all(source)
    module, diag = parse(tokens, source)
    assert not diag.has_errors, diag.render_all(source)
    return module


def parse_errors(source):
    tokens, lex_diag = lex(source)
    assert not lex_diag.has_errors, lex_diag.render_all(source)
    module, diag = parse(tokens, source)
    return module, diag.errors()


class ParserStructureTests(unittest.TestCase):
    def test_module_and_uses(self):
        module = parse_ok("module app\nuse nn\nuse math;\nfn main() -> Unit { return; }")
        self.assertEqual(module.name, "app")
        self.assertEqual([u.path for u in module.uses], [["nn"], ["math"]])
        self.assertEqual(len(module.functions), 1)

    def test_operator_precedence(self):
        module = parse_ok("fn main() -> Unit { let x = 1 + 2 * 3; }")
        stmt = module.functions[0].body.statements[0]
        self.assertIsInstance(stmt, LetStmt)
        expr = stmt.init
        self.assertIsInstance(expr, Binary)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.right, Binary)
        self.assertEqual(expr.right.op, "*")

    def test_power_is_right_associative(self):
        module = parse_ok("fn main() -> Unit { let x = 2 ** 3 ** 2; }")
        expr = module.functions[0].body.statements[0].init
        self.assertEqual(expr.op, "**")
        self.assertEqual(expr.right.op, "**")

    def test_unary_and_comparison(self):
        module = parse_ok("fn main() -> Unit { let x = -a + not b; let y = 1 < 2; }")
        let_x = module.functions[0].body.statements[0]
        self.assertIsInstance(let_x.init.left, Unary)
        let_y = module.functions[0].body.statements[1]
        self.assertEqual(let_y.init.op, "<")

    def test_calls_and_named_arguments(self):
        module = parse_ok('fn main() -> Unit { let x = f(1, 2, seed: 3); }')
        call = module.functions[0].body.statements[0].init
        self.assertIsInstance(call, Call)
        self.assertEqual(len(call.args), 3)
        self.assertEqual(call.arg_names, [None, None, "seed"])

    def test_control_flow_nodes(self):
        module = parse_ok(
            "fn main() -> Unit { if a { } else if b { } else { } while x { break; } "
            "for i in 0..10 { continue; } return; }"
        )
        body = module.functions[0].body.statements
        self.assertIsInstance(body[0], IfStmt)
        self.assertIsInstance(body[0].else_branch, IfStmt)
        self.assertIsInstance(body[1], WhileStmt)
        self.assertIsInstance(body[3], ReturnStmt)

    def test_assignment_and_compound_assignment(self):
        module = parse_ok("fn main() -> Unit { let mut x = 1; x += 2; x = 4; }")
        body = module.functions[0].body.statements
        self.assertIsInstance(body[1], AssignStmt)
        self.assertEqual(body[1].op, "+=")
        self.assertEqual(body[2].op, "=")

    def test_list_and_range_literals(self):
        module = parse_ok("fn main() -> Unit { let xs = [1, 2, 3]; let r = 0..4; }")
        body = module.functions[0].body.statements
        self.assertIsInstance(body[0].init, ListLit)
        self.assertEqual(body[1].init.__class__.__name__, "RangeExpr")

    def test_assert_both_forms(self):
        module = parse_ok(
            'fn main() -> Unit { assert(true, "message"); assert true; }'
        )
        first = module.functions[0].body.statements[0]
        second = module.functions[0].body.statements[1]
        self.assertIsNotNone(first.message)
        self.assertIsNone(second.message)

    def test_struct_and_model(self):
        source = """
        struct Point { x: Int, y: Int }
        model Net {
            input x: Tensor<Float32, [2]>
            output y: Tensor<Float32, [2]>
            stack {
                Dense(units: 4, activation: relu)
                Dense(units: 2)
            }
        }
        training Train {
            objective: "cross_entropy"
            epochs: 3
        }
        """
        module = parse_ok(source)
        self.assertEqual(module.structs[0].name, "Point")
        model = module.models[0]
        self.assertEqual(model.inputs[0].name, "x")
        self.assertEqual(model.outputs[0].name, "y")
        self.assertEqual(len(model.layers), 2)
        self.assertEqual(model.layers[0].args[1].symbol, "relu")
        self.assertEqual(module.trainings[0].name, "Train")

    def test_dotted_and_index_expressions(self):
        module = parse_ok("fn main() -> Unit { let x = a.b[0].c(1).d; }")
        expr = module.functions[0].body.statements[0].init
        self.assertEqual(expr.name, "d")
        self.assertEqual(expr.base.__class__.__name__, "Call")
        self.assertEqual(expr.base.callee.name, "c")
        callee_base = expr.base.callee.base
        self.assertEqual(callee_base.__class__.__name__, "Index")

    def test_spans_are_monotonic(self):
        module = parse_ok("fn main() -> Unit {\n    let x = 1;\n}\n")
        body = module.functions[0].body
        self.assertLess(body.span.start, body.span.end)
        self.assertGreaterEqual(body.span.line, 1)


class ParserDiagnosticTests(unittest.TestCase):
    def test_missing_semicolon(self):
        _, errors = parse_errors("fn main() -> Unit { let x = 1 }")
        self.assertTrue(any(e.code == "PE2002" and "let binding" in e.message for e in errors))

    def test_missing_module_declaration_is_not_required(self):
        module = parse_ok("fn main() -> Unit { }")
        self.assertIsNone(module.name)

    def test_reserved_future_keywords(self):
        for keyword in ("async", "await", "enum", "match", "impl", "pub", "const", "import", "spawn", "yield"):
            _, errors = parse_errors(f"{keyword} fn main() -> Unit {{ }}")
            self.assertTrue(
                any(e.code == "PE2001" for e in errors),
                f"{keyword} should produce PE2001, got {[e.code for e in errors]}",
            )

    def test_chained_comparison(self):
        _, errors = parse_errors("fn main() -> Unit { let x = 1 < 2 < 3; }")
        self.assertTrue(any(e.code == "PE2031" for e in errors))

    def test_positional_after_named(self):
        _, errors = parse_errors("fn main() -> Unit { f(seed: 1, 2); }")
        self.assertTrue(any(e.code == "PE2033" for e in errors))

    def test_invalid_assignment_target(self):
        _, errors = parse_errors("fn main() -> Unit { 1 + 2 = 3; }")
        self.assertTrue(any(e.code == "PE2030" for e in errors))

    def test_model_missing_input_or_output(self):
        source = """
        model Net {
            input x: Tensor<Float32, [2]>
            stack { Dense(units: 2) }
        }
        """
        _, errors = parse_errors(source)
        self.assertTrue(any(e.code == "PE2011" for e in errors))

    def test_module_must_be_first(self):
        _, errors = parse_errors("fn main() -> Unit { }\nmodule late")
        self.assertTrue(any(e.code == "PE2003" for e in errors))

    def test_alias_is_rejected_with_targeted_message(self):
        _, errors = parse_errors("use nn as network;\nfn main() -> Unit { }")
        self.assertTrue(any(e.code == "PE2005" for e in errors))

    def test_recovery_reports_multiple_items(self):
        _, errors = parse_errors(
            "fn broken( -> Unit { }\nfn also_broken() -> Unit { let x = ; }\n"
        )
        self.assertGreaterEqual(len(errors), 2)

    def test_unexpected_top_level_token(self):
        _, errors = parse_errors("let x = 1;")
        self.assertTrue(any(e.code == "PE2004" for e in errors))


if __name__ == "__main__":
    unittest.main()
