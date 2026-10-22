"""Differential tests for the PEACOCK-written parser (`selfhost/parser.सूत्र`).

The bootstrap parser is the oracle: both parsers must produce the same canonical
AST digest for the core-language corpus. The self-hosted parser additionally
self-parses its own source and the tokenizer, which is the strongest available
evidence that it handles the language it is written in.

Scope: the parity corpus now includes model and training declarations
(`examples/xor.सूत्र`, `examples/spiral.सूत्र`). The bootstrap parser remains the
diagnostics and recovery oracle; the self-hosted parser is strict.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.integration.ast_digest import module_digest
from tests.support import REPO_ROOT

PARSER = "selfhost/parser.सूत्र"
MAX_STEPS = "300000000"

CORE_CORPUS = [
    "examples/hello.सूत्र",
    "examples/tour.सूत्र",
    "examples/tensors.सूत्र",
    "examples/motion.सूत्र",
    "examples/aurora.सूत्र",
    "examples/xor.सूत्र",
    "examples/spiral.सूत्र",
    "linguist/samples/hello.सूत्र",
    "linguist/samples/types.सूत्र",
    "linguist/samples/colour.सूत्र",
    "linguist/samples/motion.सूत्र",
    "linguist/samples/capabilities.सूत्र",
    "linguist/samples/tensors.सूत्र",
    "selfhost/fixtures/core_syntax.सूत्र",
]

SELF_PARSE_CORPUS = [
    "selfhost/tokenizer.सूत्र",
    "selfhost/parser.सूत्र",
]

INVALID_SYNTAX = {
    "selfhost/fixtures/invalid/missing_semicolon.सूत्र": "expected ';'",
    "selfhost/fixtures/invalid/chained_comparison.सूत्र": "chained comparisons",
    "selfhost/fixtures/invalid/unclosed_block.सूत्र": "expected '}'",
    "selfhost/fixtures/invalid/unterminated_string.सूत्र": "unterminated string",
    "selfhost/fixtures/invalid/bad_model_section.सूत्र": "expected 'निवेश', 'निर्गम' or 'क्रम'",
}


def run_cli(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env.setdefault("NO_COLOR", "1")
    return subprocess.run(
        [sys.executable, "-m", "peacock.cli", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def run_selfhost_parser(path: str, *, grant: bool = True) -> subprocess.CompletedProcess:
    args = ["run", PARSER]
    if grant:
        args += ["--grant", "सञ्चय"]
    args += ["--root", ".", "--max-steps", MAX_STEPS, "--", path]
    return run_cli(*args)


class SelfHostParserParityTests(unittest.TestCase):
    def test_core_corpus_matches_bootstrap_ast(self) -> None:
        for path in CORE_CORPUS:
            with self.subTest(path=path):
                source = (REPO_ROOT / path).read_text(encoding="utf-8")
                expected = module_digest(source, path)
                result = run_selfhost_parser(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(result.stdout.strip(), expected.strip())

    def test_parser_self_parses_and_matches_bootstrap(self) -> None:
        for path in SELF_PARSE_CORPUS:
            with self.subTest(path=path):
                source = (REPO_ROOT / path).read_text(encoding="utf-8")
                expected = module_digest(source, path)
                result = run_selfhost_parser(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected.strip())


class SelfHostParserNegativeTests(unittest.TestCase):
    def test_invalid_syntax_is_rejected_with_position(self) -> None:
        for path, needle in INVALID_SYNTAX.items():
            with self.subTest(path=path):
                result = run_selfhost_parser(path)
                self.assertEqual(result.returncode, 3, result.stdout)
                self.assertIn("PE4020", result.stderr)
                self.assertIn(needle, result.stderr)
                self.assertIn("line ", result.stderr)
                self.assertIn("column ", result.stderr)

    def test_parser_requires_fs_grant(self) -> None:
        result = run_selfhost_parser("examples/hello.सूत्र", grant=False)
        self.assertEqual(result.returncode, 3)
        self.assertIn("PE4001", result.stderr)
        self.assertIn("सञ्चय", result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_usage_without_arguments(self) -> None:
        result = run_cli(
            "run", PARSER, "--grant", "सञ्चय", "--root", ".", "--max-steps", MAX_STEPS
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: parser.सूत्र", result.stdout)


if __name__ == "__main__":
    unittest.main()
