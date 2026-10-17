import math
import unittest

from peacock.frontend.colour import (
    Color,
    ColorError,
    contrast_ratio,
    mix,
    palette,
    sample_gradient,
    srgb_to_linear,
    linear_to_srgb,
)


class TransferFunctionTests(unittest.TestCase):
    def test_srgb_linear_roundtrip(self):
        for value in (0.0, 0.001, 0.04, 0.5, 1.0):
            self.assertAlmostEqual(linear_to_srgb(srgb_to_linear(value)), value, places=12)

    def test_linear_extremes(self):
        self.assertEqual(srgb_to_linear(0.0), 0.0)
        self.assertAlmostEqual(srgb_to_linear(1.0), 1.0)

    def test_linear_to_srgb_extremes(self):
        self.assertEqual(linear_to_srgb(0.0), 0.0)
        self.assertAlmostEqual(linear_to_srgb(1.0), 1.0)


class ColorConstructionTests(unittest.TestCase):
    def test_from_srgb_and_back(self):
        c = Color.from_srgb(0.25, 0.5, 0.75, 0.5)
        self.assertAlmostEqual(c.alpha, 0.5)
        r, g, b = c.srgb()
        self.assertAlmostEqual(r, 0.25, places=9)
        self.assertAlmostEqual(g, 0.5, places=9)
        self.assertAlmostEqual(b, 0.75, places=9)

    def test_oklab_white(self):
        L, a, b = Color.from_srgb(1.0, 1.0, 1.0).oklab()
        self.assertAlmostEqual(L, 1.0, places=6)
        self.assertAlmostEqual(a, 0.0, places=6)
        self.assertAlmostEqual(b, 0.0, places=6)

    def test_oklab_red_reference(self):
        L, a, b = Color.from_srgb(1.0, 0.0, 0.0).oklab()
        self.assertAlmostEqual(L, 0.6279553606145516, places=6)
        self.assertAlmostEqual(a, 0.22486306106597398, places=6)
        self.assertAlmostEqual(b, 0.1258462985307351, places=6)

    def test_oklch_roundtrip(self):
        original = Color.from_srgb(0.2, 0.6, 0.9)
        L, C, h = original.oklch()
        restored = Color.from_oklch(L, C, h)
        for a, b in zip(original.srgb(), restored.srgb()):
            self.assertAlmostEqual(a, b, places=5)

    def test_lab_white(self):
        L, a, b = Color.from_srgb(1.0, 1.0, 1.0).lab()
        self.assertAlmostEqual(L, 100.0, places=3)
        self.assertAlmostEqual(a, 0.0, places=3)
        self.assertAlmostEqual(b, 0.0, places=3)

    def test_hex_roundtrip(self):
        for text in ("#000000", "#ffffff", "#1a2b3c", "#ff000080"):
            c = Color.from_hex(text)
            self.assertEqual(c.to_hex(alpha=len(text) == 9).lower(), text.lower())

    def test_invalid_hex(self):
        for text in ("123456", "#12345", "#GGGGGG", "#1234567"):
            with self.assertRaises(ColorError):
                Color.from_hex(text)

    def test_oklab_constructor_rejects_bad_alpha(self):
        with self.assertRaises(ColorError):
            Color.from_oklab(0.5, 0.0, 0.0, 2.0)

    def test_clipped_is_in_gamut(self):
        c = Color.from_oklab(0.6, 0.4, 0.3)
        self.assertTrue(c.clipped().in_gamut())
        self.assertFalse(c.in_gamut(tolerance=0.0))


class ContrastTests(unittest.TestCase):
    def test_white_on_black_is_21(self):
        self.assertAlmostEqual(contrast_ratio(Color.from_srgb(1, 1, 1), Color.from_srgb(0, 0, 0)), 21.0, places=2)

    def test_same_color_is_one(self):
        c = Color.from_srgb(0.4, 0.4, 0.4)
        self.assertAlmostEqual(c.contrast_ratio(c), 1.0, places=9)


class MixingTests(unittest.TestCase):
    def test_mix_endpoints(self):
        a = Color.from_srgb(1.0, 0.0, 0.0)
        b = Color.from_srgb(0.0, 0.0, 1.0)
        self.assertEqual(a.mix(b, 0.0).to_hex(), a.to_hex())
        self.assertEqual(a.mix(b, 1.0).to_hex(), b.to_hex())

    def test_mix_is_in_gamut(self):
        a = Color.from_srgb(1.0, 0.0, 0.0)
        b = Color.from_srgb(0.0, 1.0, 0.0)
        mid = mix(a, b, 0.5)
        self.assertTrue(mid.in_gamut(tolerance=1e-3))

    def test_lighten_and_darken(self):
        c = Color.from_srgb(0.5, 0.5, 0.5)
        self.assertGreater(c.lighten(0.1).oklab()[0], c.oklab()[0])
        self.assertLess(c.darken(0.1).oklab()[0], c.oklab()[0])

    def test_complement_rotates_hue(self):
        c = Color.from_srgb(1.0, 0.0, 0.0)
        h1 = c.oklch()[2]
        h2 = c.complement().oklch()[2]
        self.assertAlmostEqual((h2 - h1) % 360.0, 180.0, places=4)

    def test_sample_gradient(self):
        colors = [Color.from_srgb(1, 0, 0), Color.from_srgb(0, 0, 1)]
        self.assertEqual(sample_gradient(colors, 0.0).to_hex(), colors[0].to_hex())
        self.assertEqual(sample_gradient(colors, 1.0).to_hex(), colors[1].to_hex())

    def test_palette_deterministic(self):
        self.assertEqual([c.to_hex() for c in palette(4, 7)], ["#d473cd", "#6a6300", "#0065a1", "#df7d7a"])
        self.assertEqual([c.to_hex() for c in palette(4, 7)], [c.to_hex() for c in palette(4, 7)])
        with self.assertRaises(ColorError):
            palette(0, 1)
        with self.assertRaises(ColorError):
            Color.from_hex("#12345")

    def test_thin_film_iridescence_and_wcag_thresholds(self):
        from peacock.frontend.colour import thin_film_iridescence, wcag_passes

        normal_view = thin_film_iridescence(1.0, 280.0)
        grazing_view = thin_film_iridescence(0.25, 280.0)
        self.assertTrue(normal_view.in_gamut())
        self.assertTrue(grazing_view.in_gamut())
        self.assertNotEqual(normal_view.to_hex(), grazing_view.to_hex())
        with self.assertRaises(ColorError):
            thin_film_iridescence(1.5, 280.0)

        ink = Color.from_hex("#edf3ff")
        bg = Color.from_hex("#080d18")
        low = Color.from_hex("#182235")
        self.assertTrue(wcag_passes(ink, bg, "AA"))
        self.assertTrue(wcag_passes(ink, bg, "AAA"))
        self.assertFalse(wcag_passes(low, bg, "AA"))



if __name__ == "__main__":
    unittest.main()
