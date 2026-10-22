import copy
import json
import tempfile
import unittest
from pathlib import Path

import peacock
from peacock.compiler.bytecode import BytecodeError, verify_image
from peacock.compiler.pipeline import compile_source, parse_source
from peacock.runtime.artifact import (
    ArtifactFormatError,
    artifact_fingerprint,
    image_from_bytes,
    image_to_bytes,
    load_image,
    save_image,
)
from peacock.runtime.disasm import disassemble
from tests.support import REPO_ROOT, compile_ok, run_source


EXAMPLES = [
    "hello.सूत्र",
    "tour.सूत्र",
    "tensors.सूत्र",
    "motion.सूत्र",
    "xor.सूत्र",
    "spiral.सूत्र",
    "aurora.सूत्र",
    "present.सूत्र",
]


def compile_example(name):
    path = REPO_ROOT / "examples" / name
    return compile_source(path.read_text(encoding="utf-8"), str(path)), path


class CompilationTests(unittest.TestCase):
    def test_all_examples_compile(self):
        for name in EXAMPLES:
            result, path = compile_example(name)
            self.assertTrue(result.ok, f"{name}: {result.diagnostics.render_all(path.read_text())}")
            self.assertGreater(result.stats["instructions"], 0)
            verify_image(result.image)

    def test_selfhost_programs_compile(self):
        programs = sorted((REPO_ROOT / "selfhost").glob("*.सूत्र"))
        self.assertGreaterEqual(len(programs), 2)
        for path in programs:
            source = path.read_text(encoding="utf-8")
            result = compile_source(source, str(path))
            self.assertTrue(result.ok, result.diagnostics.render_all(source))
            self.assertGreater(result.stats["instructions"], 1000)

    def test_pipeline_stats(self):
        source = 'कार्य मुख्य() -> एकक { मुद्रय("hi"); }'
        result = compile_ok(source)
        for key in ("tokens", "lex_ms", "parse_ms", "semantic_ms", "ir_ms", "bytecode_ms", "total_ms", "functions", "instructions"):
            self.assertIn(key, result.stats)
        self.assertGreaterEqual(result.stats["total_ms"], 0.0)
        self.assertEqual(result.image["language_version"], peacock.LANGUAGE_VERSION)
        self.assertEqual(result.image["compiler_version"], peacock.__version__)

    def test_compile_is_deterministic(self):
        source = (REPO_ROOT / "examples" / "tour.सूत्र").read_text(encoding="utf-8")
        first = compile_source(source, "tour.सूत्र")
        second = compile_source(source, "tour.सूत्र")
        self.assertEqual(image_to_bytes(first.image), image_to_bytes(second.image))
        self.assertEqual(first.stats["instructions"], second.stats["instructions"])

    def test_optimized_and_unoptimized_programs_agree(self):
        source = """
        कार्य fib(n: पूर्णाङ्क) -> पूर्णाङ्क {
            यदि n < 2 { प्रत्यानय n; }
            प्रत्यानय fib(n - 1) + fib(n - 2);
        }
        कार्य मुख्य() -> एकक {
            स्थापय परिवर्तनीय i = 0;
            स्थापय परिवर्तनीय total = 0;
            यावत् i < 10 { total += fib(i); i += 1; }
            मुद्रय(पाठ्यीकरण(total));
            यदि 1 + 2 * 3 == 7 { मुद्रय("folded"); }
        }
        """
        out_opt, _, _ = run_source(source)
        result = compile_source(source, "fib.सूत्र", optimize_ir=False)
        self.assertTrue(result.ok)
        import io
        from peacock.runtime.host import HostPolicy
        from peacock.runtime.vm import VM

        buffer = io.StringIO()
        VM(result.image, HostPolicy(root=str(REPO_ROOT)), stdout=buffer).run()
        self.assertEqual(out_opt, buffer.getvalue())
        self.assertIn("folded", out_opt)

    def test_parse_source_helper(self):
        module, diagnostics, tokens = parse_source('प्रकरण m\nकार्य मुख्य() -> एकक { }')
        self.assertFalse(diagnostics.has_errors)
        self.assertEqual(module.name, "m")
        self.assertGreater(len(tokens), 1)

    def test_static_error_prevents_image(self):
        result = compile_source('कार्य मुख्य() -> एकक { स्थापय क्ष = missing; }')
        self.assertFalse(result.ok)
        self.assertIsNone(result.image)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.result = compile_ok((REPO_ROOT / "examples" / "hello.सूत्र").read_text(encoding="utf-8"))

    def test_roundtrip(self):
        blob = image_to_bytes(self.result.image)
        restored = image_from_bytes(blob)
        self.assertEqual(restored, self.result.image)
        self.assertEqual(image_to_bytes(restored), blob)

    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hello.बीज"
            size = save_image(self.result.image, str(path))
            self.assertEqual(size, path.stat().st_size)
            loaded = load_image(str(path))
            self.assertEqual(loaded, self.result.image)

    def test_fingerprint_is_stable_and_content_sensitive(self):
        a = artifact_fingerprint(self.result.image)
        b = artifact_fingerprint(copy.deepcopy(self.result.image))
        self.assertEqual(a, b)
        changed = copy.deepcopy(self.result.image)
        changed["module"] = "changed"
        self.assertNotEqual(a, artifact_fingerprint(changed))

    def test_tampered_payload_is_rejected(self):
        blob = bytearray(image_to_bytes(self.result.image))
        blob[30] ^= 0xFF
        with self.assertRaises(ArtifactFormatError):
            image_from_bytes(bytes(blob))

    def test_truncated_artifact_is_rejected(self):
        blob = image_to_bytes(self.result.image)
        with self.assertRaises(ArtifactFormatError):
            image_from_bytes(blob[:-5])

    def test_bad_magic_is_rejected(self):
        blob = b"NOTPEACOCK" + image_to_bytes(self.result.image)[8:]
        with self.assertRaises(ArtifactFormatError):
            image_from_bytes(blob)

    def test_json_payload_without_verification_is_checked(self):
        bad = copy.deepcopy(self.result.image)
        bad["functions"]["main"]["code"][0] = ["NOT_AN_OPCODE"]
        blob = image_to_bytes(bad)  # container is valid; image itself is not
        with self.assertRaises(BytecodeError):
            image_from_bytes(blob)


class BytecodeValidationTests(unittest.TestCase):
    def setUp(self):
        source = """
        कार्य add(अ: पूर्णाङ्क, ब: पूर्णाङ्क) -> पूर्णाङ्क { प्रत्यानय अ + ब; }
        कार्य मुख्य() -> एकक { स्थापय क्ष = add(1, 2); मुद्रय(पाठ्यीकरण(क्ष)); }
        """
        self.image = compile_ok(source).image

    def assert_invalid(self, mutate, fragment=None):
        bad = copy.deepcopy(self.image)
        mutate(bad)
        with self.assertRaises(BytecodeError) as ctx:
            verify_image(bad)
        if fragment:
            self.assertIn(fragment, str(ctx.exception))

    def test_valid_image(self):
        verify_image(self.image)

    def test_unknown_opcode(self):
        self.assert_invalid(lambda img: img["functions"]["main"]["code"].__setitem__(0, ["FLY"]), "unknown opcode")

    def test_slot_out_of_range(self):
        def mutate(img):
            img["functions"]["main"]["code"][0] = ["STORE_SLOT", 9999]
        self.assert_invalid(mutate, "slot out of range")

    def test_bad_jump_target(self):
        def mutate(img):
            img["functions"]["main"]["code"][0] = ["JUMP", 9999]
        self.assert_invalid(mutate, "jump target")

    def test_unknown_native(self):
        def mutate(img):
            img["functions"]["main"]["code"][0] = ["CALL_NATIVE", "system.exec", 0]
        self.assert_invalid(mutate, "unknown native")

    def test_call_arity_mismatch(self):
        def mutate(img):
            for instr in img["functions"]["main"]["code"]:
                if instr[0] == "CALL":
                    instr[2] = 0
        self.assert_invalid(mutate, "calls")

    def test_unknown_capability(self):
        self.assert_invalid(lambda img: img["functions"]["main"].__setitem__("caps", ["root"]), "capabilities")

    def test_missing_function_key(self):
        self.assert_invalid(lambda img: img["functions"]["main"].pop("slots"), "missing")

    def test_missing_main_still_valid_image_but_not_runnable(self):
        image = copy.deepcopy(self.image)
        image["functions"].pop("main")
        verify_image(image)  # structural validity only
        from peacock.runtime.vm import VM
        from peacock.runtime.host import HostPolicy
        from peacock.compiler.diagnostics import RuntimeError_

        with self.assertRaises(RuntimeError_):
            VM(image, HostPolicy()).run()


class DisassemblyTests(unittest.TestCase):
    def test_disassembly_contains_functions_and_models(self):
        path = REPO_ROOT / "examples" / "xor.सूत्र"
        result = compile_source(path.read_text(encoding="utf-8"), str(path))
        text = disassemble(result.image)
        self.assertIn("function मुख्य", text)
        self.assertIn("models:", text)
        self.assertIn("XorNet", text)
        self.assertIn("दशमलव३२", text)
        self.assertIn("सघन(8,धनाङ्क)", text)
        self.assertIn("training declarations:", text)
        self.assertIn("उद्देश्य='अन्तरएन्ट्रॉपी'", text)
        self.assertIn("अनुकूलक='आदम'", text)
        self.assertIn("CALL_NATIVE 'मुद्रय'", text)
        self.assertIn("capabilities=गणना", text)

    def test_disassembly_resolves_jump_labels(self):
        source = 'कार्य मुख्य() -> एकक { स्थापय परिवर्तनीय i = 0; यावत् i < 3 { i += 1; } }'
        image = compile_ok(source).image
        text = disassemble(image)
        self.assertIn("L_", text)
        self.assertNotRegex(text, r"JUMP \d+")

    def test_image_is_json_serialisable(self):
        image = compile_ok('कार्य मुख्य() -> एकक { मुद्रय("x"); }').image
        roundtrip = json.loads(json.dumps(image))
        verify_image(roundtrip)


if __name__ == "__main__":
    unittest.main()
