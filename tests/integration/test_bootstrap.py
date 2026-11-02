import unittest
from pathlib import Path

from peacock.tools.bootstrap import bootstrap

class BootstrapTests(unittest.TestCase):
    def test_python_fixed_point(self):
        summary = bootstrap(check_peacock=False, write=False, verbose=False)
        self.assertEqual(summary["programs"], 10, "expected 10 selfhost kernels")
        self.assertTrue(summary["python_fixed_point"], "Python pipeline must be deterministic")
        # Each selfhost program must compile to >1000 instrs and fixed-point
        for entry in summary["results"]:
            self.assertTrue(entry["fixed_point"], f'{entry["program"]} fixed-point failed')
            self.assertGreater(entry["instructions"], 1000)
            self.assertGreater(entry["bytes"], 1000)

    def test_peacock_lenient_parity(self):
        summary = bootstrap(check_peacock=True, write=False, verbose=False)
        self.assertTrue(summary["peacock_lenient"], "PEACOCK pipeline lenient parity must hold")
        for entry in summary["results"]:
            self.assertTrue(entry["lenient_match"], f'{entry["program"]} peacock lenient failed')

    def test_artifact_roundtrip(self):
        from peacock.runtime.artifact import image_to_bytes, image_from_bytes
        from peacock.compiler.pipeline import compile_source
        src = Path("selfhost/vm.सूत्र").read_text(encoding="utf-8")
        res = compile_source(src, "selfhost/vm.सूत्र")
        self.assertTrue(res.ok)
        b = image_to_bytes(res.image)
        img2 = image_from_bytes(b)
        b2 = image_to_bytes(img2)
        self.assertEqual(b, b2, "artifact round-trip must be deterministic")

if __name__ == "__main__":
    unittest.main()
