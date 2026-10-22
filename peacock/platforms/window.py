"""Native X11 windows for PEACOCK's retained UI tree and event queue.

No browser or third-party widget toolkit is used.  X11 is loaded dynamically;
its absence (or a missing DISPLAY) is an explicit UIError.  Core ISO-10646
fonts are used for text, so complex-script shaping depends on the host and is
not represented as a complete Pango/HarfBuzz text stack.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import threading
import time

from peacock.frontend.colour import Color
from peacock.frontend.ui import UIBuilder, UIError


class _XChar2b(ctypes.Structure):
    _fields_ = [("byte1", ctypes.c_ubyte), ("byte2", ctypes.c_ubyte)]


class _XColor(ctypes.Structure):
    _fields_ = [
        ("pixel", ctypes.c_ulong), ("red", ctypes.c_ushort),
        ("green", ctypes.c_ushort), ("blue", ctypes.c_ushort),
        ("flags", ctypes.c_char), ("pad", ctypes.c_char),
    ]


class _XFontPrefix(ctypes.Structure):
    _fields_ = [("ext_data", ctypes.c_void_p), ("fid", ctypes.c_ulong)]


class _XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong), ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint), ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XButtonEvent(ctypes.Structure):
    _fields_ = _XKeyEvent._fields_[:-2] + [
        ("button", ctypes.c_uint), ("same_screen", ctypes.c_int),
    ]


class _XClientData(ctypes.Union):
    pass


_XClientData._fields_ = [("b", ctypes.c_char * 20), ("s", ctypes.c_short * 10), ("l", ctypes.c_long * 5)]


class _XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int), ("data", _XClientData),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int), ("xkey", _XKeyEvent),
        ("xbutton", _XButtonEvent), ("xclient", _XClientMessageEvent),
        ("pad", ctypes.c_long * 24),
    ]


def _utf16_units(text: str) -> list[tuple[int, int]]:
    """Convert BMP Unicode to XChar2b; non-BMP glyphs become U+FFFD."""

    text = "".join(character if ord(character) <= 0xFFFF else "�" for character in text)
    encoded = text.encode("utf-16-be", "replace")
    return [(encoded[i], encoded[i + 1]) for i in range(0, len(encoded), 2)]


class NativeWindowBackend:
    """Lazy native window; one instance owns one UIBuilder and one X display."""

    def __init__(self, title: str = "PEACOCK"):
        self.title = title
        self.ui: UIBuilder | None = None
        self.present_count = 0
        self.thread: threading.Thread | None = None
        self.error: str | None = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._drawn_revision = -1
        self._pixels: dict[tuple[int, int, int], int] = {}
        self.lib = None
        self.display = None
        self.window = 0
        self.gc = None
        self.colormap = 0
        self.font = None
        self._wm_delete = 0

    @staticmethod
    def _configure(function, arguments, result=ctypes.c_int):
        function.argtypes = arguments
        function.restype = result

    def _load(self):
        name = ctypes.util.find_library("X11") or "libX11.so.6"
        try:
            lib = ctypes.CDLL(name)
        except OSError as exc:
            raise UIError(f"native windows require the X11 client library: {exc}") from exc
        vp, ul = ctypes.c_void_p, ctypes.c_ulong
        self._configure(lib.XInitThreads, [], ul)
        self._configure(lib.XOpenDisplay, [ctypes.c_char_p], vp)
        self._configure(lib.XDefaultScreen, [vp])
        self._configure(lib.XRootWindow, [vp, ctypes.c_int], ul)
        self._configure(lib.XBlackPixel, [vp, ctypes.c_int], ul)
        self._configure(lib.XWhitePixel, [vp, ctypes.c_int], ul)
        self._configure(lib.XDefaultColormap, [vp, ctypes.c_int], ul)
        self._configure(lib.XCreateSimpleWindow, [vp, ul, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ul, ul], ul)
        self._configure(lib.XSelectInput, [vp, ul, ctypes.c_long])
        self._configure(lib.XStoreName, [vp, ul, ctypes.c_char_p])
        self._configure(lib.XInternAtom, [vp, ctypes.c_char_p, ctypes.c_int], ul)
        self._configure(lib.XChangeProperty, [vp, ul, ul, ul, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int])
        self._configure(lib.XSetWMProtocols, [vp, ul, ctypes.POINTER(ul), ctypes.c_int])
        self._configure(lib.XMapWindow, [vp, ul])
        self._configure(lib.XFlush, [vp])
        self._configure(lib.XPending, [vp])
        self._configure(lib.XNextEvent, [vp, ctypes.POINTER(_XEvent)])
        self._configure(lib.XCreateGC, [vp, ul, ctypes.c_ulong, vp], vp)
        self._configure(lib.XFreeGC, [vp, vp])
        self._configure(lib.XSetForeground, [vp, vp, ul])
        self._configure(lib.XFillRectangle, [vp, ul, vp, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint])
        self._configure(lib.XDrawRectangle, [vp, ul, vp, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint])
        self._configure(lib.XDrawString16, [vp, ul, vp, ctypes.c_int, ctypes.c_int, ctypes.POINTER(_XChar2b), ctypes.c_int])
        self._configure(lib.XAllocColor, [vp, ul, ctypes.POINTER(_XColor)])
        self._configure(lib.XFreeColors, [vp, ul, ctypes.POINTER(ul), ctypes.c_int, ul])
        self._configure(lib.XLoadQueryFont, [vp, ctypes.c_char_p], ctypes.POINTER(_XFontPrefix))
        self._configure(lib.XSetFont, [vp, vp, ul])
        self._configure(lib.XFreeFont, [vp, ctypes.POINTER(_XFontPrefix)])
        self._configure(lib.XLookupString, [ctypes.POINTER(_XKeyEvent), ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ul), vp])
        self._configure(lib.XDestroyWindow, [vp, ul])
        self._configure(lib.XCloseDisplay, [vp])
        lib.XInitThreads()
        self.lib = lib

    def present(self, ui: UIBuilder) -> None:
        if not isinstance(ui, UIBuilder):
            raise TypeError("NativeWindowBackend requires a UIBuilder")
        with self._lock:
            if self.error is not None:
                raise UIError(f"native window event loop failed: {self.error}")
            if self._stop.is_set():
                raise UIError("native window is closed")
            if self.ui is None:
                self.ui = ui
                try:
                    self._open()
                except Exception:
                    self._release()
                    raise
                self.thread = threading.Thread(target=self._event_loop, name="peacock-native-window", daemon=True)
                self.thread.start()
            elif self.ui is not ui:
                raise UIError("one NativeWindowBackend cannot present multiple UI documents")
            self.present_count += 1
            ui.present()

    def _open(self):
        self._load()
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise UIError("native windows require a working X11 DISPLAY; no display could be opened")
        screen = self.lib.XDefaultScreen(self.display)
        root = self.lib.XRootWindow(self.display, screen)
        ui = self.ui
        self.colormap = self.lib.XDefaultColormap(self.display, screen)
        self.window = self.lib.XCreateSimpleWindow(
            self.display, root, 0, 0, ui.width, ui.height, 0,
            self.lib.XBlackPixel(self.display, screen), self.lib.XWhitePixel(self.display, screen),
        )
        if not self.window:
            raise UIError("XCreateSimpleWindow failed")
        # Exposure, key/button and structure events.
        self.lib.XSelectInput(self.display, self.window, (1 << 15) | (1 << 0) | (1 << 2) | (1 << 3) | (1 << 17))
        title = ui.title.encode("utf-8")[:4096]
        self.lib.XStoreName(self.display, self.window, title)
        net_name = self.lib.XInternAtom(self.display, b"_NET_WM_NAME", 0)
        utf8 = self.lib.XInternAtom(self.display, b"UTF8_STRING", 0)
        if net_name and utf8:
            data = (ctypes.c_ubyte * len(title)).from_buffer_copy(title)
            self.lib.XChangeProperty(self.display, self.window, net_name, utf8, 8, 0, data, len(title))
        self._wm_delete = self.lib.XInternAtom(self.display, b"WM_DELETE_WINDOW", 0)
        protocol = ctypes.c_ulong(self._wm_delete)
        self.lib.XSetWMProtocols(self.display, self.window, ctypes.byref(protocol), 1)
        self.gc = self.lib.XCreateGC(self.display, self.window, 0, None)
        if not self.gc:
            raise UIError("XCreateGC failed")
        self.font = self.lib.XLoadQueryFont(self.display, b"-*-*-*-r-normal--18-*-*-*-*-*-iso10646-1")
        if self.font:
            self.lib.XSetFont(self.display, self.gc, self.font.contents.fid)
        self.lib.XMapWindow(self.display, self.window)
        self.lib.XFlush(self.display)
        self._draw()

    def _pixel(self, color: Color) -> int:
        rgb = tuple(max(0, min(255, round(component * 255))) for component in color.srgb())
        if rgb not in self._pixels:
            value = _XColor()
            value.red, value.green, value.blue = (component * 257 for component in rgb)
            value.flags = b"\x07"
            if not self.lib.XAllocColor(self.display, self.colormap, ctypes.byref(value)):
                raise UIError(f"X11 could not allocate RGB colour {rgb}")
            self._pixels[rgb] = value.pixel
        return self._pixels[rgb]

    def _draw(self):
        ui = self.ui
        if ui is None or not self.display or not self.window or not self.gc:
            return
        with self._lock:
            for node in ui.nodes.values():
                if node.kind not in {"root", "panel", "button", "link"} or node.background is None:
                    continue
                x, y, width, height = ui.bounds(node.id) if node.id else (0, 0, ui.width, ui.height)
                self.lib.XSetForeground(self.display, self.gc, self._pixel(node.background))
                self.lib.XFillRectangle(self.display, self.window, self.gc, round(x), round(y), max(1, round(width)), max(1, round(height)))
                if node.kind in {"button", "link"}:
                    self.lib.XDrawRectangle(self.display, self.window, self.gc, round(x), round(y), max(1, round(width)), max(1, round(height)))
            for node in ui.nodes.values():
                if node.kind not in {"text", "button", "link"} or node.foreground is None:
                    continue
                x, y, _width, height = ui.bounds(node.id)
                units = _utf16_units(node.text[:16384])
                if not units:
                    continue
                data = (_XChar2b * len(units))(*units)
                self.lib.XSetForeground(self.display, self.gc, self._pixel(node.foreground))
                baseline = round(y + min(height - 2, max(node.font_size, 12)))
                self.lib.XDrawString16(self.display, self.window, self.gc, round(x + 4), baseline, data, len(units))
            self.lib.XFlush(self.display)
            self._drawn_revision = ui.revision

    def _key(self, event: _XEvent) -> str:
        buffer = ctypes.create_string_buffer(128)
        keysym = ctypes.c_ulong()
        count = self.lib.XLookupString(ctypes.byref(event.xkey), buffer, len(buffer), ctypes.byref(keysym), None)
        special = {0xFF08: "Backspace", 0xFF09: "Tab", 0xFF0D: "Enter", 0xFF1B: "Escape", 0xFF51: "ArrowLeft", 0xFF52: "ArrowUp", 0xFF53: "ArrowRight", 0xFF54: "ArrowDown"}.get(keysym.value)
        if special:
            return special
        return buffer.raw[:max(0, min(count, 128))].decode("utf-8", "replace")[:128]

    def _dispatch(self, event: _XEvent):
        ui = self.ui
        kind = event.type
        if kind in {4, 5}:  # ButtonPress / ButtonRelease
            x, y = max(0, event.xbutton.x), max(0, event.xbutton.y)
            node = ui.hit_test(x, y)
            ui.post_event("pointer_down" if kind == 4 else "pointer_up", node, x, y)
            if kind == 5 and node >= 0:
                if ui.nodes[node].kind in {"button", "link"}:
                    try:
                        ui.post_event("focus", node, x, y)
                    except UIError:
                        pass  # disabled controls cannot receive focus
                ui.post_event("click", node, x, y)
        elif kind == 2:  # KeyPress
            ui.post_event("key", -1, key=self._key(event))
        elif kind == 33 and event.xclient.data.l[0] == self._wm_delete:
            ui.post_event("close", 0)
            self._stop.set()
        elif kind in {12, 22}:  # Expose / ConfigureNotify
            self._drawn_revision = -1

    def _event_loop(self):
        try:
            while not self._stop.is_set():
                while self.lib.XPending(self.display) and not self._stop.is_set():
                    event = _XEvent()
                    self.lib.XNextEvent(self.display, ctypes.byref(event))
                    self._dispatch(event)
                if self.ui is not None and self.ui.revision != self._drawn_revision:
                    self._draw()
                time.sleep(0.01)
        except Exception as exc:
            self.error = str(exc) or exc.__class__.__name__
            self._stop.set()
        finally:
            self._release()

    def _release(self):
        lib, display = self.lib, self.display
        if lib is None or not display:
            self.display = None
            return
        if self.font:
            lib.XFreeFont(display, self.font)
            self.font = None
        if self.gc:
            lib.XFreeGC(display, self.gc)
            self.gc = None
        if self._pixels and self.colormap:
            pixels = (ctypes.c_ulong * len(self._pixels))(*self._pixels.values())
            lib.XFreeColors(display, self.colormap, pixels, len(self._pixels), 0)
            self._pixels.clear()
        if self.window:
            lib.XDestroyWindow(display, self.window)
            self.window = 0
        lib.XCloseDisplay(display)
        self.display = None

    def close(self):
        self._stop.set()
        thread = self.thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self.thread = None
        if self.display is not None:
            self._release()

    @property
    def url(self) -> str:
        return "x11://native-window"


__all__ = ["NativeWindowBackend"]
