import io
import unittest

from peacock.compiler.pipeline import compile_source
from peacock.runtime.disasm import disassemble
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM
from tests.support import compile_ok, run_source


class FinallyExecutionTests(unittest.TestCase):
    def test_normal_throw_and_catch_paths(self):
        source = """
        कार्य मुख्य() -> एकक {
            यत्न { मुद्रय("normal"); } अन्ते { मुद्रय("normal cleanup"); }
            यत्न { क्षिप "bad"; }
            गृह्ण(दोष) { मुद्रय("catch " + दोष); }
            अन्ते { मुद्रय("catch cleanup"); }
            यत्न {
                यत्न { क्षिप "rethrow"; } अन्ते { मुद्रय("throw cleanup"); }
            } गृह्ण(दोष) { मुद्रय("outer " + दोष); }
        }
        """
        self.assertEqual(
            run_source(source)[0].splitlines(),
            ["normal", "normal cleanup", "catch bad", "catch cleanup", "throw cleanup", "outer rethrow"],
        )

    def test_return_runs_finally_before_returning_value(self):
        source = """
        कार्य मूल्य() -> अक्षरमाला {
            यत्न { प्रत्यानय "result"; } अन्ते { मुद्रय("cleanup"); }
        }
        कार्य मुख्य() -> एकक { मुद्रय(मूल्य()); }
        """
        self.assertEqual(run_source(source)[0].splitlines(), ["cleanup", "result"])

    def test_break_and_continue_run_finally_once(self):
        source = """
        कार्य मुख्य() -> एकक {
            प्रति i मध्ये ०..४ {
                यत्न {
                    यदि i == ० { अनुवर्तय; }
                    यदि i == ३ { विच्छिन्दु; }
                    मुद्रय("body " + पाठ्यीकरण(i));
                } अन्ते {
                    मुद्रय("cleanup " + पाठ्यीकरण(i));
                }
            }
        }
        """
        self.assertEqual(
            run_source(source)[0].splitlines(),
            ["cleanup 0", "body 1", "cleanup 1", "body 2", "cleanup 2", "cleanup 3"],
        )

    def test_nested_cleanup_and_internal_branch_preserve_original_error(self):
        source = """
        कार्य मुख्य() -> एकक {
            यत्न {
                यत्न { क्षिप "original"; }
                अन्ते {
                    यदि सत्य { मुद्रय("outer cleanup"); }
                    यत्न { मुद्रय("nested"); }
                    अन्ते { मुद्रय("nested cleanup"); }
                }
            } गृह्ण(दोष) { मुद्रय("caught " + दोष); }
        }
        """
        for optimize in (False, True):
            with self.subTest(optimize=optimize):
                result = compile_source(source, optimize_ir=optimize)
                self.assertTrue(result.ok, result.diagnostics.render_all(source))
                output = io.StringIO()
                VM(result.image, HostPolicy(), stdout=output).run()
                self.assertEqual(
                    output.getvalue().splitlines(),
                    ["outer cleanup", "nested", "nested cleanup", "caught original"],
                )

    def test_new_cleanup_error_supersedes_original(self):
        source = """
        कार्य मुख्य() -> एकक {
            यत्न {
                यत्न { क्षिप "first"; } अन्ते { क्षिप "second"; }
            } गृह्ण(दोष) { मुद्रय(दोष); }
            यत्न {
                यत्न { क्षिप "body"; }
                गृह्ण(दोष) { क्षिप "catch"; }
                अन्ते { मुद्रय("cleanup after catch failure"); }
            } गृह्ण(दोष) { मुद्रय(दोष); }
        }
        """
        self.assertEqual(run_source(source)[0].splitlines(), ["second", "cleanup after catch failure", "catch"])

    def test_return_in_inner_cleanup_still_unwinds_outer_finally(self):
        source = """
        कार्य मूल्य() -> अक्षरमाला {
            यत्न {
                यत्न { प्रत्यानय "first"; }
                अन्ते { मुद्रय("inner"); प्रत्यानय "second"; }
            } अन्ते { मुद्रय("outer"); }
        }
        कार्य मुख्य() -> एकक { मुद्रय(मूल्य()); }
        """
        self.assertEqual(run_source(source)[0].splitlines(), ["inner", "outer", "second"])

    def test_verified_bytecode_and_disassembly(self):
        source = 'कार्य मुख्य() -> एकक { यत्न { मुद्रय("x"); } अन्ते { मुद्रय("y"); } }'
        image = compile_ok(source).image
        opcodes = {instruction[0] for instruction in image["functions"]["main"]["code"]}
        self.assertTrue({"FINALLY_BEGIN", "FINALLY_END", "FINALLY_RESUME"} <= opcodes)
        rendered = disassemble(image)
        self.assertIn("FINALLY_BEGIN FINALLY_", rendered)
        self.assertIn("FINALLY_END END_FINALLY_", rendered)

    def test_try_requires_catch_or_finally(self):
        source = 'कार्य मुख्य() -> एकक { यत्न { मुद्रय("x"); } }'
        result = compile_source(source)
        self.assertFalse(result.ok)
        self.assertIn("expected 'गृह्ण' or 'अन्ते'", result.diagnostics.render_all(source))


if __name__ == "__main__":
    unittest.main()
