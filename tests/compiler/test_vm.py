import io
import os
import tempfile
import unittest
from pathlib import Path

from peacock.compiler.diagnostics import CapabilityError, HostError, ResourceLimitError
from peacock.compiler.pipeline import compile_source
from peacock.runtime.artifact import ArtifactFormatError
from peacock.runtime.errors import VMFault, format_error
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM
from tests.support import REPO_ROOT, compile_ok, run_source


def make_vm(source, grants=(), argv=(), root=None, **policy_kwargs):
    result = compile_ok(source)
    stdout = policy_kwargs.pop("stdout", None) or io.StringIO()
    policy = HostPolicy(
        grants=frozenset(grants),
        root=str(root if root is not None else REPO_ROOT),
        **policy_kwargs,
    )
    return VM(result.image, policy, stdout=stdout, argv=list(argv)), stdout


class ArithmeticTests(unittest.TestCase):
    def test_integer_arithmetic(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                print(str(7 + 3));
                print(str(7 - 3));
                print(str(7 * 3));
                print(str(7 / 3));
                print(str(-7 / 3));
                print(str(-7 % 3));  // truncated division: remainder keeps the dividend's sign
                print(str(2 ** 10));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["10", "4", "21", "2", "-2", "-1", "1024"])

    def test_float_arithmetic(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                print(str(1.5 + 2.25));
                print(str(3.0 * 2.0));
                print(str(1.0 / 4.0));
                print(str(2.0 ** 3.0));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["3.75", "6.0", "0.25", "8.0"])

    def test_division_by_zero(self):
        vm, _ = make_vm("fn main() -> Unit { let x = 1 / 0; }")
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4005")

    def test_integer_overflow(self):
        vm, _ = make_vm("fn main() -> Unit { let x = 9223372036854775807 + 1; }")
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4004")

    def test_power_overflow(self):
        vm, _ = make_vm("fn main() -> Unit { let x = 2 ** 63; }")
        with self.assertRaises(VMFault):
            vm.run()

    def test_float_zero_division(self):
        vm, _ = make_vm("fn main() -> Unit { let x = 1.0 / 0.0; }")
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4005")


class ControlFlowTests(unittest.TestCase):
    def test_if_else(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let n = 5;
                if n > 10 { print("big"); } else if n > 3 { print("medium"); } else { print("small"); }
            }
            """
        )
        self.assertEqual(out.strip(), "medium")

    def test_while_break_continue(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let mut i = 0;
                let mut total = 0;
                while i < 20 {
                    i += 1;
                    if i % 2 == 0 { continue; }
                    if i > 9 { break; }
                    total += i;
                }
                print(str(total));
                print(str(i));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["25", "11"])

    def test_range_for(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let mut total = 0;
                for i in 0..5 { total += i; }
                print(str(total));
            }
            """
        )
        self.assertEqual(out.strip(), "10")

    def test_list_for(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let xs = [2, 3, 5, 7];
                let mut product = 1;
                for x in xs { product *= x; }
                print(str(product));
            }
            """
        )
        self.assertEqual(out.strip(), "210")

    def test_short_circuit_evaluation(self):
        out, _, _ = run_source(
            """
            fn boom() -> Bool { throw "must not run"; }
            fn main() -> Unit {
                let a = false and boom();
                let b = true or boom();
                print(str(a));
                print(str(b));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["false", "true"])

    def test_scoping_and_shadowing(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let x = 1;
                if true { let x = 2; print(str(x)); }
                print(str(x));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["2", "1"])

    def test_recursion(self):
        out, _, _ = run_source(
            """
            fn fact(n: Int) -> Int { if n <= 1 { return 1; } return n * fact(n - 1); }
            fn main() -> Unit { print(str(fact(10))); }
            """
        )
        self.assertEqual(out.strip(), "3628800")

    def test_call_depth_limit(self):
        vm, _ = make_vm(
            "fn f(n: Int) -> Int { return f(n + 1); }\n"
            "fn main() -> Unit { let x = f(0); }",
            max_call_depth=16,
        )
        with self.assertRaises(ResourceLimitError) as ctx:
            vm.run()
        self.assertIn("call depth", str(ctx.exception))

    def test_step_limit(self):
        vm, _ = make_vm("fn main() -> Unit { while true { } }", max_steps=500)
        with self.assertRaises(ResourceLimitError) as ctx:
            vm.run()
        self.assertIn("step limit", str(ctx.exception))

    def test_output_limit(self):
        vm, _ = make_vm(
            'fn main() -> Unit { print("123456"); print("123456"); }',
            max_output_chars=8,
        )
        with self.assertRaises(ResourceLimitError):
            vm.run()


class CollectionTests(unittest.TestCase):
    def test_list_methods(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let mut xs: List<Int> = [];
                xs.push(3); xs.push(1); xs.push(2);
                print(str(xs));
                print(str(xs.get(1)));
                print(str(xs.len()));
                print(str(xs.contains(2)));
                print(str(xs.index_of(9)));
                xs.sort(); print(str(xs));
                xs.reverse(); print(str(xs));
                xs[0] = 42; print(str(xs));
                print(str(xs.pop()));
            }
            """
        )
        self.assertEqual(
            out.splitlines(),
            ["[3, 1, 2]", "1", "3", "true", "-1", "[1, 2, 3]", "[3, 2, 1]", "[42, 2, 1]", "1"],
        )

    def test_list_bounds(self):
        vm, _ = make_vm("fn main() -> Unit { let xs = [1]; let x = xs.get(5); }")
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertIn("out of bounds", str(ctx.exception))

    def test_index_assignment(self):
        out, _, _ = run_source(
            "fn main() -> Unit { let xs = [1, 2, 3]; xs[1] = 9; print(str(xs)); }"
        )
        self.assertEqual(out.strip(), "[1, 9, 3]")

    def test_string_methods(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                print("  Peacock  ".trim());
                print("abc".upper());
                print("ABC".lower());
                print("abc".substring(1, 3));
                print(str("a,b,c".split(",")));
                print(str("abc".starts_with("ab")));
                print(str("abc".ends_with("bc")));
                print("abc".replace("b", "X"));
                print(str(len("hello")));
                print("hello"[1]);
            }
            """
        )
        self.assertEqual(
            out.splitlines(),
            ["Peacock", "ABC", "abc", "bc", '["a", "b", "c"]', "true", "true", "aXc", "5", "e"],
        )

    def test_substring_bounds(self):
        vm, _ = make_vm('fn main() -> Unit { print("abc".substring(2, 9)); }')
        with self.assertRaises(VMFault):
            vm.run()

    def test_string_index_bounds(self):
        vm, _ = make_vm('fn main() -> Unit { print("abc"[5]); }')
        with self.assertRaises(VMFault):
            vm.run()


class StructTests(unittest.TestCase):
    def test_struct_construction_and_mutation(self):
        out, _, _ = run_source(
            """
            struct Point { x: Int, y: Int }
            fn length_squared(p: Point) -> Int { return p.x * p.x + p.y * p.y; }
            fn main() -> Unit {
                let p = Point(3, 4);
                print(str(length_squared(p)));
                p.x = 6;
                print(str(p.x));
                print(type_name(p));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["25", "6", "Point"])


class ErrorHandlingTests(unittest.TestCase):
    def test_throw_and_catch(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                try { throw "boom"; } catch (message) { print("caught: " + message); }
                print("continues");
            }
            """
        )
        self.assertEqual(out.splitlines(), ["caught: boom", "continues"])

    def test_runtime_error_can_be_caught(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                try { let x = 1 / 0; print(str(x)); }
                catch (message) { print("error: " + message); }
            }
            """
        )
        self.assertEqual(out.strip(), "error: division by zero")

    def test_nested_try_rethrow(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                try {
                    try { throw "inner"; } catch (e) { throw "outer:" + e; }
                } catch (final) { print(final); }
            }
            """
        )
        self.assertEqual(out.strip(), "outer:inner")

    def test_uncaught_error_has_stack_trace(self):
        vm, _ = make_vm(
            """
            fn divide() -> Int { return 10 / 0; }
            fn middle() -> Int { return divide(); }
            fn main() -> Unit { let x = middle(); }
            """
        )
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        text = format_error(ctx.exception)
        self.assertIn("at divide", text)
        self.assertIn("at middle", text)
        self.assertIn("at main", text)
        self.assertIn("line", text)

    def test_assert_success_and_failure(self):
        out, _, _ = run_source(
            'fn main() -> Unit { assert(1 + 1 == 2, "math works"); print("ok"); }'
        )
        self.assertEqual(out.strip(), "ok")
        vm, _ = make_vm('fn main() -> Unit { assert(false, "boom"); }')
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4010")
        self.assertEqual(ctx.exception.message, "boom")


class CapabilityRuntimeTests(unittest.TestCase):
    def test_host_denies_compute(self):
        source = """
        use nn
        fn main() -> Unit {
            capability compute;
            let w = nn.parameter([1.0, 2.0]);
        }
        """
        vm, _ = make_vm(source, grants=())
        with self.assertRaises(CapabilityError) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4001")
        self.assertIn("host has not granted", str(ctx.exception))

    def test_host_grants_compute(self):
        source = """
        use nn
        fn main() -> Unit {
            capability compute;
            let w = nn.parameter([1.0, 2.0]);
            print(str(w.size));
        }
        """
        out, _, _ = run_source(source, grants=("compute",))
        self.assertEqual(out.strip(), "2")

    def test_fs_requires_host_grant(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            fs.write_text("blocked.txt", "data");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm, _ = make_vm(source, grants=(), root=tmp)
            with self.assertRaises(CapabilityError):
                vm.run()

    def test_fs_roundtrip_in_sandbox(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            fs.write_text("notes/hello.txt", "PEACOCK sandbox");
            let text = fs.read_text("notes/hello.txt");
            print(text);
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            out, _, _ = run_source(source, grants=("fs",), root=tmp)
            self.assertEqual(out.strip(), "PEACOCK sandbox")
            self.assertEqual(
                (Path(tmp) / "notes" / "hello.txt").read_text(encoding="utf-8"),
                "PEACOCK sandbox",
            )

    def test_fs_path_escape_is_blocked(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            let text = fs.read_text("../outside.txt");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            (Path(tmp) / "outside.txt").write_text("secret", encoding="utf-8")
            vm, _ = make_vm(source, grants=("fs",), root=root)
            with self.assertRaises(HostError) as ctx:
                vm.run()
            self.assertIn("escapes", str(ctx.exception))

    def test_fs_absolute_path_escape_is_blocked(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            let text = fs.read_text("/etc/passwd");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm, _ = make_vm(source, grants=("fs",), root=tmp)
            with self.assertRaises(HostError):
                vm.run()

    def test_fs_symlink_escape_is_blocked(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            let text = fs.read_text("link.txt");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            try:
                os.symlink(outside, root / "link.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported on this platform")
            vm, _ = make_vm(source, grants=("fs",), root=root)
            with self.assertRaises(HostError):
                vm.run()

    def test_fs_write_limit(self):
        source = """
        use fs
        fn main() -> Unit {
            capability fs;
            fs.write_text("big.txt", "0123456789ABCDEF");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm, _ = make_vm(source, grants=("fs",), root=tmp, max_file_bytes=8)
            with self.assertRaises(HostError):
                vm.run()

    def test_nul_byte_rejected(self):
        policy = HostPolicy(root=str(REPO_ROOT))
        with self.assertRaises(HostError):
            policy.resolve_path("bad\x00name")

    def test_unknown_grant_rejected(self):
        with self.assertRaises(HostError):
            HostPolicy(grants=frozenset({"camera"}))


class NativeBridgeTests(unittest.TestCase):
    def test_math_functions(self):
        out, _, _ = run_source(
            """
            use math
            fn main() -> Unit {
                print(str(math.sqrt(9.0)));
                print(str(math.round(2.5)));
                print(str(math.clamp(5.0, 0.0, 1.0)));
                print(str(math.min(1.0, 2.0)));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["3.0", "3", "1.0", "1.0"])

    def test_math_domain_error(self):
        vm, _ = make_vm("use math\nfn main() -> Unit { let x = math.sqrt(-1.0); }")
        with self.assertRaises(VMFault):
            vm.run()

    def test_text_functions(self):
        out, _, _ = run_source(
            """
            use text
            fn main() -> Unit {
                print(str(text.is_alpha("A")));
                print(str(text.is_digit("7")));
                print(str(text.ord("A")));
                print(text.chr(80) + text.chr(75));
                print(str(text.split_lines("a\\nb")));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["true", "true", "65", "PK", '["a", "b"]'])

    def test_process_args(self):
        source = "use process\nfn main() -> Unit { print(process.args().join(\"|\")); }"
        out, _, _ = run_source(source, argv=("alpha", "beta"))
        self.assertEqual(out.strip(), "alpha|beta")

    def test_graphics_save_writes_png(self):
        source = """
        use graphics
        use colour
        fn main() -> Unit {
            capability fs;
            let canvas = graphics.canvas(8, 6);
            graphics.fill(canvas, colour.srgb(1.0, 0.0, 0.0));
            graphics.save(canvas, "out/red.png");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            out, _, _ = run_source(source, grants=("fs",), root=tmp)
            data = (Path(tmp) / "out" / "red.png").read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG"))
            from peacock.frontend.png import decode_png

            width, height, rgba = decode_png(data)
            self.assertEqual((width, height), (8, 6))
            self.assertEqual(tuple(rgba[:4]), (255, 0, 0, 255))

    def test_invalid_canvas_arguments(self):
        vm, _ = make_vm("use graphics\nfn main() -> Unit { let c = graphics.canvas(0, 0); }")
        with self.assertRaises(VMFault):
            vm.run()

    def test_tensor_methods(self):
        out, _, _ = run_source(
            """
            fn main() -> Unit {
                let t = tensor([[1.0, 2.0], [3.0, 4.0]]);
                print(str(t.rank));
                print(str(t.size));
                print(str(t.sum()));
                print(str(t.transpose()));
                print(str(t.reshape([4])));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["2", "4", "10.0", "Tensor(Float32[2, 2], [[1.0, 3.0], [2.0, 4.0]])", "Tensor(Float32[4], [1.0, 2.0, 3.0, 4.0])"])

    def test_motion_native(self):
        out, _, _ = run_source(
            """
            use motion
            fn main() -> Unit {
                let values = motion.spring_steps(0.0, 10.0, 170.0, 26.0, 30, 0.016666666666666666);
                print(str(len(values)));
                print(str(motion.ease("linear", 0.25)));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["31", "0.25"])


class VMLifecycleTests(unittest.TestCase):
    def test_main_must_be_zero_arity(self):
        from tests.support import expect_diagnostic

        expect_diagnostic("fn main(x: Int) -> Unit { }", "PE3013", "no parameters")

    def test_main_must_return_unit(self):
        from tests.support import expect_diagnostic

        expect_diagnostic("fn main() -> Int { return 0; }", "PE3013", "Unit")

    def test_missing_main(self):
        result = compile_ok("fn helper() -> Unit { }")
        vm = VM(result.image, HostPolicy())
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertIn("no 'main'", str(ctx.exception))

    def test_invalid_image_rejected(self):
        result = compile_ok('fn main() -> Unit { print("x"); }')
        bad = {**result.image}
        bad["functions"] = {}
        with self.assertRaises(ArtifactFormatError):
            VM(bad, HostPolicy())

    def test_uninitialised_slot_guard(self):
        result = compile_ok("fn main() -> Unit { }")
        image = result.image
        code = [["PUSH_SLOT", 0], ["RET", 1]]
        image = {**image, "functions": {**image["functions"], "main": {**image["functions"]["main"], "code": code, "lines": [[1, 1], [1, 1]], "slots": 1}}}
        vm = VM(image, HostPolicy())
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertIn("uninitialised", str(ctx.exception))

    def test_halt_on_bad_pc(self):
        result = compile_ok("fn main() -> Unit { }")
        image = {**result.image}
        main = {**image["functions"]["main"], "code": [["JUMP", 99]], "lines": [[1, 1]]}
        image["functions"] = {**image["functions"], "main": main}
        with self.assertRaises(ArtifactFormatError):
            VM(image, HostPolicy())


if __name__ == "__main__":
    unittest.main()
