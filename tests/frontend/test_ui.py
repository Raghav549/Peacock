import unittest

from peacock.frontend.colour import Color
from peacock.frontend.ui import UIBuilder, UIError


class UIBuilderTests(unittest.TestCase):
    def setUp(self):
        self.bg = Color.from_hex("#102030")
        self.fg = Color.from_hex("#ffffff")
        self.accent = Color.from_hex("#007777")
        self.ui = UIBuilder("मयूर", 640, 360, self.bg)

    def test_flow_bounds_and_hit_testing(self):
        panel = self.ui.panel(0, 20, 20, 600, 320, self.bg)
        self.ui.text(panel, "संस्कृतम्", 0, 0, 560, 64, self.fg, 28)
        button = self.ui.button(panel, "आरभ्यताम्", 0, 0, 220, 52, self.accent, self.fg)
        self.ui.flow(panel, "column", 16, 20)
        self.assertEqual(self.ui.bounds(button), (40.0, 120.0, 220.0, 52.0))
        self.assertEqual(self.ui.hit_test(50, 130), button)
        self.assertEqual(self.ui.hit_test(630, 350), -1)

    def test_grid_layout(self):
        panel = self.ui.panel(0, 0, 0, 440, 300, self.bg)
        children = [self.ui.panel(panel, 0, 0, 50, 40 + 10 * index, self.accent) for index in range(3)]
        self.ui.grid(panel, 2, 10, 10)
        first, second, third = [self.ui.nodes[node] for node in children]
        self.assertEqual(first.width, 205.0)
        self.assertEqual(second.x, 225.0)
        self.assertEqual(third.y, 70.0)

    def test_accessibility_audit_clean(self):
        panel = self.ui.panel(0, 20, 20, 600, 320, self.bg)
        self.ui.text(panel, "शुद्धः पाठः", 20, 20, 400, 60, self.fg)
        self.ui.button(panel, "नोदक", 20, 100, 200, 52, self.accent, self.fg)
        self.assertEqual(self.ui.audit(), [])

    def test_accessibility_audit_findings(self):
        panel = self.ui.panel(0, 0, 0, 100, 100, Color.from_hex("#ffffff"))
        self.ui.text(panel, "", 0, 0, 120, 20, Color.from_hex("#eeeeee"))
        self.ui.button(panel, "x", 0, 30, 20, 20, Color.from_hex("#ffffff"), Color.from_hex("#eeeeee"))
        findings = self.ui.audit()
        self.assertTrue(any("UI-CONTRAST" in finding for finding in findings))
        self.assertTrue(any("UI-EMPTY-LABEL" in finding for finding in findings))
        self.assertTrue(any("UI-TOUCH-TARGET" in finding for finding in findings))
        self.assertTrue(any("UI-OVERFLOW" in finding for finding in findings))

    def test_html_is_unicode_responsive_escaped_and_script_free(self):
        self.ui.text(0, "संस्कृतं <सत्यम्>", 10, 10, 300, 50, self.fg)
        self.ui.link(0, "अनुबन्ध", "/सूत्र?x=1&y=2", 10, 80, 200, 50, self.fg)
        html = self.ui.to_html()
        self.assertIn('lang="sa"', html)
        self.assertIn("संस्कृतं &lt;सत्यम्&gt;", html)
        self.assertIn("/सूत्र?x=1&amp;y=2", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertNotIn("<script", html)

    def test_unsafe_links_and_invalid_nodes_are_rejected(self):
        with self.assertRaises(UIError):
            self.ui.link(0, "bad", "javascript:alert(1)", 0, 0, 50, 50, self.fg)
        with self.assertRaises(UIError):
            self.ui.panel(999, 0, 0, 10, 10, self.bg)
        with self.assertRaises(UIError):
            self.ui.bounds(999)


if __name__ == "__main__":
    unittest.main()
