"""Deterministic retained-mode UI trees with layout, audit and HTML export.

The builder is intentionally dependency-free.  It produces responsive,
script-free HTML whose text remains Unicode/Sanskrit, and provides native layout
and hit-testing before export.  Buttons are semantic preview components; this
module does not invent an event loop or claim a native windowing backend.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from html import escape
import math
import threading
import time
from urllib.parse import urlsplit

from .colour import Color, ColorError


class UIError(ValueError):
    pass


@dataclass(slots=True)
class UINode:
    id: int
    kind: str
    parent: int
    x: float
    y: float
    width: float
    height: float
    text: str = ""
    foreground: Color | None = None
    background: Color | None = None
    font_size: float = 18.0
    href: str | None = None
    children: list[int] = field(default_factory=list)
    enabled: bool = True


@dataclass(slots=True, frozen=True)
class UIEvent:
    id: int
    kind: str
    node: int
    x: float
    y: float
    key: str
    text: str
    handler: int
    action: str

    def as_strings(self) -> list[str]:
        """Stable homogeneous record exposed to `.सूत्र` programs."""

        return [
            str(self.id), self.kind, str(self.node), str(self.x), str(self.y),
            self.key, self.text, str(self.handler), self.action,
        ]


class UIBuilder:
    def __init__(self, title: str, width: int, height: int, background: Color):
        if not isinstance(title, str) or not title.strip():
            raise UIError("UI title must be non-empty")
        if not isinstance(width, int) or not isinstance(height, int) or not (1 <= width <= 8192 and 1 <= height <= 8192):
            raise UIError("UI dimensions must be integers between 1 and 8192")
        if not isinstance(background, Color):
            raise UIError("UI background must be a colour")
        self.title = title.strip()
        self.width, self.height = width, height
        self.nodes: dict[int, UINode] = {
            0: UINode(0, "root", -1, 0.0, 0.0, float(width), float(height), background=background)
        }
        self._events: deque[UIEvent] = deque()
        self._bindings: dict[tuple[int, str], str] = {}
        self._condition = threading.Condition()
        self._next_event_id = 1
        self.focus_node = -1
        self.revision = 0
        self.max_events = 1024

    def _touch(self) -> None:
        with self._condition:
            self.revision += 1
            self._condition.notify_all()

    def _number(self, value: float, name: str, minimum: float = 0.0) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
            raise UIError(f"{name} must be finite and at least {minimum}")
        return float(value)

    def _parent(self, node_id: int) -> UINode:
        node = self.nodes.get(node_id)
        if node is None:
            raise UIError(f"unknown UI node {node_id}")
        if node.kind not in ("root", "panel"):
            raise UIError(f"UI {node.kind} node {node_id} cannot have children")
        return node

    def _add(self, node: UINode) -> int:
        if len(self.nodes) >= 10_000:
            raise UIError("UI node limit is 10000 including the root")
        parent = self._parent(node.parent)
        node.x = self._number(node.x, "x")
        node.y = self._number(node.y, "y")
        node.width = self._number(node.width, "width", 1e-6)
        node.height = self._number(node.height, "height", 1e-6)
        self.nodes[node.id] = node
        parent.children.append(node.id)
        self._touch()
        return node.id

    def panel(self, parent: int, x: float, y: float, width: float, height: float, background: Color) -> int:
        if not isinstance(background, Color):
            raise UIError("panel background must be a colour")
        return self._add(UINode(len(self.nodes), "panel", parent, x, y, width, height, background=background))

    def text(self, parent: int, text: str, x: float, y: float, width: float, height: float, color: Color, size: float = 18.0) -> int:
        if not isinstance(text, str) or not isinstance(color, Color):
            raise UIError("text requires a string and foreground colour")
        size = self._number(size, "font size", 1.0)
        if size > 256.0:
            raise UIError("font size is limited to 256")
        return self._add(UINode(len(self.nodes), "text", parent, x, y, width, height, text=text, foreground=color, font_size=size))

    def button(self, parent: int, label: str, x: float, y: float, width: float, height: float, background: Color, foreground: Color) -> int:
        if not isinstance(label, str) or not isinstance(background, Color) or not isinstance(foreground, Color):
            raise UIError("button requires a label and two colours")
        return self._add(UINode(len(self.nodes), "button", parent, x, y, width, height, text=label, foreground=foreground, background=background))

    def link(self, parent: int, label: str, href: str, x: float, y: float, width: float, height: float, color: Color, size: float = 18.0) -> int:
        if not isinstance(label, str) or not isinstance(href, str) or not isinstance(color, Color):
            raise UIError("link requires label, target and colour")
        parsed = urlsplit(href)
        if parsed.scheme and parsed.scheme.lower() not in ("https", "http", "mailto"):
            raise UIError("link targets allow relative URLs, https, http and mailto only")
        if href.strip().lower().startswith(("javascript:", "data:", "vbscript:")):
            raise UIError("active-content link targets are not allowed")
        size = self._number(size, "font size", 1.0)
        return self._add(UINode(len(self.nodes), "link", parent, x, y, width, height, text=label, foreground=color, font_size=size, href=href))

    def flow(self, parent: int, direction: str = "column", gap: float = 0.0, padding: float = 0.0) -> None:
        container = self._parent(parent)
        if direction not in ("column", "row"):
            raise UIError("flow direction must be column or row")
        gap = self._number(gap, "layout gap")
        padding = self._number(padding, "layout padding")
        cursor = padding
        for child_id in container.children:
            child = self.nodes[child_id]
            if direction == "column":
                child.x, child.y = padding, cursor
                cursor += child.height + gap
            else:
                child.x, child.y = cursor, padding
                cursor += child.width + gap
        self._touch()

    def grid(self, parent: int, columns: int = 2, gap: float = 0.0, padding: float = 0.0) -> None:
        container = self._parent(parent)
        if not isinstance(columns, int) or isinstance(columns, bool) or not 1 <= columns <= 64:
            raise UIError("grid columns must be an integer between 1 and 64")
        gap = self._number(gap, "grid gap")
        padding = self._number(padding, "grid padding")
        available = container.width - 2.0 * padding - (columns - 1) * gap
        if available <= 0.0:
            raise UIError("grid padding and gaps leave no room for columns")
        cell_width = available / columns
        cursor = padding
        row_height = 0.0
        for index, child_id in enumerate(container.children):
            column = index % columns
            if column == 0 and index:
                cursor += row_height + gap
                row_height = 0.0
            child = self.nodes[child_id]
            child.x = padding + column * (cell_width + gap)
            child.y = cursor
            child.width = cell_width
            row_height = max(row_height, child.height)
        self._touch()

    def bounds(self, node_id: int) -> tuple[float, float, float, float]:
        node = self.nodes.get(node_id)
        if node is None:
            raise UIError(f"unknown UI node {node_id}")
        x, y = node.x, node.y
        parent = node.parent
        while parent > 0:
            ancestor = self.nodes[parent]
            x += ancestor.x
            y += ancestor.y
            parent = ancestor.parent
        return x, y, node.width, node.height

    def hit_test(self, x: float, y: float) -> int:
        x = self._number(x, "hit-test x")
        y = self._number(y, "hit-test y")
        for node_id in reversed(self.nodes):
            if node_id == 0:
                continue
            nx, ny, width, height = self.bounds(node_id)
            if nx <= x < nx + width and ny <= y < ny + height:
                return node_id
        return -1

    def _node(self, node_id: int) -> UINode:
        if isinstance(node_id, bool) or not isinstance(node_id, int) or node_id not in self.nodes:
            raise UIError(f"unknown UI node {node_id}")
        return self.nodes[node_id]

    def bind(self, node_id: int, kind: str, action: str) -> None:
        self._node(node_id)
        if kind not in {"click", "pointer_down", "pointer_up", "key", "text", "focus", "submit", "close", "*"}:
            raise UIError(f"unsupported UI event kind {kind!r}")
        if not isinstance(action, str) or not action.strip() or len(action) > 256:
            raise UIError("UI action must be a non-empty string of at most 256 characters")
        self._bindings[(node_id, kind)] = action.strip()
        self._touch()

    def set_text(self, node_id: int, text: str) -> None:
        node = self._node(node_id)
        if node.kind not in {"text", "button", "link"}:
            raise UIError("only text, button and link nodes accept text mutation")
        if not isinstance(text, str) or len(text) > 100_000:
            raise UIError("UI text must be a string of at most 100000 characters")
        node.text = text
        self._touch()

    def set_enabled(self, node_id: int, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise UIError("UI enabled state must be सत्यता")
        self._node(node_id).enabled = enabled
        self._touch()

    def focus(self, node_id: int) -> None:
        node = self._node(node_id)
        if node.kind not in {"button", "link"} or not self._enabled_in_tree(node_id):
            raise UIError("only enabled button/link nodes can receive focus")
        self.focus_node = node_id
        self._touch()

    def pending_events(self) -> int:
        with self._condition:
            return len(self._events)

    def _enabled_in_tree(self, node_id: int) -> bool:
        current = node_id
        while current >= 0:
            if not self.nodes[current].enabled:
                return False
            current = self.nodes[current].parent
        return True

    def _action(self, node_id: int, kind: str) -> tuple[int, str]:
        if not self._enabled_in_tree(node_id):
            return -1, ""
        current = node_id
        while current >= 0:
            binding = self._bindings.get((current, kind)) or self._bindings.get((current, "*"))
            if binding is not None:
                return current, binding
            current = self.nodes[current].parent
        return -1, ""

    def post_event(
        self,
        kind: str,
        node_id: int = -1,
        x: float = 0.0,
        y: float = 0.0,
        key: str = "",
        text: str = "",
    ) -> int:
        if kind not in {"click", "pointer_down", "pointer_up", "key", "text", "focus", "submit", "close"}:
            raise UIError(f"unsupported UI event kind {kind!r}")
        x, y = self._number(x, "event x"), self._number(y, "event y")
        if not isinstance(key, str) or not isinstance(text, str) or len(key) > 128 or len(text) > 16_384:
            raise UIError("UI event key/text limits exceeded")
        if node_id == -1:
            node_id = self.focus_node if kind in {"key", "text"} else self.hit_test(x, y)
        if node_id != -1:
            self._node(node_id)
        if kind == "focus" and node_id >= 0:
            self.focus(node_id)
        handler, action = self._action(node_id, kind) if node_id >= 0 else (-1, "")
        with self._condition:
            if len(self._events) >= self.max_events:
                raise UIError("UI event queue is full")
            event_id = self._next_event_id
            self._next_event_id += 1
            self._events.append(UIEvent(event_id, kind, node_id, x, y, key, text, handler, action))
            self._condition.notify_all()
        return event_id

    def next_event(self, timeout_ms: int = 0) -> UIEvent | None:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 0 <= timeout_ms <= 60_000:
            raise UIError("UI event timeout must be an integer from 0 to 60000 ms")
        deadline = time.monotonic() + timeout_ms / 1000.0
        with self._condition:
            while not self._events:
                remaining = deadline - time.monotonic()
                if timeout_ms == 0 or remaining <= 0:
                    return None
                self._condition.wait(remaining)
            return self._events.popleft()

    def present(self) -> None:
        """Publish the current revision to an attached interactive host."""

        self._touch()

    def _background(self, node: UINode) -> Color:
        current: UINode | None = node
        while current is not None:
            if current.background is not None:
                return current.background
            current = self.nodes.get(current.parent) if current.parent >= 0 else None
        return Color.from_srgb(1.0, 1.0, 1.0)

    def audit(self) -> list[str]:
        findings: list[str] = []
        for node_id, node in self.nodes.items():
            if node_id == 0:
                continue
            parent = self.nodes[node.parent]
            if node.x < 0 or node.y < 0 or node.x + node.width > parent.width + 1e-6 or node.y + node.height > parent.height + 1e-6:
                findings.append(f"UI-OVERFLOW node={node_id} parent={parent.id}")
            if node.kind in ("text", "button", "link"):
                if not node.text.strip():
                    findings.append(f"UI-EMPTY-LABEL node={node_id}")
                assert node.foreground is not None
                ratio = node.foreground.contrast_ratio(self._background(node))
                if ratio < 4.5:
                    findings.append(f"UI-CONTRAST node={node_id} ratio={ratio:.2f} minimum=4.50")
            if node.kind in ("button", "link") and (node.width < 44.0 or node.height < 44.0):
                findings.append(f"UI-TOUCH-TARGET node={node_id} minimum=44x44")
        return findings

    def to_html(self) -> str:
        css = """
:root{color-scheme:light dark;font-family:system-ui,-apple-system,'Noto Sans Devanagari',sans-serif}
*{box-sizing:border-box}body{margin:0;padding:clamp(12px,3vw,36px);background:#10161a;display:grid;place-items:center;min-height:100vh}
.peacock-ui{position:relative;width:min(100%,var(--ui-width));aspect-ratio:var(--ui-ratio);container-type:inline-size;overflow:hidden;border-radius:16px;box-shadow:0 20px 70px #0008}
.peacock-ui [data-node]{position:absolute;margin:0;overflow-wrap:anywhere}
.peacock-ui [data-kind=panel]{border-radius:2.2cqw}
.peacock-ui [data-kind=text],.peacock-ui [data-kind=link]{display:flex;align-items:center;line-height:1.35}
.peacock-ui [data-kind=button]{border:0;border-radius:1.6cqw;font:inherit;font-weight:650;cursor:pointer}
.peacock-ui a{color:inherit;text-decoration-thickness:.08em;text-underline-offset:.15em}
.peacock-ui :focus-visible{outline:3px solid #ffbf47;outline-offset:3px}
@media(max-width:540px){body{padding:0}.peacock-ui{border-radius:0;box-shadow:none}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
""".strip()

        def style(node: UINode, parent: UINode) -> str:
            values = {
                "left": f"{node.x / parent.width * 100.0:.6f}%",
                "top": f"{node.y / parent.height * 100.0:.6f}%",
                "width": f"{node.width / parent.width * 100.0:.6f}%",
                "height": f"{node.height / parent.height * 100.0:.6f}%",
                "font-size": f"{node.font_size / self.width * 100.0:.4f}cqw",
            }
            if node.background is not None:
                values["background"] = node.background.to_css()
            if node.foreground is not None:
                values["color"] = node.foreground.to_css()
            return ";".join(f"{key}:{value}" for key, value in values.items())

        def render(node_id: int) -> str:
            node = self.nodes[node_id]
            parent = self.nodes[node.parent]
            common = f'data-node="{node.id}" data-kind="{node.kind}" style="{style(node, parent)}"'
            content = escape(node.text)
            children = "".join(render(child) for child in node.children)
            if node.kind == "panel":
                return f'<section {common} aria-label="पटल {node.id}">{children}</section>'
            if node.kind == "button":
                disabled = "" if self._enabled_in_tree(node.id) else ' disabled aria-disabled="true"'
                return f'<button {common} type="button"{disabled}>{content}</button>'
            if node.kind == "link":
                disabled = "" if self._enabled_in_tree(node.id) else ' aria-disabled="true" tabindex="-1"'
                return f'<a {common} href="{escape(node.href or "", quote=True)}"{disabled}>{content}</a>'
            return f'<p {common}>{content}</p>'

        body = "".join(render(node_id) for node_id in self.nodes[0].children)
        background = self.nodes[0].background.to_css() if self.nodes[0].background else "white"
        return (
            "<!doctype html>\n<html lang=\"sa\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<meta name=\"generator\" content=\"PEACOCK दृश्य\"><title>{escape(self.title)}</title>"
            f"<style>{css}</style></head><body><main class=\"peacock-ui\" "
            f"style=\"--ui-width:{self.width}px;--ui-ratio:{self.width}/{self.height};background:{background}\" "
            f"aria-label=\"{escape(self.title, quote=True)}\">{body}</main></body></html>\n"
        )

    def to_fragment(self) -> str:
        """Return the current `<main>` subtree for interactive host refreshes."""

        html = self.to_html()
        start = html.index("<main ")
        end = html.rindex("</main>") + len("</main>")
        return html[start:end]
