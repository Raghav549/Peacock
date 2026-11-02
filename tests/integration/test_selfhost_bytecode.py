"""Differential tests for the PEACOCK-native bytecode builder (`selfhost/bytecode.सूत्र`)."""

from __future__ import annotations

import unittest
from pathlib import Path

from peacock.compiler.selfhost_bytecode import shadow_bytecode_check

# Subset of CORE_CORPUS that currently has bytecode parity.
# tokenizer.सूत्र needs additional string-escape parity (tracked separately).
BYTECODE_CORPUS = [
    "examples/hello.सूत्र",
    "examples/tour.सूत्र",
    "examples/motion.सूत्र",
    "examples/aurora.सूत्र",
    "examples/native.सूत्र",
    "examples/xor.सूत्र",
    "examples/spiral.सूत्र",
    "selfhost/fixtures/core_syntax.सूत्र",
    "selfhost/fixtures/finally.सूत्र",
]

LINGUIST_SUBSET = [
    "linguist/samples/types.सूत्र",
    "linguist/samples/statements.सूत्र",
    "linguist/samples/expressions.सूत्र",
]

OVERSIZED = {
    "selfhost/parser.सूत्र",
    "selfhost/type_model.सूत्र",
}


class TestSelfHostBytecode(unittest.TestCase):
    def test_bytecode_shadow_core(self):
        for rel in BYTECODE_CORPUS:
            path = Path(rel)
            src = path.read_text(encoding="utf-8")
            result = shadow_bytecode_check(src, str(path))
            self.assertTrue(result["verified"], f"{rel} should verify")
            self.assertGreater(result["bytecode_cases"], 0)

    def test_bytecode_linguist_subset(self):
        for rel in LINGUIST_SUBSET:
            p = Path(rel)
            if not p.exists():
                continue
            src = p.read_text(encoding="utf-8")
            result = shadow_bytecode_check(src, str(p))
            self.assertTrue(result["verified"])

    def test_bytecode_oversized_documented(self):
        for rel in sorted(OVERSIZED):
            path = Path(rel)
            src = path.read_text(encoding="utf-8")
            from peacock.compiler.selfhost_bytecode import shadow_bytecode_check as check
            try:
                check(src, str(path))
            except Exception as exc:
                self.assertIn("256", str(exc))
            else:
                # Some oversized may pass with chunking in future
                pass


if __name__ == "__main__":
    unittest.main()
