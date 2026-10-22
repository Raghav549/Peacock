import math
import unittest

from peacock.frontend.colour import (
    Color, ColorError, delta_e_2000, map_gamut, mix_subtractive, mix_weighted,
)


class AdvancedMixingTests(unittest.TestCase):
    def setUp(self):
        self.red = Color.from_hex("#ff0000")
        self.blue = Color.from_hex("#0000ff")

    def test_weight_normalization_and_linear_mix(self):
        result = mix_weighted([self.red, self.blue], [2.0, 2.0], "linear")
        self.assertAlmostEqual(result.r, 0.5)
        self.assertAlmostEqual(result.g, 0.0)
        self.assertAlmostEqual(result.b, 0.5)

    def test_oklch_hue_uses_circular_mean(self):
        a = Color.from_oklch(0.6, 0.1, 350.0)
        b = Color.from_oklch(0.6, 0.1, 10.0)
        hue = mix_weighted([a, b], [1.0, 1.0], "oklch").oklch()[2]
        self.assertLess(min(hue, 360.0 - hue), 1e-4)

    def test_identical_colours_are_invariant_in_every_space(self):
        for space in ("linear", "oklab", "oklch", "srgb", "subtractive"):
            with self.subTest(space=space):
                result = mix_weighted([self.red, self.red], [1.0, 3.0], space)
                self.assertAlmostEqual(result.r, self.red.r, places=6)
                self.assertAlmostEqual(result.g, self.red.g, places=6)
                self.assertAlmostEqual(result.b, self.red.b, places=6)

    def test_subtractive_direct_weights_are_normalized(self):
        a = mix_subtractive([self.red, self.blue], [1.0, 1.0])
        b = mix_subtractive([self.red, self.blue], [10.0, 10.0])
        self.assertAlmostEqual(a.r, b.r)
        self.assertAlmostEqual(a.g, b.g)
        self.assertAlmostEqual(a.b, b.b)

    def test_invalid_weights(self):
        for colors, weights in (([], []), ([self.red], []), ([self.red], [-1.0]), ([self.red], [0.0]), ([self.red], [math.nan])):
            with self.subTest(colors=colors, weights=weights), self.assertRaises(ColorError):
                mix_weighted(colors, weights)


class ColourScienceTests(unittest.TestCase):
    def test_ciede2000_reference_pair(self):
        a = Color.from_lab(50.0, 2.6772, -79.7751)
        b = Color.from_lab(50.0, 0.0, -82.7485)
        self.assertAlmostEqual(delta_e_2000(a, b), 2.0425, places=4)
        self.assertAlmostEqual(delta_e_2000(a, b), delta_e_2000(b, a), places=12)
        self.assertEqual(delta_e_2000(a, a), 0.0)

    def test_gamut_mapping_reduces_chroma(self):
        original = Color.from_oklch(0.7, 0.5, 30.0)
        mapped = map_gamut(original)
        self.assertTrue(mapped.in_gamut(tolerance=1e-5))
        self.assertLess(mapped.oklch()[1], original.oklch()[1])
        self.assertAlmostEqual(mapped.oklch()[2], original.oklch()[2], places=4)

    def test_gamut_mapping_preserves_in_gamut_identity(self):
        color = Color.from_hex("#3280a0")
        self.assertIs(map_gamut(color), color)


if __name__ == "__main__":
    unittest.main()
