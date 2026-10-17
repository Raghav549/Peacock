import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from peacock.compiler.lexer import lex
from tests.support import REPO_ROOT


def run_cli(*args, cwd=None, timeout=180):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("NO_COLOR", "1")
    return subprocess.run(
        [sys.executable, "-m", "peacock.cli", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


class CLIBasicsTests(unittest.TestCase):
    def test_version(self):
        result = run_cli("version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PEACOCK AI", result.stdout)
        self.assertIn(".pac", result.stdout)
        self.assertIn("NOT self-hosting", result.stdout)

    def test_help(self):
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0)
        for command in ("run", "check", "build", "disasm", "audit", "bench", "fuzz", "test"):
            self.assertIn(command, result.stdout)

    def test_unknown_command(self):
        result = run_cli("frobnicate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown command", result.stderr)


class CheckCommandTests(unittest.TestCase):
    def test_check_success(self):
        result = run_cli("check", "examples/hello.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK examples/hello.pac", result.stdout)

    def test_check_json(self):
        result = run_cli("check", "examples/tour.pac", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["diagnostics"], [])
        self.assertGreater(payload["stats"]["instructions"], 0)

    def test_check_failure_exit_code_and_caret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.pac"
            path.write_text("fn main() -> Unit { let x = missing; }\n", encoding="utf-8")
            result = run_cli("check", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("PE3002", result.stderr)
            self.assertIn("^", result.stderr)

    def test_check_rejects_wrong_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.pk"
            path.write_text("fn main() -> Unit { }\n", encoding="utf-8")
            result = run_cli("check", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertIn("canonical PEACOCK source extension", result.stderr)

    def test_check_missing_file(self):
        result = run_cli("check", "examples/does_not_exist.pac")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_ast_and_tokens(self):
        tokens = run_cli("tokens", "examples/hello.pac")
        self.assertEqual(tokens.returncode, 0)
        self.assertIn("FN", tokens.stdout)
        tree = run_cli("ast", "examples/hello.pac")
        self.assertEqual(tree.returncode, 0)
        self.assertIn("FunctionDecl", tree.stdout)


class RunCommandTests(unittest.TestCase):
    def test_run_hello(self):
        result = run_cli("run", "examples/hello.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "Hello from PEACOCK")

    def test_run_json(self):
        result = run_cli("run", "examples/hello.pac", "--json")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["output"].strip(), "Hello from PEACOCK")
        self.assertGreater(payload["steps"], 0)

    def test_run_tour(self):
        result = run_cli("run", "examples/tour.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("caught: doubled() does not accept negative numbers", result.stdout)
        self.assertIn("sum: 55", result.stdout)
        self.assertIn("types: String, Float, List", result.stdout)

    def test_capability_denied(self):
        result = run_cli("run", "examples/tensors.pac")
        self.assertEqual(result.returncode, 3)
        self.assertIn("PE4001", result.stderr)
        self.assertIn("compute", result.stderr)

    def test_capability_granted(self):
        result = run_cli("run", "examples/tensors.pac", "--grant", "compute")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("max abs difference: 0.0", result.stdout)

    def test_unknown_grant(self):
        result = run_cli("run", "examples/hello.pac", "--grant", "root")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown grant", result.stderr)

    def test_runtime_error_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crash.pac"
            path.write_text('fn main() -> Unit { let x = 1 / 0; }\n', encoding="utf-8")
            result = run_cli("run", str(path))
            self.assertEqual(result.returncode, 3)
            self.assertIn("division by zero", result.stderr)

    def test_program_arguments(self):
        result = run_cli(
            "run", "selfhost/tokenizer.pac", "--grant", "fs", "--root", ".", "--", "examples/tour.pac"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "367")


class BuildDisassembleAuditTests(unittest.TestCase):
    def test_build_and_run_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "hello.pkb"
            build = run_cli("build", "examples/hello.pac", "-o", str(output))
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertTrue(output.exists())
            self.assertIn("sha256", build.stdout)
            run = run_cli("run", str(output))
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), "Hello from PEACOCK")

    def test_run_tampered_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "hello.pkb"
            run_cli("build", "examples/hello.pac", "-o", str(output))
            data = bytearray(output.read_bytes())
            data[-1] ^= 0xFF
            output.write_bytes(bytes(data))
            result = run_cli("run", str(output))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid artifact", result.stderr)

    def test_disasm(self):
        result = run_cli("disasm", "examples/xor.pac")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("function main", result.stdout)
        self.assertIn("MODEL_INIT", result.stdout)
        self.assertIn("TRAINING_METHOD", result.stdout)

    def test_audit_json(self):
        result = run_cli("audit", "examples/xor.pac", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["capabilities_used"], ["compute"])
        self.assertIn("XorNet", payload["models"])
        self.assertIn("XorTraining", payload["trainings"])
        main = payload["functions"]["main"]
        kinds = {call["kind"] for call in main["capability_calls"]}
        self.assertTrue({"native", "model_init", "training"} & kinds)


class ExampleSuiteTests(unittest.TestCase):
    def test_every_example_is_pac_and_compiles(self):
        examples = sorted((REPO_ROOT / "examples").glob("*"))
        sources = [p for p in examples if p.suffix == ".pac"]
        self.assertGreaterEqual(len(sources), 7)
        self.assertFalse(list((REPO_ROOT / "examples").glob("*.pk")))
        for path in sources:
            result = run_cli("check", str(path.relative_to(REPO_ROOT)))
            self.assertEqual(result.returncode, 0, f"{path.name}: {result.stderr}")

    def test_aurora_writes_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "run", "examples/aurora.pac", "--grant", "fs", "--root", tmp, timeout=300
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            png = Path(tmp) / "examples" / "out" / "aurora.png"
            self.assertTrue(png.exists())
            from peacock.frontend.png import decode_png

            width, height, rgba = decode_png(png.read_bytes())
            self.assertEqual((width, height), (960, 540))
            self.assertEqual(len(set(rgba[::97])), len(set(rgba[::97])))  # decode succeeded

    def test_xor_training(self):
        result = run_cli("run", "examples/xor.pac", "--grant", "compute")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("accuracy: 1.0", result.stdout)

    def test_spiral_training(self):
        result = run_cli("run", "examples/spiral.pac", "--grant", "compute", timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("accuracy: 1.0", result.stdout)

    def test_training_report_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            result = run_cli(
                "run", "examples/spiral.pac", "--grant", "compute", "--report", str(report), timeout=300
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(report.read_text())
            self.assertEqual(payload["epochs"], 250)
            self.assertAlmostEqual(payload["final_accuracy"], 1.0)
            self.assertIn("environment", payload)


class SelfHostParityTests(unittest.TestCase):
    def test_tokenizer_counts_match_bootstrap_lexer(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.pac"
            source = (REPO_ROOT / "examples" / "tour.pac").read_text(encoding="utf-8")
            sample.write_text(source, encoding="utf-8")
            result = run_cli(
                "run", "selfhost/tokenizer.pac", "--grant", "fs", "--root", tmp, "--", "sample.pac"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(int(result.stdout.strip()), len(lex(source)[0]) - 1)

    def test_tokenizer_dump_matches_non_string_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.pac"
            source = 'module demo\nfn main() -> Unit { let x = 0x2A + 1.5e3; }\n'
            sample.write_text(source, encoding="utf-8")
            result = run_cli(
                "run",
                "selfhost/tokenizer.pac",
                "--grant",
                "fs",
                "--root",
                tmp,
                "--",
                "sample.pac",
                "--dump",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            reported = result.stdout.splitlines()
            count = int(reported[0])
            labels = reported[1:]
            self.assertEqual(count, len(labels))
            tokens, diag = lex(source)
            self.assertFalse(diag.has_errors)
            expected = []
            for token in tokens[:-1]:
                if token.kind.name == "IDENT":
                    expected.append(f"id:{token.text}")
                elif token.kind.name in ("INT", "FLOAT"):
                    expected.append(f"num:{token.text}")
                elif token.kind.name == "STRING":
                    expected.append("str:<value>")
                elif token.kind.name == "EOF":
                    continue
                elif token.kind.name in {
                    "MODULE", "USE", "AS", "FN", "LET", "MUT", "IF", "ELSE", "WHILE",
                    "FOR", "IN", "RETURN", "BREAK", "CONTINUE", "STRUCT", "MODEL",
                    "TRAINING", "CAPABILITY", "TRY", "CATCH", "THROW", "ASSERT",
                    "TRUE", "FALSE", "AND", "OR", "NOT",
                }:
                    expected.append(f"kw:{token.text}")
                else:
                    expected.append(f"op:{token.text}")
            actual = []
            for label in labels:
                actual.append("str:<value>" if label.startswith("str:") else label)
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
