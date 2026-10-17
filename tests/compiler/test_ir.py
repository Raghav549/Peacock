import copy
import unittest

from peacock.compiler.ir import IRInstr, IRVerificationError, build_ir, verify_ir
from peacock.compiler.optimizer import optimize
from peacock.compiler.pipeline import compile_source
from tests.support import compile_ok


def raw_ir(source):
    result = compile_ok(source)
    return build_ir(result.typed, source, "test.pac")


class IRBuilderTests(unittest.TestCase):
    def test_ir_contains_expected_operations(self):
        ir = raw_ir(
            "fn add(a: Int, b: Int) -> Int { return a + b; }\n"
            "fn main() -> Unit { let x = add(1, 2); print(str(x)); }"
        )
        verify_ir(ir)
        ops = [instr.op for instr in ir.functions["add"].instrs]
        self.assertIn("binop", ops)
        self.assertEqual(ops[-1], "return")
        main_ops = [instr.op for instr in ir.functions["main"].instrs]
        self.assertIn("call", main_ops)
        self.assertIn("call_native", main_ops)

    def test_slot_allocation_is_per_function(self):
        ir = raw_ir(
            "fn f(a: Int) -> Int { let b = a + 1; return b; }\n"
            "fn main() -> Unit { let x = f(1); }"
        )
        self.assertGreaterEqual(ir.functions["f"].slot_count, 2)
        self.assertGreaterEqual(ir.functions["main"].slot_count, 1)

    def test_unreachable_statements_are_not_emitted(self):
        ir = raw_ir('fn main() -> Unit { return; print("never"); }')
        constants = [instr.args[0] for instr in ir.functions["main"].instrs if instr.op == "const"]
        self.assertNotIn("never", constants)

    def test_try_scope_is_balanced(self):
        ir = raw_ir(
            'fn main() -> Unit { try { throw "x"; } catch (e) { print(e); } }'
        )
        ops = [instr.op for instr in ir.functions["main"].instrs]
        self.assertEqual(ops.count("try_begin"), ops.count("try_end"))
        verify_ir(ir)

    def test_ir_uses_only_declared_capabilities(self):
        ir = raw_ir("fn main() -> Unit { capability fs; let x = 1; }")
        self.assertEqual(ir.functions["main"].capabilities, frozenset({"fs"}))


class OptimizerTests(unittest.TestCase):
    def optimized(self, source):
        ir = raw_ir(source)
        ir, stats = optimize(ir)
        verify_ir(ir)
        return ir, stats

    def test_constant_folding(self):
        ir, stats = self.optimized("fn main() -> Unit { let x = 1 + 2 * 3; print(str(x)); }")
        constants = [instr.args[0] for instr in ir.functions["main"].instrs if instr.op == "const"]
        self.assertIn(7, constants)
        self.assertGreaterEqual(stats["constants_folded"], 2)

    def test_constant_branch_folding(self):
        ir, stats = self.optimized(
            'fn main() -> Unit { if true { print("a"); } else { print("b"); } }'
        )
        ops = [instr.op for instr in ir.functions["main"].instrs]
        self.assertNotIn("branch", ops)
        constants = [instr.args[0] for instr in ir.functions["main"].instrs if instr.op == "const"]
        self.assertIn("a", constants)
        self.assertNotIn("b", constants)
        self.assertGreaterEqual(stats["branches_folded"], 1)

    def test_dead_temporary_elimination(self):
        ir, stats = self.optimized("fn main() -> Unit { 1 + 2; }")
        self.assertGreaterEqual(stats["dead_temps_removed"], 1)
        self.assertFalse(
            any(instr.op == "binop" for instr in ir.functions["main"].instrs)
        )

    def test_optimizer_is_idempotent(self):
        source = "fn main() -> Unit { let x = 1 + 2; if false { print(str(x)); } }"
        ir1, _ = self.optimized(source)
        first = [(i.op, i.dest, i.args) for i in ir1.functions["main"].instrs]
        ir2, _ = optimize(ir1)
        second = [(i.op, i.dest, i.args) for i in ir2.functions["main"].instrs]
        self.assertEqual(first, second)

    def test_all_examples_optimize_cleanly(self):
        for name in ("hello.pac", "tour.pac", "tensors.pac", "xor.pac", "aurora.pac"):
            source = (__import__("pathlib").Path(__file__).resolve().parents[2] / "examples" / name).read_text()
            result = compile_source(source, name)
            self.assertTrue(result.ok, name)
            verify_ir(result.ir)


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.ir = raw_ir("fn main() -> Unit { let x = 1; print(str(x)); }")

    def test_rejects_bad_register(self):
        bad = copy.deepcopy(self.ir)
        bad.functions["main"].instrs[1].dest = 9999
        with self.assertRaises(IRVerificationError):
            verify_ir(bad)

    def test_rejects_unknown_jump_target(self):
        bad = copy.deepcopy(self.ir)
        bad.functions["main"].instrs.insert(0, IRInstr("jump", None, ("nowhere",)))
        with self.assertRaises(IRVerificationError):
            verify_ir(bad)

    def test_rejects_missing_terminator(self):
        bad = copy.deepcopy(self.ir)
        bad.functions["main"].instrs = bad.functions["main"].instrs[:-1]
        with self.assertRaises(IRVerificationError):
            verify_ir(bad)

    def test_rejects_unknown_opcode(self):
        bad = copy.deepcopy(self.ir)
        bad.functions["main"].instrs.insert(0, IRInstr("mystery", 0, ()))
        with self.assertRaises(IRVerificationError):
            verify_ir(bad)

    def test_rejects_duplicate_label(self):
        bad = copy.deepcopy(self.ir)
        bad.functions["main"].instrs.insert(0, IRInstr("label", None, ("L",)))
        bad.functions["main"].instrs.insert(1, IRInstr("label", None, ("L",)))
        with self.assertRaises(IRVerificationError):
            verify_ir(bad)

    def test_rejects_binop_type_mismatch(self):
        bad = copy.deepcopy(self.ir)
        instrs = bad.functions["main"].instrs
        inserted = [
            IRInstr("const", 50, (1,), __import__("peacock.compiler.types", fromlist=["IntType"]).IntType),
            IRInstr("const", 51, (1.5,), __import__("peacock.compiler.types", fromlist=["FloatType"]).FloatType),
            IRInstr("binop", 52, ("+", 50, 51), __import__("peacock.compiler.types", fromlist=["IntType"]).IntType),
        ]
        bad.functions["main"].instrs = inserted + instrs
        with self.assertRaises(IRVerificationError):
            verify_ir(bad)


if __name__ == "__main__":
    unittest.main()
