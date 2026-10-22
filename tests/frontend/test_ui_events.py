import unittest

from peacock.frontend.colour import Color
from peacock.frontend.ui import UIBuilder, UIError
from tests.support import run_source


class UIEventModelTests(unittest.TestCase):
    def setUp(self):
        self.white = Color.from_hex("#ffffff")
        self.black = Color.from_hex("#000000")
        self.ui = UIBuilder("घटना", 320, 240, self.white)
        self.panel = self.ui.panel(0, 0, 0, 300, 200, self.white)
        self.text = self.ui.text(self.panel, "०", 0, 0, 200, 50, self.black)
        self.button = self.ui.button(self.panel, "बढ़ाएँ", 0, 60, 160, 50, self.white, self.black)

    def test_binding_bubbling_and_monotonic_records(self):
        self.ui.bind(self.panel, "click", "parent-action")
        first = self.ui.post_event("click", self.button, 10, 70)
        second = self.ui.post_event("click", self.button, 11, 71)
        self.assertEqual((first, second), (1, 2))
        event = self.ui.next_event()
        self.assertEqual(event.handler, self.panel)
        self.assertEqual(event.action, "parent-action")
        self.assertEqual(event.as_strings()[:3], ["1", "click", str(self.button)])
        self.assertEqual(self.ui.pending_events(), 1)
        self.assertEqual(self.ui.next_event().id, 2)
        self.assertIsNone(self.ui.next_event())

    def test_child_binding_precedes_parent_and_wildcard(self):
        self.ui.bind(self.panel, "*", "fallback")
        self.ui.bind(self.button, "click", "child")
        self.ui.post_event("click", self.button)
        self.ui.post_event("key", self.button, key="Enter")
        self.assertEqual(self.ui.next_event().action, "child")
        self.assertEqual(self.ui.next_event().action, "fallback")

    def test_focus_keyboard_and_disabled_subtree(self):
        self.ui.focus(self.button)
        self.ui.bind(self.button, "key", "activate")
        self.ui.bind(self.button, "click", "activate")
        self.ui.post_event("key", key="Enter")
        event = self.ui.next_event()
        self.assertEqual((event.node, event.action), (self.button, "activate"))
        self.ui.set_enabled(self.panel, False)
        self.ui.post_event("click", self.button)
        self.assertEqual(self.ui.next_event().action, "")
        self.assertIn("disabled", self.ui.to_html())
        self.ui.set_enabled(self.panel, True)
        self.ui.post_event("click", self.button)
        self.assertEqual(self.ui.next_event().action, "activate")

    def test_text_mutation_revision_and_static_fragment(self):
        revision = self.ui.revision
        self.ui.set_text(self.text, "संस्कृतम् <safe>")
        self.assertGreater(self.ui.revision, revision)
        html = self.ui.to_html()
        self.assertNotIn("<script", html)
        self.assertIn("संस्कृतम् &lt;safe&gt;", html)
        fragment = self.ui.to_fragment()
        self.assertTrue(fragment.startswith("<main "))
        self.assertTrue(fragment.endswith("</main>"))
        with self.assertRaises(UIError):
            self.ui.set_text(self.panel, "invalid")

    def test_bounded_queue_and_validation(self):
        self.ui.max_events = 1
        self.ui.post_event("click", self.button)
        with self.assertRaisesRegex(UIError, "queue is full"):
            self.ui.post_event("click", self.button)
        with self.assertRaises(UIError):
            self.ui.next_event(60_001)
        with self.assertRaises(UIError):
            self.ui.bind(self.button, "unknown", "action")

    def test_sanskrit_native_roundtrip(self):
        source = """
        उपयोग रङ्ग
        उपयोग दृश्य
        कार्य मुख्य() -> एकक {
            स्थापय रचना = दृश्य.सृज("घटना", १००, १००, रङ्ग.षोडशात्("#ffffff"));
            स्थापय नोदक = दृश्य.नोदक(रचना, ०, "नोदक", ०.०, ०.०, ८०.०, ५०.०, रङ्ग.षोडशात्("#ffffff"), रङ्ग.षोडशात्("#000000"));
            दृश्य.बन्धन(रचना, नोदक, "स्पर्श", "क्रिया");
            स्थापय परिचय = दृश्य.घटनाप्रेषय(रचना, "स्पर्श", नोदक);
            स्थापय घटना = दृश्य.अग्रघटना(रचना);
            निश्चिनु परिचय == १;
            निश्चिनु घटना[१] == "स्पर्श";
            निश्चिनु घटना[८] == "क्रिया";
            निश्चिनु दृश्य.घटनासंख्या(रचना) == ०;
            दृश्य.पाठ्यस्थापय(रचना, नोदक, "सिद्ध");
            निश्चिनु दृश्य.एचटीएमएलपाठ्य(रचना).अन्तर्भूत("सिद्ध");
        }
        """
        self.assertEqual(run_source(source)[0], "")


if __name__ == "__main__":
    unittest.main()
