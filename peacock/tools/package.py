"""Deterministic PEACOCK package manager (minimal, honest, zero-budget).

Implements `peacock package` and `peacock install` for the 0.4 language.

A package is a directory containing `peacock.toml` (package manifest) and
`.सूत्र` sources. The tool validates, fingerprints, and copies sources—no network,
no hidden downloads, no paid APIs.

This is a foundation, not a full registry. It is deterministic: the same sources
produce the same fingerprint; installs are verified against that fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import re
from pathlib import Path
from typing import Any

from peacock.sanskrit import SOURCE_EXTENSION
from peacock.compiler.pipeline import compile_source

_KEYVAL_RE = re.compile(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*["\'](.*?)["\']\s*(?:#.*)?$')
_SECTION_RE = re.compile(r'^\s*\[([a-zA-Z0-9_.-]+)\]\s*(?:#.*)?$')


def parse_toml(text: str) -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = {}
    current = ""
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m_sec = _SECTION_RE.match(line)
        if m_sec:
            current = m_sec.group(1)
            data.setdefault(current, {})
            continue
        m_kv = _KEYVAL_RE.match(line)
        if m_kv:
            k, v = m_kv.group(1), m_kv.group(2)
            if not current:
                raise ValueError(f"line {lineno}: key/value outside section: {raw!r}")
            data[current][k] = v
            continue
        if "=" in line or line.startswith("["):
            raise ValueError(f"line {lineno}: cannot parse: {raw!r}")
    return data


def load_manifest(project_dir: Path) -> dict[str, Any]:
    toml_path = project_dir / "peacock.toml"
    if not toml_path.is_file():
        raise FileNotFoundError(f"no peacock.toml in {project_dir}")
    text = toml_path.read_text(encoding="utf-8")
    data = parse_toml(text)
    pkg = data.get("package", {})
    if "name" not in pkg:
        raise ValueError("peacock.toml [package] missing 'name'")
    if "version" not in pkg:
        raise ValueError("peacock.toml [package] missing 'version'")
    pkg.setdefault("language", "0.4")
    return data


def collect_sources(project_dir: Path, exclude_dirs: tuple[str, ...] = ("out", "dist", "target", "__pycache__", ".git", "peacock_modules")) -> list[Path]:
    sources: list[Path] = []
    for p in sorted(project_dir.rglob(f"*{SOURCE_EXTENSION}")):
        if any(ex in p.parts for ex in exclude_dirs):
            continue
        sources.append(p)
    return sources


def fingerprint_sources(sources: list[Path], project_dir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(sources, key=lambda x: x.relative_to(project_dir).as_posix()):
        rel = p.relative_to(project_dir).as_posix().encode()
        h.update(rel + b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def validate_sources(sources: list[Path], project_dir: Path) -> list[dict[str, Any]]:
    results = []
    for p in sources:
        src = p.read_text(encoding="utf-8")
        res = compile_source(src, str(p))
        diags = []
        for d in res.diagnostics:
            diags.append({"code": d.code, "severity": d.severity.value, "message": d.message, "line": d.span.line, "column": d.span.column})
        results.append({
            "path": str(p.relative_to(project_dir)),
            "ok": res.ok,
            "diagnostics": diags,
            "stats": res.stats,
        })
        if not res.ok:
            results[-1]["render"] = res.diagnostics.render_all(src)
    return results


def package_project(project_dir: Path, out_dir: Path | None = None) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    data = load_manifest(project_dir)
    pkg = data["package"]
    sources = collect_sources(project_dir)
    if not sources:
        raise ValueError(f"no {SOURCE_EXTENSION} sources found in {project_dir}")
    validation = validate_sources(sources, project_dir)
    failed = [r for r in validation if not r["ok"]]
    if failed:
        raise ValueError(f"validation failed for {len(failed)} file(s): " + ", ".join(r["path"] for r in failed))
    fingerprint = fingerprint_sources(sources, project_dir)
    manifest = {
        "name": pkg["name"],
        "version": pkg["version"],
        "language": pkg.get("language", "0.4"),
        "fingerprint": fingerprint,
        "fingerprint_algo": "sha256",
        "sources": [str(p.relative_to(project_dir)) for p in sources],
        "dependencies": data.get("dependencies", {}),
        "build": data.get("build", {}),
    }
    if out_dir is not None:
        out_dir = out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{pkg['name']}-{pkg['version']}.json"
        out_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest["_out_file"] = str(out_file)
    return manifest


def install_package(package_path: Path, project_dir: Path, dest_name: str | None = None) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    package_path = package_path.resolve()
    if package_path.is_file() and package_path.suffix == ".json":
        manifest = json.loads(package_path.read_text(encoding="utf-8"))
        src_root = package_path.parent
        if "name" not in manifest:
            raise ValueError("manifest missing 'name'")
        name = dest_name or manifest["name"]
    elif package_path.is_dir():
        manifest = package_project(package_path)
        src_root = package_path
        name = dest_name or manifest["name"]
    else:
        raise ValueError(f"package path must be a directory or manifest.json, got {package_path}")
    sources = collect_sources(src_root)
    expected = manifest.get("fingerprint")
    if expected:
        actual = fingerprint_sources(sources, src_root)
        if actual != expected:
            raise ValueError(f"fingerprint mismatch: expected {expected}, got {actual}")
    dest = project_dir / "peacock_modules" / name
    dest.mkdir(parents=True, exist_ok=True)
    for src in sources:
        rel = src.relative_to(src_root)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (dest / "peacock.install.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"installed_to": str(dest), "manifest": manifest, "files": [str(s.relative_to(src_root)) for s in sources]}
