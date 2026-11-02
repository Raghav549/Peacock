import tempfile
import unittest
from pathlib import Path

from peacock.compiler.pipeline import compile_source


class ModuleImportTests(unittest.TestCase):
    def test_single_file_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "सहायक.सूत्र").write_text(
                "प्रकरण सहायक\nकार्य वर्ग(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ * अ; }\n",
                encoding="utf-8",
            )
            main_src = "प्रकरण मुख्य\nउपयोग सहायक\nकार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(वर्ग(५))); }"
            result = compile_source(main_src, str(tmp / "main.सूत्र"))
            self.assertTrue(result.ok, result.diagnostics.render_all(main_src))
            self.assertIn("modules_loaded", result.stats)

    def test_nested_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "क.सूत्र").write_text(
                "प्रकरण क\nकार्य योग(अ: पूर्णाङ्क, ब: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ + ब; }",
                encoding="utf-8",
            )
            (tmp / "ख.सूत्र").write_text(
                "प्रकरण ख\nउपयोग क\nकार्य द्विगुण(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय योग(अ, अ); }",
                encoding="utf-8",
            )
            main_src = "प्रकरण मुख्य\nउपयोग ख\nकार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(द्विगुण(७))); }"
            result = compile_source(main_src, str(tmp / "main.सूत्र"))
            self.assertTrue(result.ok, result.diagnostics.render_all(main_src))

    def test_unknown_module_error(self):
        src = "प्रकरण मुख्य\nउपयोग अज्ञातमापांक\nकार्य मुख्य() -> एकक {}"
        result = compile_source(src, "<source>")
        self.assertFalse(result.ok)
        self.assertTrue(any("unknown module" in d.message for d in result.diagnostics.errors()))

    def test_circular_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "अ.सूत्र").write_text("प्रकरण अ\nउपयोग ब\nकार्य foo() -> पूर्णाङ्क { प्रत्यानय १; }", encoding="utf-8")
            (tmp / "ब.सूत्र").write_text("प्रकरण ब\nउपयोग अ\nकार्य bar() -> पूर्णाङ्क { प्रत्यानय २; }", encoding="utf-8")
            main_src = "प्रकरण मुख्य\nउपयोग अ\nकार्य मुख्य() -> एकक {}"
            result = compile_source(main_src, str(tmp / "main.सूत्र"))
            self.assertFalse(result.ok)
            self.assertTrue(any("circular" in d.message for d in result.diagnostics.errors()))

    def test_builtin_still_works_with_file_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "सहायक.सूत्र").write_text("प्रकरण सहायक\nकार्य वर्ग(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ * अ; }", encoding="utf-8")
            src = "प्रकरण मुख्य\nउपयोग सहायक\nउपयोग तन्त्रजाल\nकार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(वर्ग(३))); }"
            result = compile_source(src, str(tmp / "main.सूत्र"))
            self.assertTrue(result.ok, result.diagnostics.render_all(src))

    def test_qualified_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "सहायक.सूत्र").write_text(
                "प्रकरण सहायक\nकार्य वर्ग(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ * अ; }\nकार्य घन(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ * अ * अ; }\nसंघटन बिन्दु { क्ष: पूर्णाङ्क य: पूर्णाङ्क }",
                encoding="utf-8",
            )
            src = "प्रकरण मुख्य\nउपयोग सहायक\nकार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(सहायक.वर्ग(५))); मुद्रय(पाठ्यीकरण(सहायक.घन(३))); स्थापय ब = सहायक.बिन्दु(१,२); मुद्रय(पाठ्यीकरण(ब.क्ष)); }"
            result = compile_source(src, str(tmp / "main.सूत्र"))
            self.assertTrue(result.ok, result.diagnostics.render_all(src))

    def test_file_alias_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "सहायक.सूत्र").write_text(
                "प्रकरण सहायक\nकार्य वर्ग(अ: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ * अ; }",
                encoding="utf-8",
            )
            src = "प्रकरण मुख्य\nउपयोग सहायक रूपेण S\nकार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(S.वर्ग(५))); }"
            result = compile_source(src, str(tmp / "main.सूत्र"))
            self.assertTrue(result.ok, result.diagnostics.render_all(src))
            src2 = "प्रकरण मुख्य\nउपयोग सहायक रूपेण S\nकार्य मुख्य() -> एकक { मुद्रय(पाठ्यीकरण(सहायक.वर्ग(५))); }"
            result2 = compile_source(src2, str(tmp / "main.सूत्र"))
            self.assertFalse(result2.ok)

    def test_builtin_alias_import(self):
        src = "प्रकरण मुख्य\nउपयोग गणित रूपेण g\nकार्य मुख्य() -> एकक { स्थापय x = g.वर्गमूल(४.०); मुद्रय(x); }"
        result = compile_source(src, "<source>")
        self.assertTrue(result.ok, result.diagnostics.render_all(src))
        src2 = "प्रकरण मुख्य\nउपयोग गणित रूपेण g\nकार्य मुख्य() -> एकक { स्थापय x = गणित.वर्गमूल(४.०); }"
        result2 = compile_source(src2, "<source>")
        self.assertFalse(result2.ok)


if __name__ == "__main__":
    unittest.main()
