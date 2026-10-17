import unittest

import peacock
from peacock.compiler.tokens import KNOWN_CAPABILITIES, KNOWN_NAMESPACES, RESERVED_FUTURE
from peacock.compiler import builtins


class VersionTests(unittest.TestCase):
    def test_package_metadata(self):
        self.assertEqual(peacock.__version__, "0.1.0")
        self.assertEqual(peacock.LANGUAGE_VERSION, "0.1")
        self.assertEqual(peacock.__codename__, "Fledgling")

    def test_capabilities_are_documented_and_small(self):
        self.assertEqual(set(KNOWN_CAPABILITIES), {"compute", "fs", "ui"})
        self.assertEqual(set(builtins.NAMESPACES), set(KNOWN_NAMESPACES) | {"text", "process", "fs"})

    def test_reserved_future_keywords(self):
        self.assertIn("match", RESERVED_FUTURE)
        self.assertIn("async", RESERVED_FUTURE)
        self.assertIn("impl", RESERVED_FUTURE)

    def test_every_native_has_a_signature_and_doc(self):
        missing = [name for name in builtins.NATIVES if name not in builtins.NATIVE_DOCS]
        self.assertEqual(missing, [])
        for name, signatures in builtins.NATIVES.items():
            self.assertTrue(signatures, name)
            for signature in signatures:
                self.assertTrue(signature.capability is None or signature.capability in KNOWN_CAPABILITIES)


if __name__ == "__main__":
    unittest.main()
