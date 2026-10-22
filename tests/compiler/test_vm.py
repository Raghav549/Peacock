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
            कार्य मुख्य() -> एकक {
                मुद्रय(पाठ्यीकरण(7 + 3));
                मुद्रय(पाठ्यीकरण(7 - 3));
                मुद्रय(पाठ्यीकरण(7 * 3));
                मुद्रय(पाठ्यीकरण(7 / 3));
                मुद्रय(पाठ्यीकरण(-7 / 3));
                मुद्रय(पाठ्यीकरण(-7 % 3));  // truncated division: remainder keeps the dividend's sign
                मुद्रय(पाठ्यीकरण(2 ** 10));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["10", "4", "21", "2", "-2", "-1", "1024"])

    def test_float_arithmetic(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                मुद्रय(पाठ्यीकरण(1.5 + 2.25));
                मुद्रय(पाठ्यीकरण(3.0 * 2.0));
                मुद्रय(पाठ्यीकरण(1.0 / 4.0));
                मुद्रय(पाठ्यीकरण(2.0 ** 3.0));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["3.75", "6.0", "0.25", "8.0"])

    def test_division_by_zero(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { स्थापय क्ष = 1 / 0; }')
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4005")

    def test_integer_overflow(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { स्थापय क्ष = 9223372036854775807 + 1; }')
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4004")

    def test_power_overflow(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { स्थापय क्ष = 2 ** 63; }')
        with self.assertRaises(VMFault):
            vm.run()

    def test_float_zero_division(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { स्थापय क्ष = 1.0 / 0.0; }')
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4005")


class ControlFlowTests(unittest.TestCase):
    def test_if_else(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय n = 5;
                यदि n > 10 { मुद्रय("big"); } अन्यथा यदि n > 3 { मुद्रय("medium"); } अन्यथा { मुद्रय("small"); }
            }
            """
        )
        self.assertEqual(out.strip(), "medium")

    def test_while_break_continue(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय परिवर्तनीय i = 0;
                स्थापय परिवर्तनीय total = 0;
                यावत् i < 20 {
                    i += 1;
                    यदि i % 2 == 0 { अनुवर्तय; }
                    यदि i > 9 { विच्छिन्दु; }
                    total += i;
                }
                मुद्रय(पाठ्यीकरण(total));
                मुद्रय(पाठ्यीकरण(i));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["25", "11"])

    def test_range_for(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय परिवर्तनीय total = 0;
                प्रति i मध्ये 0..5 { total += i; }
                मुद्रय(पाठ्यीकरण(total));
            }
            """
        )
        self.assertEqual(out.strip(), "10")

    def test_list_for(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय xs = [2, 3, 5, 7];
                स्थापय परिवर्तनीय product = 1;
                प्रति क्ष मध्ये xs { product *= क्ष; }
                मुद्रय(पाठ्यीकरण(product));
            }
            """
        )
        self.assertEqual(out.strip(), "210")

    def test_short_circuit_evaluation(self):
        out, _, _ = run_source(
            """
            कार्य boom() -> सत्यता { क्षिप "must not run"; }
            कार्य मुख्य() -> एकक {
                स्थापय अ = असत्य तथा boom();
                स्थापय ब = सत्य वा boom();
                मुद्रय(पाठ्यीकरण(अ));
                मुद्रय(पाठ्यीकरण(ब));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["असत्य", "सत्य"])

    def test_scoping_and_shadowing(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय क्ष = 1;
                यदि सत्य { स्थापय क्ष = 2; मुद्रय(पाठ्यीकरण(क्ष)); }
                मुद्रय(पाठ्यीकरण(क्ष));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["2", "1"])

    def test_recursion(self):
        out, _, _ = run_source(
            """
            कार्य fact(n: पूर्णाङ्क) -> पूर्णाङ्क { यदि n <= 1 { प्रत्यानय 1; } प्रत्यानय n * fact(n - 1); }
            कार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(fact(10))); }
            """
        )
        self.assertEqual(out.strip(), "3628800")

    def test_call_depth_limit(self):
        vm, _ = make_vm(
            'कार्य f(n: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय f(n + 1); }\n'
            'कार्य मुख्य() -> एकक { स्थापय क्ष = f(0); }',
            max_call_depth=16,
        )
        with self.assertRaises(ResourceLimitError) as ctx:
            vm.run()
        self.assertIn("call depth", str(ctx.exception))

    def test_step_limit(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { यावत् सत्य { } }', max_steps=500)
        with self.assertRaises(ResourceLimitError) as ctx:
            vm.run()
        self.assertIn("step limit", str(ctx.exception))

    def test_output_limit(self):
        vm, _ = make_vm(
            'कार्य मुख्य() -> एकक { मुद्रय("123456"); मुद्रय("123456"); }',
            max_output_chars=8,
        )
        with self.assertRaises(ResourceLimitError):
            vm.run()


class CollectionTests(unittest.TestCase):
    def test_list_methods(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय परिवर्तनीय xs: सूची<पूर्णाङ्क> = [];
                xs.योजय(3); xs.योजय(1); xs.योजय(2);
                मुद्रय(पाठ्यीकरण(xs));
                मुद्रय(पाठ्यीकरण(xs.प्राप्नु(1)));
                मुद्रय(पाठ्यीकरण(xs.दैर्घ्य()));
                मुद्रय(पाठ्यीकरण(xs.अन्तर्भूत(2)));
                मुद्रय(पाठ्यीकरण(xs.सूचकाङ्क(9)));
                xs.क्रमय(); मुद्रय(पाठ्यीकरण(xs));
                xs.विपर्यय(); मुद्रय(पाठ्यीकरण(xs));
                xs[0] = 42; मुद्रय(पाठ्यीकरण(xs));
                मुद्रय(पाठ्यीकरण(xs.निष्कासय()));
            }
            """
        )
        self.assertEqual(
            out.splitlines(),
            ["[3, 1, 2]", "1", "3", "सत्य", "-1", "[1, 2, 3]", "[3, 2, 1]", "[42, 2, 1]", "1"],
        )

    def test_list_bounds(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { स्थापय xs = [1]; स्थापय क्ष = xs.प्राप्नु(5); }')
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertIn("out of bounds", str(ctx.exception))

    def test_index_assignment(self):
        out, _, _ = run_source(
            'कार्य मुख्य() -> एकक { स्थापय xs = [1, 2, 3]; xs[1] = 9; मुद्रय(पाठ्यीकरण(xs)); }'
        )
        self.assertEqual(out.strip(), "[1, 9, 3]")

    def test_string_methods(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                मुद्रय("  Peacock  ".शोधय());
                मुद्रय("abc".बृहदक्षर());
                मुद्रय("ABC".लघ्वक्षर());
                मुद्रय("abc".उपपाठ्य(1, 3));
                मुद्रय(पाठ्यीकरण("a,b,c".विभाजय(",")));
                मुद्रय(पाठ्यीकरण("abc".आरम्भयुक्त("ab")));
                मुद्रय(पाठ्यीकरण("abc".अन्तयुक्त("bc")));
                मुद्रय("abc".प्रतिस्थापय("b", "X"));
                मुद्रय(पाठ्यीकरण(दैर्घ्य("hello")));
                मुद्रय("hello"[1]);
            }
            """
        )
        self.assertEqual(
            out.splitlines(),
            ["Peacock", "ABC", "abc", "bc", '["a", "b", "c"]', "सत्य", "सत्य", "aXc", "5", "e"],
        )

    def test_substring_bounds(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { मुद्रय("abc".उपपाठ्य(2, 9)); }')
        with self.assertRaises(VMFault):
            vm.run()

    def test_string_index_bounds(self):
        vm, _ = make_vm('कार्य मुख्य() -> एकक { मुद्रय("abc"[5]); }')
        with self.assertRaises(VMFault):
            vm.run()


class StructTests(unittest.TestCase):
    def test_struct_construction_and_mutation(self):
        out, _, _ = run_source(
            """
            संघटन Point { क्ष: पूर्णाङ्क, य: पूर्णाङ्क }
            कार्य length_squared(p: Point) -> पूर्णाङ्क { प्रत्यानय p.क्ष * p.क्ष + p.य * p.य; }
            कार्य मुख्य() -> एकक {
                स्थापय p = Point(3, 4);
                मुद्रय(पाठ्यीकरण(length_squared(p)));
                p.क्ष = 6;
                मुद्रय(पाठ्यीकरण(p.क्ष));
                मुद्रय(प्रकारनाम(p));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["25", "6", "Point"])


class ErrorHandlingTests(unittest.TestCase):
    def test_throw_and_catch(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                यत्न { क्षिप "boom"; } गृह्ण (सन्देश) { मुद्रय("caught: " + सन्देश); }
                मुद्रय("continues");
            }
            """
        )
        self.assertEqual(out.splitlines(), ["caught: boom", "continues"])

    def test_runtime_error_can_be_caught(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                यत्न { स्थापय क्ष = 1 / 0; मुद्रय(पाठ्यीकरण(क्ष)); }
                गृह्ण (सन्देश) { मुद्रय("error: " + सन्देश); }
            }
            """
        )
        self.assertEqual(out.strip(), "error: division by zero")

    def test_nested_try_rethrow(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                यत्न {
                    यत्न { क्षिप "inner"; } गृह्ण (घाताधार) { क्षिप "outer:" + घाताधार; }
                } गृह्ण (final) { मुद्रय(final); }
            }
            """
        )
        self.assertEqual(out.strip(), "outer:inner")

    def test_uncaught_error_has_stack_trace(self):
        vm, _ = make_vm(
            """
            कार्य divide() -> पूर्णाङ्क { प्रत्यानय 10 / 0; }
            कार्य middle() -> पूर्णाङ्क { प्रत्यानय divide(); }
            कार्य मुख्य() -> एकक { स्थापय क्ष = middle(); }
            """
        )
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        text = format_error(ctx.exception)
        self.assertIn("at divide", text)
        self.assertIn("at middle", text)
        self.assertIn("at मुख्य", text)
        self.assertIn("line", text)

    def test_assert_success_and_failure(self):
        out, _, _ = run_source(
            'कार्य मुख्य() -> एकक { निश्चिनु(1 + 1 == 2, "math works"); मुद्रय("ok"); }'
        )
        self.assertEqual(out.strip(), "ok")
        vm, _ = make_vm('कार्य मुख्य() -> एकक { निश्चिनु(असत्य, "boom"); }')
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4010")
        self.assertEqual(ctx.exception.message, "boom")


class CapabilityRuntimeTests(unittest.TestCase):
    def test_host_denies_compute(self):
        source = """
        उपयोग तन्त्रजाल
        कार्य मुख्य() -> एकक {
            अधिकार गणना;
            स्थापय w = तन्त्रजाल.प्राचल([1.0, 2.0]);
        }
        """
        vm, _ = make_vm(source, grants=())
        with self.assertRaises(CapabilityError) as ctx:
            vm.run()
        self.assertEqual(ctx.exception.code, "PE4001")
        self.assertIn("host has not granted", str(ctx.exception))

    def test_host_grants_compute(self):
        source = """
        उपयोग तन्त्रजाल
        कार्य मुख्य() -> एकक {
            अधिकार गणना;
            स्थापय w = तन्त्रजाल.प्राचल([1.0, 2.0]);
            मुद्रय(पाठ्यीकरण(w.मान));
        }
        """
        out, _, _ = run_source(source, grants=("compute",))
        self.assertEqual(out.strip(), "2")

    def test_fs_requires_host_grant(self):
        source = """
        उपयोग सञ्चय
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            सञ्चय.पाठ्यलेखन("blocked.txt", "दत्त");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm, _ = make_vm(source, grants=(), root=tmp)
            with self.assertRaises(CapabilityError):
                vm.run()

    def test_fs_roundtrip_in_sandbox(self):
        source = """
        उपयोग सञ्चय
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            सञ्चय.पाठ्यलेखन("notes/hello.txt", "PEACOCK sandbox");
            स्थापय पाठ्य = सञ्चय.पाठ्यपठन("notes/hello.txt");
            मुद्रय(पाठ्य);
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
        उपयोग सञ्चय
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            स्थापय पाठ्य = सञ्चय.पाठ्यपठन("../outside.txt");
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
        उपयोग सञ्चय
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            स्थापय पाठ्य = सञ्चय.पाठ्यपठन("/etc/passwd");
        }
        """
        with tempfile.TemporaryDirectory() as tmp:
            vm, _ = make_vm(source, grants=("fs",), root=tmp)
            with self.assertRaises(HostError):
                vm.run()

    def test_fs_symlink_escape_is_blocked(self):
        source = """
        उपयोग सञ्चय
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            स्थापय पाठ्य = सञ्चय.पाठ्यपठन("link.txt");
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
        उपयोग सञ्चय
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            सञ्चय.पाठ्यलेखन("big.txt", "0123456789ABCDEF");
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
            उपयोग गणित
            कार्य मुख्य() -> एकक {
                मुद्रय(पाठ्यीकरण(गणित.वर्गमूल(9.0)));
                मुद्रय(पाठ्यीकरण(गणित.पूर्णीत(2.5)));
                मुद्रय(पाठ्यीकरण(गणित.सीमित(5.0, 0.0, 1.0)));
                मुद्रय(पाठ्यीकरण(गणित.न्यूनतम(1.0, 2.0)));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["3.0", "3", "1.0", "1.0"])

    def test_math_domain_error(self):
        vm, _ = make_vm('उपयोग गणित\nकार्य मुख्य() -> एकक { स्थापय क्ष = गणित.वर्गमूल(-1.0); }')
        with self.assertRaises(VMFault):
            vm.run()

    def test_text_functions(self):
        out, _, _ = run_source(
            """
            उपयोग पाठ्य
            कार्य मुख्य() -> एकक {
                मुद्रय(पाठ्यीकरण(पाठ्य.वर्णः("A")));
                मुद्रय(पाठ्यीकरण(पाठ्य.अङ्कः("7")));
                मुद्रय(पाठ्यीकरण(पाठ्य.अक्षरसङ्ख्या("A")));
                मुद्रय(पाठ्य.सङ्ख्याक्षर(80) + पाठ्य.सङ्ख्याक्षर(75));
                मुद्रय(पाठ्यीकरण(पाठ्य.पङ्क्तिविभाजन("a\\nb")));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["सत्य", "सत्य", "65", "PK", '["a", "b"]'])

    def test_process_args(self):
        source = 'उपयोग प्रक्रिया\nकार्य मुख्य() -> एकक { मुद्रय(प्रक्रिया.तर्कावली().संयोजय("|")); }'
        out, _, _ = run_source(source, argv=("alpha", "beta"))
        self.assertEqual(out.strip(), "alpha|beta")

    def test_graphics_save_writes_png(self):
        source = """
        उपयोग चित्र
        उपयोग रङ्ग
        कार्य मुख्य() -> एकक {
            अधिकार सञ्चय;
            स्थापय चित्रपट्ट = चित्र.चित्रपट्ट(8, 6);
            चित्र.पूरय(चित्रपट्ट, रङ्ग.एसआरजीबी(1.0, 0.0, 0.0));
            चित्र.रक्ष(चित्रपट्ट, "out/red.png");
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
        vm, _ = make_vm('उपयोग चित्र\nकार्य मुख्य() -> एकक { स्थापय च = चित्र.चित्रपट्ट(0, 0); }')
        with self.assertRaises(VMFault):
            vm.run()

    def test_tensor_methods(self):
        out, _, _ = run_source(
            """
            कार्य मुख्य() -> एकक {
                स्थापय त = आयामीकरण([[1.0, 2.0], [3.0, 4.0]]);
                मुद्रय(पाठ्यीकरण(त.कोटि));
                मुद्रय(पाठ्यीकरण(त.मान));
                मुद्रय(पाठ्यीकरण(त.योग()));
                मुद्रय(पाठ्यीकरण(त.परिवर्त()));
                मुद्रय(पाठ्यीकरण(त.पुनराकृति([4])));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["2", "4", "10.0", "आयाम(दशमलव३२[2, 2], [[1.0, 3.0], [2.0, 4.0]])", "आयाम(दशमलव३२[4], [1.0, 2.0, 3.0, 4.0])"])

    def test_motion_native(self):
        out, _, _ = run_source(
            """
            उपयोग गति
            कार्य मुख्य() -> एकक {
                स्थापय values = गति.स्पृङ्गचरण(0.0, 10.0, 170.0, 26.0, 30, 0.016666666666666666);
                मुद्रय(पाठ्यीकरण(दैर्घ्य(values)));
                मुद्रय(पाठ्यीकरण(गति.गतिशैली("रैखिक", 0.25)));
            }
            """
        )
        self.assertEqual(out.splitlines(), ["31", "0.25"])


class VMLifecycleTests(unittest.TestCase):
    def test_main_must_be_zero_arity(self):
        from tests.support import expect_diagnostic

        expect_diagnostic('कार्य मुख्य(क्ष: पूर्णाङ्क) -> एकक { }', "PE3013", "no parameters")

    def test_main_must_return_unit(self):
        from tests.support import expect_diagnostic

        expect_diagnostic('कार्य मुख्य() -> पूर्णाङ्क { प्रत्यानय 0; }', "PE3013", "एकक")

    def test_missing_main(self):
        result = compile_ok('कार्य helper() -> एकक { }')
        vm = VM(result.image, HostPolicy())
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertIn("no 'मुख्य'", str(ctx.exception))

    def test_invalid_image_rejected(self):
        result = compile_ok('कार्य मुख्य() -> एकक { मुद्रय("x"); }')
        bad = {**result.image}
        bad["functions"] = {}
        with self.assertRaises(ArtifactFormatError):
            VM(bad, HostPolicy())

    def test_uninitialised_slot_guard(self):
        result = compile_ok('कार्य मुख्य() -> एकक { }')
        image = result.image
        code = [["PUSH_SLOT", 0], ["RET", 1]]
        image = {**image, "functions": {**image["functions"], "main": {**image["functions"]["main"], "code": code, "lines": [[1, 1], [1, 1]], "slots": 1}}}
        vm = VM(image, HostPolicy())
        with self.assertRaises(VMFault) as ctx:
            vm.run()
        self.assertIn("uninitialised", str(ctx.exception))

    def test_halt_on_bad_pc(self):
        result = compile_ok('कार्य मुख्य() -> एकक { }')
        image = {**result.image}
        main = {**image["functions"]["main"], "code": [["JUMP", 99]], "lines": [[1, 1]]}
        image["functions"] = {**image["functions"], "main": main}
        with self.assertRaises(ArtifactFormatError):
            VM(image, HostPolicy())


if __name__ == "__main__":
    unittest.main()
