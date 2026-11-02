"""Differential tests for the PEACOCK-native IR builder (`selfhost/ir.सूत्र`).

The Python IR is the oracle; the PEACOCK kernel must produce byte-identical
digests for the core-language corpus. Large self-host files that exceed the
256-slot VM limit are excluded with an explicit skip (see `OVERSIZED`).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from peacock.compiler.selfhost_ir import shadow_ir_check

# Core corpus that exercises control flow, field access, methods, try/catch,
# structs, lists, ranges, and model/training declarations.
CORE_CORPUS = [
    "examples/hello.सूत्र",
    "examples/tour.सूत्र",
    "examples/motion.सूत्र",
    "examples/aurora.सूत्र",
    "examples/native.सूत्र",
    "examples/xor.सूत्र",
    "examples/spiral.सूत्र",
    "linguist/samples/hello.सूत्र",
    "linguist/samples/types.सूत्र",
    "linguist/samples/colour.सूत्र",
    "linguist/samples/motion.सूत्र",
    "linguist/samples/capabilities.सूत्र",
    "linguist/samples/tensors.सूत्र",
    "selfhost/fixtures/core_syntax.सूत्र",
    "selfhost/fixtures/finally.सूत्र",
    "selfhost/tokenizer.सूत्र",
]

# Files that compile but need >256 locals for the shadow probe's single
# `main` wrapper. The VM limit is documented in `docs/compiler/ir.md`.
OVERSIZED = {
    "selfhost/parser.सूत्र",
    "selfhost/type_model.सूत्र",
}


class TestSelfHostIR(unittest.TestCase):
    def test_ir_shadow_core_corpus(self):
        for rel in CORE_CORPUS:
            path = Path(rel)
            src = path.read_text(encoding="utf-8")
            result = shadow_ir_check(src, str(path))
            self.assertTrue(result["verified"], f"{rel} should verify")
            self.assertGreater(result["ir_cases"], 0, f"{rel} should have at least one function")

    def test_ir_shadow_oversized_is_documented(self):
        for rel in sorted(OVERSIZED):
            path = Path(rel)
            src = path.read_text(encoding="utf-8")
            try:
                shadow_ir_check(src, str(path))
            except Exception as exc:
                msg = str(exc)
                self.assertIn("256", msg, f"{rel} should fail with slot limit, got {msg[:200]}")
            else:
                self.fail(f"{rel} was expected to be oversized but passed")


if __name__ == "__main__":
    unittest.main()
