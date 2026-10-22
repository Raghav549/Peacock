import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from peacock.cli import main as cli_main
from peacock.compiler.diagnostics import CapabilityError
from peacock.frontend.png import decode_png
from tests.support import compile_ok, read_example, run_example, run_source


class AdvancedExampleTests(unittest.TestCase):
    def test_vyakarana_example(self):
        output, _outcome, _vm, result = run_example("vyakarana.सूत्र")
        self.assertIn("1.1.1 वृद्धिरादैच्", output)
        self.assertIn("रामेन्द्रः\nनद्यत्र\nमहर्षिः", output)
        self.assertIn("sūtra texts: 3983", output)
        self.assertIn("executable sandhi rules: 4", output)
        self.assertEqual(list(result.diagnostics), [])

    def test_colour_lab_example(self):
        output, _outcome, _vm, result = run_example("colour_lab.सूत्र")
        self.assertIn("oklab: rgb(81 71 210)", output)
        self.assertIn("subtractive: rgb(0 0 0)", output)
        self.assertIn("gamut: rgb(255 101 81)", output)
        self.assertEqual(list(result.diagnostics), [])

    def test_agent_example_and_compute_denial(self):
        output, _outcome, _vm, result = run_example("agents.सूत्र", grants=("compute",))
        self.assertIn("plan: द्वारं गच्छ → गृहं प्रविश", output)
        self.assertIn("rule=1", output)
        self.assertEqual(list(result.diagnostics), [])
        with self.assertRaises(CapabilityError):
            run_example("agents.सूत्र")

    def test_ui_example_exports_accessible_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = read_example("ui_builder.सूत्र").replace("examples/out/ui.html", "ui.html")
            output, _outcome, _vm = run_source(source, grants=("fs",), root=tmp)
            self.assertIn("UI nodes: 4", output)
            html = (Path(tmp) / "ui.html").read_text(encoding="utf-8")
            self.assertIn("संस्कृतं स्वाभाविकम्", html)
            self.assertIn('lang="sa"', html)
            self.assertNotIn("<script", html)

    def test_scene3d_example_exports_real_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = read_example("scene3d.सूत्र").replace("examples/out/scene3d.png", "scene.png")
            output, _outcome, _vm = run_source(source, grants=("fs",), root=tmp)
            self.assertIn("3D triangles: 588", output)
            width, height, pixels = decode_png((Path(tmp) / "scene.png").read_bytes())
            self.assertEqual((width, height), (320, 200))
            self.assertEqual(len(pixels), 320 * 200 * 4)
            self.assertGreater(len(set(pixels)), 100)


class SanskritNativeSurfaceTests(unittest.TestCase):
    def test_named_arguments_and_opaque_type_displays(self):
        source = """
        उपयोग व्याकरण
        उपयोग रङ्ग
        उपयोग दृश्य
        उपयोग त्रिअयाम
        उपयोग अभिकर्तृ
        कार्य मुख्य() -> एकक {
            स्थापय परिणाम = व्याकरण.अन्वेषय(अन्वेषण: "वृद्धिरादैच्", अवधि: १);
            निश्चिनु दैर्घ्य(परिणाम) == १;
            स्थापय रक्त = रङ्ग.षोडशात्("#ff0000");
            स्थापय नील = रङ्ग.षोडशात्("#0000ff");
            स्थापय मिश्र = रङ्ग.बहुमिश्रय(वर्णावलीः: [रक्त, नील], भारावली: [१.०, १.०], वर्णावकाश: "ओकलैब");
            निश्चिनु रङ्ग.वर्णान्तर(मिश्र, मिश्र) == ०.०;
            स्थापय रचना = दृश्य.सृज(शीर्षक: "मयूर", विस्तार: ६४, औन्नत्य: ६४, पृष्ठवर्ण: रक्त);
            निश्चिनु प्रकारनाम(रचना) == "दृश्यरचना";
            स्थापय दृश्य = त्रिअयाम.सृज();
            निश्चिनु प्रकारनाम(दृश्य) == "त्रिअयामदृश्य";
            स्थापय कर्ता = अभिकर्तृ.सृज(लक्ष्यसूची: "स्थिति", लक्ष्यमूल्य: "सिद्ध", अधिकतमचरण: ४);
            निश्चिनु प्रकारनाम(कर्ता) == "अभिकर्तृप्रकार";
        }
        """
        output, _outcome, _vm = run_source(source)
        self.assertEqual(output, "")


class VyakaranaCommandTests(unittest.TestCase):
    def test_sanskrit_cli_operations(self):
        cases = [
            (["व्याकरण", "सूत्र", "1.1.1"], "1.1.1 वृद्धिरादैच्"),
            (["व्याकरण", "प्रत्याहार", "यण्"], "य व र ल"),
            (["व्याकरण", "संधि", "नदी", "अत्र"], "नद्यत्र — 6.1.77"),
            (["व्याकरण", "आच्छादन"], "sūtra texts: 3983"),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = cli_main(argv)
                self.assertEqual(code, 0)
                self.assertIn(expected, stdout.getvalue())

    def test_cli_grammar_error_is_controlled(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = cli_main(["व्याकरण", "सूत्र", "9.9.9"])
        self.assertEqual(code, 1)
        self.assertIn("unknown Aṣṭādhyāyī sūtra", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
