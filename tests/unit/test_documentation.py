"""Documentation, bibliography and language-packaging checks.

These tests keep the claims and cross-references in the repository honest:
relative documentation links must resolve, citations must exist in the
bibliography, the Linguist grammar must parse, the samples must compile with the
real compiler, and the icon must be a valid PNG produced by the project's codec.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from peacock.compiler.pipeline import compile_source
from peacock.frontend.png import decode_png

ROOT = Path(__file__).resolve().parents[2]
DOC_DIRS = ("", "docs", "research", "linguist")

CITATION_RE = re.compile(r"\[([a-z0-9][a-z0-9-]*\d{4}[a-z0-9-]*)\]")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def _markdown_files():
    for rel in DOC_DIRS:
        base = ROOT / rel if rel else ROOT
        for path in sorted(base.glob("*.md")):
            yield path
    for sub in ("docs",):
        for path in sorted((ROOT / sub).rglob("*.md")):
            yield path


class DocumentationTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self) -> None:
        broken = []
        for path in _markdown_files():
            for target in LINK_RE.findall(path.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    broken.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [], "broken relative links:\n" + "\n".join(broken))

    def test_bibliography_has_at_least_100_unique_entries(self) -> None:
        text = (ROOT / "research" / "references.bib").read_text(encoding="utf-8")
        keys = re.findall(r"@\w+\{([^,]+),", text)
        self.assertGreaterEqual(len(keys), 100)
        self.assertEqual(len(keys), len(set(keys)), "duplicate BibTeX keys")
        for key in keys:
            self.assertRegex(key, r"^[a-z0-9][a-z0-9-]*$")

    def test_every_cited_key_exists_in_bibliography(self) -> None:
        bib = (ROOT / "research" / "references.bib").read_text(encoding="utf-8")
        known = set(re.findall(r"@\w+\{([^,]+),", bib))
        missing = {}
        for path in _markdown_files():
            used = set(CITATION_RE.findall(path.read_text(encoding="utf-8")))
            absent = sorted(used - known)
            if absent:
                missing[str(path.relative_to(ROOT))] = absent
        self.assertEqual(missing, {}, f"citation keys missing from references.bib: {missing}")

    def test_linguist_metadata_and_grammar(self) -> None:
        languages = (ROOT / "linguist" / "languages.yml").read_text(encoding="utf-8")
        self.assertIn("Peacock:", languages)
        self.assertIn('".pac"', languages)
        self.assertIn("tm_scope: source.peacock", languages)
        grammar = json.loads((ROOT / "linguist" / "peacock.tmLanguage.json").read_text(encoding="utf-8"))
        self.assertEqual(grammar["scopeName"], "source.peacock")
        self.assertIn("pac", grammar["fileTypes"])
        self.assertIn("patterns", grammar)
        # The editor package ships the same grammar.
        packaged = json.loads(
            (ROOT / "editors" / "vscode" / "syntaxes" / "peacock.tmLanguage.json").read_text(encoding="utf-8")
        )
        self.assertEqual(packaged["scopeName"], grammar["scopeName"])

    def test_linguist_samples_compile_with_the_real_compiler(self) -> None:
        samples = sorted((ROOT / "linguist" / "samples").glob("*.pac"))
        self.assertGreaterEqual(len(samples), 4)
        for path in samples:
            source = path.read_text(encoding="utf-8")
            result = compile_source(source, str(path))
            self.assertTrue(result.ok, f"{path.name} failed to compile:\n{result.diagnostics.render_all(source)}")

    def test_icon_is_a_valid_256px_png(self) -> None:
        data = (ROOT / "assets" / "peacock-256.png").read_bytes()
        width, height, pixels = decode_png(data)
        self.assertEqual((width, height), (256, 256))
        self.assertEqual(len(pixels), 256 * 256 * 4)
        self.assertEqual(pixels[3], 0, "icon should have a transparent corner")


if __name__ == "__main__":
    unittest.main()
