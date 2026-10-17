"""Differential tests for the PEACOCK-written parser (`selfhost/parser.pac`).

The bootstrap parser is the oracle: both parsers must produce the same canonical
AST digest for the core-language corpus. The self-hosted parser additionally
self-parses its own source and the tokenizer, which is the strongest available
evidence that it handles the language it is written in.

Scope: the parity corpus now includes model and training declarations
(`examples/xor.pac`, `examples/spiral.pac`). The bootstrap parser remains the
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

PARSER = "selfhost/parser.pac"
MAX_STEPS = "300000000"

CORE_CORPUS = [
    "examples/hello.pac",
    "examples/tour.pac",
    "examples/tensors.pac",
    "examples/motion.pac",
    "examples/aurora.pac",
    "examples/xor.pac",
    "examples/spiral.pac",
    "linguist/samples/hello.pac",
    "linguist/samples/types.pac",
    "linguist/samples/colour.pac",
    "linguist/samples/motion.pac",
    "linguist/samples/capabilities.pac",
    "linguist/samples/tensors.pac",
    "selfhost/fixtures/core_syntax.pac",
]

SELF_PARSE_CORPUS = [
    "selfhost/tokenizer.pac",
    "selfhost/parser.pac",
]

INVALID_SYNTAX = {
    "selfhost/fixtures/invalid/missing_semicolon.pac": "expected ';'",
    "selfhost/fixtures/invalid/chained_comparison.pac": "chained comparisons",
    "selfhost/fixtures/invalid/unclosed_block.pac": "expected '}'",
    "selfhost/fixtures/invalid/unterminated_string.pac": "unterminated string",
    "selfhost/fixtures/invalid/bad_model_section.pac": "expected 'input', 'output' or 'stack'",
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
        args += ["--grant", "fs"]
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
        result = run_selfhost_parser("examples/hello.pac", grant=False)
        self.assertEqual(result.returncode, 3)
        self.assertIn("PE4001", result.stderr)
        self.assertIn("fs", result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_usage_without_arguments(self) -> None:
        result = run_cli(
            "run", PARSER, "--grant", "fs", "--root", ".", "--max-steps", MAX_STEPS
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: parser.pac", result.stdout)


if __name__ == "__main__":
    unittest.main()
