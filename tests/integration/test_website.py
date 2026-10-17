"""End-to-end checks for the PEACOCK-authored static website export."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest

from tests.integration.test_cli import run_cli
from tests.support import REPO_ROOT


ROUTES = {
    "index.html",
    "language.html",
    "compiler.html",
    "ai-engine.html",
    "frontend-studio.html",
    "docs.html",
    "examples.html",
    "research.html",
    "roadmap.html",
    "security.html",
    "download.html",
    "community.html",
}


class PageAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.title_parts: list[str] = []
        self.title_count = 0
        self.h1_count = 0
        self.main_ids: list[str] = []
        self.nav_labels: list[str] = []
        self.current_routes = 0
        self.nav_link_count = 0
        self.script_count = 0
        self.images_have_alt = True
        self.code_parts: list[str] = []
        self._in_title = False
        self._in_code = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
            if "nav-link" in attrs.get("class", "").split():
                self.nav_link_count += 1
                if attrs.get("aria-current") == "page":
                    self.current_routes += 1
        if tag == "title":
            self.title_count += 1
            self._in_title = True
        if tag == "h1":
            self.h1_count += 1
        if tag == "main":
            self.main_ids.append(attrs.get("id", ""))
        if tag == "nav":
            self.nav_labels.append(attrs.get("aria-label", ""))
        if tag == "script":
            self.script_count += 1
        if tag == "img" and "alt" not in attrs:
            self.images_have_alt = False
        if tag == "code":
            self._in_code += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "code" and self._in_code:
            self._in_code -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_code:
            self.code_parts.append(data)


class PeacockWebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix=".website-test-", dir=REPO_ROOT)
        relative_temp = Path(cls._temp.name).relative_to(REPO_ROOT)
        cls.output_dir = REPO_ROOT / relative_temp / "site"
        result = run_cli(
            "run",
            "website/site.pac",
            "--grant",
            "fs",
            "--root",
            str(REPO_ROOT),
            "--max-steps",
            "10000000",
            "--",
            str(relative_temp / "site"),
            timeout=180,
        )
        if result.returncode != 0:
            cls._temp.cleanup()
            raise AssertionError(f"PEACOCK website build failed:\n{result.stderr}\n{result.stdout}")
        cls.build_output = result.stdout

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def test_site_source_is_genuine_pac_and_builds_twelve_routes(self):
        source = (REPO_ROOT / "website/site.pac").read_text(encoding="utf-8")
        self.assertIn("fn render_page(", source)
        self.assertIn("fn site_pages(", source)
        self.assertIn("fn stylesheet(", source)
        self.assertIn("renderer_self_test();", source)
        pages = {path.name for path in self.output_dir.glob("*.html")}
        self.assertEqual(pages, ROUTES)
        self.assertTrue((self.output_dir / "styles.css").is_file())
        self.assertTrue((self.output_dir / "assets/peacock.svg").is_file())
        self.assertIn("Built 12 PEACOCK-authored pages", self.build_output)
        self.assertFalse(list(self.output_dir.rglob("*.js")))

    def test_all_routes_have_accessible_navigation_and_no_broken_internal_links(self):
        for route in sorted(ROUTES):
            path = self.output_dir / route
            parser = PageAudit()
            parser.feed(path.read_text(encoding="utf-8"))
            with self.subTest(route=route):
                self.assertEqual(parser.title_count, 1)
                self.assertTrue("".join(parser.title_parts).strip())
                self.assertEqual(parser.h1_count, 1)
                self.assertEqual(parser.main_ids, ["main"])
                self.assertEqual(parser.nav_labels, ["Primary"])
                self.assertEqual(parser.current_routes, 1)
                self.assertEqual(parser.nav_link_count, 12)
                self.assertEqual(parser.script_count, 0)
                self.assertTrue(parser.images_have_alt)
                for href in parser.links:
                    if href.startswith(("https://", "http://", "mailto:")):
                        continue
                    route_part, separator, fragment = href.partition("#")
                    if route_part:
                        target = self.output_dir / route_part
                        self.assertTrue(target.is_file(), f"{route}: broken link {href}")
                    else:
                        target = path
                    if separator and fragment:
                        target_parser = PageAudit()
                        target_parser.feed(target.read_text(encoding="utf-8"))
                        self.assertIn(fragment, target_parser.ids, f"{route}: broken fragment {href}")

    def test_real_pac_examples_are_embedded_as_selectable_text(self):
        source = (REPO_ROOT / "examples/hello.pac").read_text(encoding="utf-8")
        parser = PageAudit()
        parser.feed((self.output_dir / "language.html").read_text(encoding="utf-8"))
        rendered_code = "".join(parser.code_parts)
        self.assertIn("print(\"Hello from PEACOCK\")", rendered_code)
        self.assertIn("fn main()", rendered_code)
        self.assertIn("Selectable source", (self.output_dir / "language.html").read_text())
        self.assertIn("Hello from PEACOCK", source)

    def test_responsive_accessible_css_includes_reduced_motion_and_focus_states(self):
        css = (self.output_dir / "styles.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 1050px)", css)
        self.assertIn("@media (max-width: 680px)", css)
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("scrollbar-width: thin", css)


if __name__ == "__main__":
    unittest.main()
