import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from peacock.frontend.canvas import Canvas
from peacock.frontend.colour import Color
from peacock.platforms import HeadlessBackend, ServerBackend, WebBackend


def scene(width=64, height=36):
    canvas = Canvas(width, height)
    canvas.gradient([Color.from_srgb(0.1, 0.8, 0.9), Color.from_srgb(0.6, 0.1, 0.9)], 30.0)
    canvas.circle(width / 2, height / 2, min(width, height) / 5, Color.from_srgb(1.0, 0.9, 0.2))
    return canvas


class HeadlessBackendTests(unittest.TestCase):
    def test_present_keeps_latest_frame(self):
        backend = HeadlessBackend()
        frame = backend.present(scene())
        self.assertEqual((frame.width, frame.height), (64, 36))
        self.assertEqual(backend.frame_count, 1)
        self.assertIs(backend.last_frame, frame)
        self.assertTrue(frame.to_png().startswith(b"\x89PNG"))

    def test_writes_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = HeadlessBackend(tmp)
            backend.present(scene())
            backend.present(scene())
            files = sorted(Path(tmp).glob("frame_*.png"))
            self.assertEqual(len(files), 2)

    def test_close_clears(self):
        backend = HeadlessBackend()
        backend.present(scene())
        backend.close()
        self.assertIsNone(backend.last_frame)


class WebBackendTests(unittest.TestCase):
    def test_writes_viewer_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = WebBackend(tmp, title="Unit test")
            frame = backend.present(scene())
            backend.close()
            index = (Path(tmp) / "index.html").read_text(encoding="utf-8")
            self.assertIn("Unit test", index)
            self.assertIn("latest.png", index)
            self.assertNotIn("<script", index.lower())
            self.assertTrue((Path(tmp) / "latest.png").exists())
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(manifest["frames"][0]["width"], 64)
            self.assertEqual(frame.sequence, 0)
            self.assertTrue(frame.data_uri().startswith("data:image/png;base64,"))


class ServerBackendTests(unittest.TestCase):
    def test_health_frame_and_manifest(self):
        with ServerBackend(port=0) as backend:
            base = backend.url.rstrip("/")
            with urllib.request.urlopen(base + "/healthz", timeout=5) as response:
                self.assertEqual(response.read(), b"ok\n")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(base + "/frame.png", timeout=5)
            self.assertEqual(ctx.exception.code, 404)
            backend.present(scene())
            with urllib.request.urlopen(base + "/frame.png", timeout=5) as response:
                self.assertEqual(response.headers.get_content_type(), "image/png")
                self.assertTrue(response.read().startswith(b"\x89PNG"))
            with urllib.request.urlopen(base + "/", timeout=5) as response:
                html = response.read().decode("utf-8")
                self.assertIn("<img", html)
            with urllib.request.urlopen(base + "/manifest.json", timeout=5) as response:
                manifest = json.loads(response.read())
            self.assertEqual(manifest["frames_presented"], 1)
            self.assertEqual(manifest["latest"]["width"], 64)

    def test_unknown_route(self):
        with ServerBackend(port=0) as backend:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(backend.url + "nope", timeout=5)
            self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
