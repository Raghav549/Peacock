"""End-to-end tests for `चित्र.प्रदर्शय` and the host presentation path.

These tests exercise the real VM native, the real capability checks and the real
static-web backend. They are the evidence that a `.सूत्र` program can hand frames
to a host without the language runtime knowing what the host is.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from peacock.frontend.png import decode_png
from peacock.runtime.host import HostPolicy
from peacock.compiler.diagnostics import HostError
from tests.support import REPO_ROOT


def run_cli(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
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


class PresentCommandTests(unittest.TestCase):
    def test_presents_frames_to_web_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "preview"
            result = run_cli(
                "run",
                "examples/present.सूत्र",
                "--grant",
                "दृश्य",
                "--present",
                str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "presented 4 frames")

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["format"], "peacock-web-frames")
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(len(manifest["frames"]), 4)
            self.assertEqual(
                [f["sequence"] for f in manifest["frames"]], [0, 1, 2, 3]
            )
            for frame in manifest["frames"]:
                self.assertEqual((frame["width"], frame["height"]), (320, 180))
                self.assertTrue((out / frame["file"]).is_file(), frame["file"])

            width, height, pixels = decode_png((out / "latest.png").read_bytes())
            self.assertEqual((width, height), (320, 180))
            self.assertEqual(len(pixels), 320 * 180 * 4)
            html = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn("<img", html)
            self.assertIn("present — PEACOCK", html)  # title comes from the source stem

    def test_present_without_host_grant_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "preview"
            result = run_cli(
                "run", "examples/present.सूत्र", "--present", str(out)
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn("PE4001", result.stderr)
            self.assertIn("ui", result.stderr)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["frames"], [])
            self.assertEqual(list((out / "frames").iterdir()), [])
            self.assertFalse((out / "latest.png").exists())

    def test_grant_without_backend_is_a_configuration_error(self) -> None:
        result = run_cli("run", "examples/present.सूत्र", "--grant", "दृश्य")
        self.assertEqual(result.returncode, 3)
        self.assertIn("PE4006", result.stderr)
        self.assertIn("no presentation backend", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_json_reports_frames_presented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "run",
                "examples/present.सूत्र",
                "--grant",
                "दृश्य",
                "--present",
                str(Path(tmp) / "preview"),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["frames_presented"], 4)
            self.assertEqual(payload["grants"], ["ui"])

    def test_unknown_grant_message_lists_ui(self) -> None:
        result = run_cli("run", "examples/present.सूत्र", "--grant", "network")
        self.assertEqual(result.returncode, 2)
        self.assertIn("known Sanskrit grants: गणना, सञ्चय, दृश्य", result.stderr)


class StaticCapabilityTests(unittest.TestCase):
    def test_present_requires_a_declaration(self) -> None:
        source = textwrap.dedent(
            """
            प्रकरण missing_declaration

            उपयोग चित्र

            कार्य मुख्य() -> एकक {
                स्थापय चित्रपट्ट = चित्र.चित्रपट्ट(8, 8);
                चित्र.प्रदर्शय(चित्रपट्ट);
            }
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.सूत्र"
            path.write_text(source, encoding="utf-8")
            result = run_cli("check", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("PE3005", result.stderr)
            self.assertIn("ui", result.stderr)
            self.assertIn("अधिकार दृश्य", result.stderr)

    def test_declaration_without_grant_is_catchable_and_presents_nothing(self) -> None:
        source = textwrap.dedent(
            """
            प्रकरण caught_denial

            उपयोग चित्र

            कार्य मुख्य() -> एकक {
                अधिकार दृश्य;
                स्थापय चित्रपट्ट = चित्र.चित्रपट्ट(16, 16);
                यत्न {
                    चित्र.प्रदर्शय(चित्रपट्ट);
                    मुद्रय("presented");
                } गृह्ण (सन्देश) {
                    मुद्रय("denied: " + सन्देश);
                }
            }
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caught.सूत्र"
            path.write_text(source, encoding="utf-8")
            out = Path(tmp) / "preview"
            result = run_cli("run", str(path), "--present", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("denied: host has not granted capability 'दृश्य'", result.stdout)
            self.assertNotIn("presented", result.stdout.replace("denied:", ""))
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["frames"], [])


class HostPresenterTests(unittest.TestCase):
    def test_present_requires_ui_grant(self) -> None:
        host = HostPolicy(grants=frozenset(), presenter=lambda canvas: None)
        with self.assertRaises(HostError) as ctx:
            host.present(object())
        self.assertEqual(ctx.exception.code, "PE4001")

    def test_present_requires_an_attached_backend(self) -> None:
        host = HostPolicy(grants=frozenset({"ui"}))
        with self.assertRaises(HostError) as ctx:
            host.present(object())
        self.assertEqual(ctx.exception.code, "PE4006")

    def test_backend_failures_are_wrapped(self) -> None:
        def explode(canvas):
            raise RuntimeError("display unplugged")

        host = HostPolicy(grants=frozenset({"ui"}), presenter=explode)
        with self.assertRaises(HostError) as ctx:
            host.present(object())
        self.assertEqual(ctx.exception.code, "PE5003")
        self.assertIn("display unplugged", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


class ServeCommandTests(unittest.TestCase):
    def _free_port(self) -> int:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def test_serves_frames_over_http_during_and_after_the_run(self) -> None:
        import socket
        import time
        import urllib.request

        port = self._free_port()
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        env.setdefault("NO_COLOR", "1")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "peacock.cli",
                "run",
                "examples/present.सूत्र",
                "--grant",
                "दृश्य",
                "--serve",
                str(port),
                "--linger",
                "3",
            ],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.time() + 30
            payload = None
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(base + "/manifest.json", timeout=2) as response:
                        payload = json.loads(response.read())
                    if payload["frames_presented"] == 4:
                        break
                except Exception:
                    pass
                time.sleep(0.1)
            self.assertIsNotNone(payload, "server never became reachable")
            self.assertEqual(payload["format"], "peacock-server-frame")
            self.assertEqual(payload["frames_presented"], 4)
            self.assertEqual(payload["latest"]["width"], 320)
            self.assertEqual(payload["latest"]["height"], 180)

            with urllib.request.urlopen(base + "/frame.png", timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get("Content-Type"), "image/png")
                png = response.read()
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
            width, height, pixels = decode_png(png)
            self.assertEqual((width, height), (320, 180))
            self.assertEqual(len(pixels), 320 * 180 * 4)

            with urllib.request.urlopen(base + "/", timeout=5) as response:
                html = response.read().decode("utf-8")
            self.assertIn("<img", html)
            self.assertNotIn("<script", html)

            with urllib.request.urlopen(base + "/healthz", timeout=5) as response:
                self.assertEqual(response.read(), b"ok\n")
        finally:
            stdout, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "presented 4 frames")
        self.assertIn(f"serving at http://127.0.0.1:{port}/", stderr)

        # The server is closed when the process exits.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            self.assertNotEqual(sock.connect_ex(("127.0.0.1", port)), 0)

    def test_present_and_serve_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "run",
                "examples/present.सूत्र",
                "--grant",
                "दृश्य",
                "--present",
                str(Path(tmp) / "preview"),
                "--serve",
                str(self._free_port()),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("mutually exclusive", result.stderr)

    def test_busy_port_is_a_usage_error(self) -> None:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            result = run_cli(
                "run",
                "examples/present.सूत्र",
                "--grant",
                "दृश्य",
                "--serve",
                str(port),
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot serve", result.stderr)
