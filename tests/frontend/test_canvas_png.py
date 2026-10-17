import struct
import unittest
import zlib

from peacock.frontend.canvas import Canvas, CanvasError
from peacock.frontend.colour import Color
from peacock.frontend.png import PNGError, canvas_to_rgba8, decode_png, encode_png, write_png

import tempfile
from pathlib import Path


RED = Color.from_srgb(1.0, 0.0, 0.0)
GREEN = Color.from_srgb(0.0, 1.0, 0.0)
BLUE = Color.from_srgb(0.0, 0.0, 1.0)


class CanvasTests(unittest.TestCase):
    def test_dimensions_and_clear(self):
        canvas = Canvas(8, 6)
        self.assertEqual((canvas.width, canvas.height), (8, 6))
        canvas.clear(RED)
        r, g, b, a = canvas.pixel_straight(3, 3)
        self.assertAlmostEqual(r, 1.0, places=6)
        self.assertAlmostEqual(g, 0.0, places=6)
        self.assertAlmostEqual(a, 1.0, places=6)

    def test_invalid_dimensions(self):
        for width, height in ((0, 4), (4, 0), (-1, 4), (4097, 1)):
            with self.assertRaises(CanvasError):
                Canvas(width, height)

    def test_rect_draws_expected_pixels(self):
        canvas = Canvas(10, 10)
        canvas.rect(2.0, 2.0, 4.0, 4.0, RED)
        self.assertAlmostEqual(canvas.pixel_straight(4, 4)[0], 1.0, places=6)
        self.assertEqual(canvas.pixel_straight(0, 0)[3], 0.0)
        self.assertGreaterEqual(canvas.draw_calls, 1)

    def test_circle_draws_center(self):
        canvas = Canvas(20, 20)
        canvas.circle(10.0, 10.0, 5.0, GREEN)
        r, g, b, a = canvas.pixel_straight(10, 10)
        self.assertGreater(a, 0.9)
        self.assertAlmostEqual(g, 1.0, places=6)

    def test_line(self):
        canvas = Canvas(16, 16)
        canvas.line(0.0, 0.0, 15.0, 15.0, 2.0, BLUE)
        self.assertGreater(canvas.pixel_straight(8, 8)[3], 0.5)

    def test_alpha_compositing_is_premultiplied(self):
        canvas = Canvas(4, 4)
        canvas.clear(Color.from_srgb(0.0, 0.0, 0.0, 1.0))
        canvas.rect(0.0, 0.0, 4.0, 4.0, Color.from_srgb(1.0, 1.0, 1.0, 0.5))
        r, g, b, a = canvas.pixel(1, 1)
        self.assertAlmostEqual(r, g, places=9)
        self.assertGreater(a, 0.9)
        straight = canvas.pixel_straight(1, 1)
        self.assertAlmostEqual(straight[0], 0.5, places=4)

    def test_gradient_interpolates(self):
        canvas = Canvas(32, 4)
        canvas.gradient([RED, BLUE], 0.0)
        left = canvas.pixel_straight(0, 2)
        right = canvas.pixel_straight(31, 2)
        self.assertGreater(left[0], left[2])
        self.assertGreater(right[2], right[0])

    def test_gradient_requires_colors(self):
        with self.assertRaises(CanvasError):
            Canvas(4, 4).gradient([], 0.0)

    def test_glow_is_additive(self):
        canvas = Canvas(16, 16)
        canvas.glow(8.0, 8.0, 6.0, RED, 1.0)
        self.assertGreater(canvas.pixel(8, 8)[3], 0.0)

    def test_aurora_is_deterministic_and_rejects_nan(self):
        first = Canvas(24, 12)
        second = Canvas(24, 12)
        first.aurora(1.25, 3)
        second.aurora(1.25, 3)
        self.assertEqual(first.data, second.data)
        with self.assertRaises(CanvasError):
            canvas = Canvas(8, 8)
            canvas.aurora(float("nan"))

    def test_stats(self):
        canvas = Canvas(8, 8)
        stats = canvas.stats()
        self.assertEqual(stats["width"], 8)
        self.assertIn("draw_calls", stats)


class PNGTests(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        canvas = Canvas(16, 12)
        canvas.clear(Color.from_srgb(0.2, 0.4, 0.6, 1.0))
        canvas.rect(2, 2, 6, 6, RED)
        data = encode_png(canvas)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height, rgba = decode_png(data)
        self.assertEqual((width, height), (16, 12))
        self.assertEqual(len(rgba), 16 * 12 * 4)
        self.assertEqual(tuple(rgba[0:4]), (51, 102, 153, 255))

    def test_deterministic_encoding(self):
        canvas = Canvas(9, 7)
        canvas.gradient([RED, BLUE], 45.0)
        self.assertEqual(encode_png(canvas), encode_png(canvas))

    def test_lit_sphere_and_feather_eye_render_deterministically(self):
        c1 = Canvas(32, 32)
        c1.clear(Color.from_hex("#080d18"))
        c1.feather_eye(16.0, 16.0, 12.0, 0.5)
        c1.lit_sphere(16.0, 16.0, 8.0, Color.from_hex("#22b8aa"), 0.2, 0.7, 300.0)
        c2 = Canvas(32, 32)
        c2.clear(Color.from_hex("#080d18"))
        c2.feather_eye(16.0, 16.0, 12.0, 0.5)
        c2.lit_sphere(16.0, 16.0, 8.0, Color.from_hex("#22b8aa"), 0.2, 0.7, 300.0)
        self.assertEqual(encode_png(c1), encode_png(c2))
        self.assertGreater(c1.pixel(16, 16)[1], 0.05)


    def test_hdr_values_are_tone_mapped(self):
        canvas = Canvas(2, 2)
        canvas.clear(Color.from_srgb(1.0, 1.0, 1.0))
        canvas.data[0] = 4.0
        clipped = canvas_to_rgba8(canvas, "clip")
        self.assertEqual(clipped[0], 255)
        aces = canvas_to_rgba8(canvas, "aces")
        self.assertLessEqual(aces[0], 255)

    def test_unknown_tone_map(self):
        with self.assertRaises(PNGError):
            canvas_to_rgba8(Canvas(2, 2), "unknown")

    def test_write_and_decode_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.png"
            canvas = Canvas(5, 5)
            canvas.clear(GREEN)
            size = write_png(canvas, str(path))
            self.assertEqual(size, path.stat().st_size)
            width, height, rgba = decode_png(path.read_bytes())
            self.assertEqual((width, height), (5, 5))

    def test_truncated_png_rejected(self):
        data = encode_png(Canvas(4, 4))
        with self.assertRaises(PNGError):
            decode_png(data[:-8])

    def test_bad_signature_rejected(self):
        data = bytearray(encode_png(Canvas(4, 4)))
        data[0] = 0
        with self.assertRaises(PNGError):
            decode_png(bytes(data))

    def test_crc_is_validated(self):
        data = bytearray(encode_png(Canvas(4, 4)))
        # Flip a byte inside the IHDR payload (offset 8 is the length, 12 the type).
        data[20] ^= 0xFF
        with self.assertRaises(PNGError):
            decode_png(bytes(data))

    def test_chunk_layout(self):
        data = encode_png(Canvas(3, 3))
        offset = 8
        seen = []
        while offset < len(data):
            (length,) = struct.unpack(">I", data[offset : offset + 4])
            kind = data[offset + 4 : offset + 8]
            payload = data[offset + 8 : offset + 8 + length]
            crc = data[offset + 8 + length : offset + 12 + length]
            self.assertEqual(crc, struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
            seen.append(kind)
            offset += 12 + length
        self.assertEqual(seen[0], b"IHDR")
        self.assertEqual(seen[-1], b"IEND")


if __name__ == "__main__":
    unittest.main()
