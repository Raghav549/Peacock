import ctypes
import os
import time
import unittest

from peacock.frontend.colour import Color
from peacock.frontend.ui import UIBuilder, UIError
from peacock.platforms.window import NativeWindowBackend, _XEvent, _utf16_units


def make_ui():
    ui = UIBuilder("परीक्षा", 320, 200, Color.from_hex("#ffffff"))
    button = ui.button(0, "वृद्धि", 20, 20, 140, 60, Color.from_hex("#000000"), Color.from_hex("#ffffff"))
    ui.bind(button, "click", "वृद्धि")
    return ui, button


class NativeWindowModelTests(unittest.TestCase):
    def test_unicode_units_and_xevent_abi_size(self):
        text = "सूत्र"
        encoded = text.encode("utf-16-be")
        self.assertEqual(_utf16_units(text), [(encoded[i], encoded[i + 1]) for i in range(0, len(encoded), 2)])
        self.assertEqual(_utf16_units("A😀"), [(0, 65), (0xFF, 0xFD)])
        self.assertGreaterEqual(ctypes.sizeof(_XEvent), 192)

    def test_native_button_release_generates_shared_ui_events(self):
        ui, button = make_ui()
        backend = NativeWindowBackend()
        backend.ui = ui
        event = _XEvent()
        event.xbutton.type = 5
        event.xbutton.x, event.xbutton.y = 30, 30
        event.xbutton.button = 1
        backend._dispatch(event)
        records = [ui.next_event() for _ in range(3)]
        self.assertEqual([record.kind for record in records], ["pointer_up", "focus", "click"])
        self.assertEqual(records[-1].node, button)
        self.assertEqual(records[-1].action, "वृद्धि")
        self.assertEqual(ui.focus_node, button)

    def test_native_close_wakes_shared_event_queue(self):
        ui, _button = make_ui()
        ui.bind(0, "close", "निर्गम")
        backend = NativeWindowBackend()
        backend.ui = ui
        backend._wm_delete = 77
        event = _XEvent()
        event.xclient.type = 33
        event.xclient.data.l[0] = 77
        backend._dispatch(event)
        record = ui.next_event()
        self.assertEqual((record.kind, record.node, record.action), ("close", 0, "निर्गम"))
        self.assertTrue(backend._stop.is_set())
        with self.assertRaisesRegex(UIError, "closed"):
            backend.present(ui)

    @unittest.skipIf(bool(os.environ.get("DISPLAY")), "explicit no-display diagnostic applies only headlessly")
    def test_headless_window_is_an_explicit_error(self):
        ui, _button = make_ui()
        backend = NativeWindowBackend()
        try:
            with self.assertRaisesRegex(UIError, "X11|DISPLAY"):
                backend.present(ui)
            self.assertEqual(backend.present_count, 0)
        finally:
            backend.close()

    @unittest.skipUnless(os.environ.get("PEACOCK_TEST_X11") == "1" and os.environ.get("DISPLAY"), "opt-in real X11 display test")
    def test_real_x11_open_draw_close(self):
        ui, _button = make_ui()
        backend = NativeWindowBackend()
        try:
            backend.present(ui)
            deadline = time.monotonic() + 3
            while backend._drawn_revision < 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreaterEqual(backend._drawn_revision, 0, backend.error)
            self.assertEqual(backend.present_count, 1)
        finally:
            backend.close()


if __name__ == "__main__":
    unittest.main()
