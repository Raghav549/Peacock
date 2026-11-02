"""Phase C bootstrap harness — PEACOCK compiles its own compiler.

This is the first PEACOCK-native bootstrap.  It uses the existing Python
toolchain (the oracle) to build the selfhost kernels, then invokes the
PEACOCK-native pipeline (`selfhost/pipeline.सूत्र`) via the VM to re-compile
the same sources.  Outputs are compared as canonical ``.बीज`` artifact bytes
(``image_to_bytes``) for reproducibility — the bootstrap fixed-point.

Current status (2026-11-02): the PEACOCK pipeline is a deterministic
wiring stub (lex→parse→type→ir→bytecode→opt→vm via the selfhost kernels);
full semantic parity is still Python-authoritative (see AUDIT.md).  The
harness therefore checks strict fixed-point for the Python oracle and
strict digest parity via `pipeline_digest` (tag-chain) — the gate that will
become full ``.बीज`` parity once the type-model shadow covers all
natives/members/models.  Large selfhost sources (up to 60K) are handled via
chunked string literals (CHUNK_SIZE) and hash/len parity to avoid single-
literal limits and output truncation.

Usage:
    python -m peacock.tools.bootstrap            # check all selfhost/*.सूत्र
    python -m peacock.tools.bootstrap --write    # also emit .बीज to build/bootstrap/
    python -m peacock.tools.bootstrap --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from peacock.compiler.pipeline import compile_source
from peacock.runtime.artifact import image_to_bytes, image_from_bytes
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM

REPO_ROOT = Path(__file__).resolve().parents[2]
SELFHOST = REPO_ROOT / "selfhost"
BUILD_BOOTSTRAP = REPO_ROOT / "build" / "bootstrap"

# Chunk size for PEACOCK string literals — avoids single-literal limits and
# makes the VM wrapper robust for 60K+ sources.  500 chars keeps each
# literal well under any implicit limit while keeping chunk count manageable.
CHUNK_SIZE = 500

def _compile_python(path: Path):
    src = path.read_text(encoding="utf-8")
    res = compile_source(src, str(path))
    if not res.ok:
        raise RuntimeError(f"Python compile failed for {path}: {res.diagnostics.render_all(src)}")
    return res

def _artifact_digest(image: dict) -> str:
    payload = json.dumps(image, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

# --- Python mirror of selfhost/pipeline.सूत्र pipeline_digest ---
def _stage_py(name: str, inp: str) -> str:
    return f"({name} {inp})"

def _compile_py(source: str) -> str:
    t = _stage_py("lex", source)
    p = _stage_py("parse", t)
    s = _stage_py("type", p)
    i = _stage_py("ir", s)
    b = _stage_py("bytecode", i)
    o = _stage_py("opt", b)
    v = _stage_py("vm", o)
    return v

def pipeline_digest_py(source: str) -> str:
    compiled = _compile_py(source)
    return f"{compiled} [{len(compiled)}]"

def pipeline_digest_hash_py(source: str) -> tuple[str, int]:
    """Hash/len parity for pipeline_digest — Python oracle."""
    d = pipeline_digest_py(source)
    h = hashlib.sha256(d.encode("utf-8")).hexdigest()[:16]
    return h, len(d)

def _escape_peacock_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

def _chunked_peacock_expr(s: str) -> str:
    """Return a PEACOCK expression that reconstructs s via chunked literals.

    Splits s into CHUNK_SIZE pieces, escapes each, and joins with ` + `.
    This avoids a single huge string literal and is robust for 60K+ sources
    where a lone literal might hit lexer or diagnostic limits.
    """
    if not s:
        return '""'
    chunks = []
    for i in range(0, len(s), CHUNK_SIZE):
        chunk = s[i:i+CHUNK_SIZE]
        escaped = _escape_peacock_string(chunk)
        chunks.append(f'"{escaped}"')
    if len(chunks) == 1:
        return chunks[0]
    return " + ".join(chunks)

def _run_peacock_pipeline(source: str) -> str:
    """Run selfhost/pipeline.सूत्र via the VM and return its pipeline_digest(source).

    Uses chunked literals to handle large sources (vm.सूत्र 41K, parser 33K, etc.)
    without hitting PE1021 single-literal span or PE1002 escape issues.
    """
    from peacock.compiler.pipeline import compile_source as cs
    pipeline_path = SELFHOST / "pipeline.सूत्र"
    pipeline_src = pipeline_path.read_text(encoding="utf-8")
    compiled = cs(pipeline_src, str(pipeline_path))
    if not compiled.ok:
        raise RuntimeError(f"Pipeline kernel failed to compile: {compiled.diagnostics.render_all(pipeline_src)}")
    marker = "कार्य मुख्य() -> एकक {"
    idx = pipeline_src.rfind(marker)
    if idx < 0:
        raise RuntimeError("pipeline.सूत्र missing मुख्य")
    lib = pipeline_src[:idx]
    chunked_expr = _chunked_peacock_expr(source)
    wrapper = f'कार्य मुख्य() -> एकक {{\n    स्थापय src = {chunked_expr};\n    मुद्रय(pipeline_digest(src));\n}}\n'
    combined = lib + wrapper
    compiled2 = cs(combined, "<pipeline-wrapper>")
    if not compiled2.ok:
        raise RuntimeError(f"Wrapper compile failed: {compiled2.diagnostics.render_all(combined)}")
    out = io.StringIO()
    VM(compiled2.image, HostPolicy(root=str(REPO_ROOT), max_steps=20_000_000), stdout=out).run()
    return out.getvalue().strip()

def _run_peacock_pipeline_hash_len(source: str) -> tuple[str, int, str]:
    """Return (peacock_digest, peacock_hash, peacock_len) via chunked wrapper.

    The PEACOCK side returns the full digest; we compute hash/len on the Python
    side for parity.  This is the hash/len-based strict gate that avoids
    comparing huge strings byte-for-byte in the harness output.
    """
    d = _run_peacock_pipeline(source)
    h = hashlib.sha256(d.encode("utf-8")).hexdigest()[:16]
    return d, h, len(d)

def bootstrap(check_peacock: bool = True, write: bool = False, verbose: bool = False, strict: bool = True) -> dict:
    programs = sorted(SELFHOST.glob("*.सूत्र"))
    results = []
    all_ok = True
    peacock_ok = True

    # Strict check on a small synthetic source (fits in single literal) — fast gate
    strict_source = "hello"
    strict_py = pipeline_digest_py(strict_source)
    strict_py_hash, strict_py_len = pipeline_digest_hash_py(strict_source)
    strict_peacock = None
    strict_peacock_hash = None
    strict_peacock_len = None
    strict_match = None
    if check_peacock:
        try:
            strict_peacock = _run_peacock_pipeline(strict_source)
            strict_peacock_hash = hashlib.sha256(strict_peacock.encode("utf-8")).hexdigest()[:16]
            strict_peacock_len = len(strict_peacock)
            # Hash/len parity: more robust than full string compare for large outputs
            strict_match = (strict_py == strict_peacock) and (strict_py_hash == strict_peacock_hash) and (strict_py_len == strict_peacock_len)
            if strict and not strict_match:
                peacock_ok = False
                if verbose:
                    print(f"STRICT MISMATCH synthetic: py {strict_py!r} != peacock {strict_peacock!r} (hash {strict_py_hash} vs {strict_peacock_hash} len {strict_py_len} vs {strict_peacock_len})", file=sys.stderr)
            elif not strict and not (strict_py and strict_peacock):
                peacock_ok = False
        except Exception as exc:
            peacock_ok = False
            if verbose:
                print(f"PEACOCK strict fail synthetic: {exc}", file=sys.stderr)
            strict_match = False
            strict_peacock = f"error:{exc}"

    for path in programs:
        res1 = _compile_python(path)
        b1 = image_to_bytes(res1.image)
        res2 = _compile_python(path)
        b2 = image_to_bytes(res2.image)
        if b1 != b2:
            all_ok = False
            if verbose:
                print(f"FAIL fixed-point {path.name}", file=sys.stderr)
        img_rt = image_from_bytes(b1)
        b_rt = image_to_bytes(img_rt)
        if b_rt != b1:
            all_ok = False
            if verbose:
                print(f"FAIL round-trip {path.name}", file=sys.stderr)

        digest_py = _artifact_digest(res1.image)
        src_text = path.read_text(encoding="utf-8")
        # Python-side full pipeline digest (for reference)
        pipeline_py = pipeline_digest_py(src_text)
        pipeline_py_hash, pipeline_py_len = pipeline_digest_hash_py(src_text)
        digest_peacock = None
        pipeline_peacock_hash = None
        pipeline_peacock_len = None
        # Per-file strict is now full-source via chunked literals + hash/len parity
        per_file_strict = None
        lenient_match = None
        if check_peacock:
            try:
                # Strict: full source via chunked literals, hash/len parity
                peacock_digest, peacock_hash, peacock_len = _run_peacock_pipeline_hash_len(src_text)
                digest_peacock = peacock_digest
                pipeline_peacock_hash = peacock_hash
                pipeline_peacock_len = peacock_len
                per_file_strict = (pipeline_py == peacock_digest) and (pipeline_py_hash == peacock_hash) and (pipeline_py_len == peacock_len)
                # Lenient is the pipeline's own checks (still valid)
                from peacock.compiler.pipeline import compile_source as cs
                pipeline_path = SELFHOST / "pipeline.सूत्र"
                pipeline_src = pipeline_path.read_text(encoding="utf-8")
                compiled = cs(pipeline_src, str(pipeline_path))
                out = io.StringIO()
                VM(compiled.image, HostPolicy(root=str(REPO_ROOT), max_steps=5_000_000), stdout=out).run()
                lenient_out = out.getvalue().strip()
                lenient_match = bool(lenient_out and "PEACOCK pipeline checks passed" in lenient_out)
                if not lenient_match:
                    lenient_match = per_file_strict
                if strict and not per_file_strict:
                    peacock_ok = False
                    if verbose:
                        print(f"STRICT MISMATCH {path.name}: py hash {pipeline_py_hash} len {pipeline_py_len} vs peacock hash {pipeline_peacock_hash} len {pipeline_peacock_len}", file=sys.stderr)
            except Exception as exc:
                if verbose:
                    print(f"PEACOCK pipeline strict fail {path.name}: {exc}", file=sys.stderr)
                per_file_strict = False
                lenient_match = False
                digest_peacock = f"error:{exc}"
                if strict:
                    peacock_ok = False
            # For strict mode, the gate is per-file strict (full-source)
            if strict and per_file_strict is not None and not per_file_strict:
                peacock_ok = False

        if write:
            out_path = BUILD_BOOTSTRAP / (path.stem + ".बीज")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b1)

        entry = {
            "program": path.name,
            "instructions": res1.stats.get("instructions", 0),
            "functions": res1.stats.get("functions", 0),
            "digest_py": digest_py[:16],
            "pipeline_py": pipeline_py[:40],
            "pipeline_py_hash": pipeline_py_hash,
            "pipeline_py_len": pipeline_py_len,
            "pipeline_peacock": (digest_peacock[:40] if digest_peacock else None),
            "pipeline_peacock_hash": pipeline_peacock_hash,
            "pipeline_peacock_len": pipeline_peacock_len,
            "strict_match": per_file_strict if per_file_strict is not None else strict_match,
            "lenient_match": lenient_match,
            "bytes": len(b1),
            "fixed_point": b1 == b2,
        }
        results.append(entry)
        if verbose:
            print(f"{path.name}: {entry['instructions']} instr, pipeline strict {entry['strict_match']} (hash {pipeline_py_hash} vs {pipeline_peacock_hash} len {pipeline_py_len} vs {pipeline_peacock_len}), lenient {lenient_match}, fixed-point {entry['fixed_point']}")

    summary = {
        "programs": len(programs),
        "python_fixed_point": all_ok,
        "peacock_strict": all(r["strict_match"] for r in results) if check_peacock and results else strict_match,
        "peacock_lenient": peacock_ok if not strict else None,
        "peacock_strict_synthetic": strict_match,
        "peacock_hash_len_parity": all(r["strict_match"] for r in results) if check_peacock and results else False,
        "total_instructions": sum(r["instructions"] for r in results),
        "results": results,
    }
    # Keep backward-compat
    summary["peacock_lenient"] = peacock_ok
    summary["peacock_strict"] = summary["peacock_strict"] if isinstance(summary["peacock_strict"], bool) else strict_match
    return summary

def main(argv=None):
    ap = argparse.ArgumentParser(description="PEACOCK Phase C bootstrap check")
    ap.add_argument("--write", action="store_true", help="write .बीज artifacts to build/bootstrap/")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-peacock", action="store_true", help="skip PEACOCK VM check")
    ap.add_argument("--lenient", action="store_true", help="use lenient (non-empty) instead of strict digest equality")
    args = ap.parse_args(argv)
    summary = bootstrap(check_peacock=not args.no_peacock, write=args.write, verbose=args.verbose, strict=not args.lenient)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    ok = summary["python_fixed_point"] and (summary.get("peacock_strict") or summary.get("peacock_lenient"))
    if not ok:
        print("Bootstrap failed — see strict mismatches above (pipeline.सूत्र must match Python tag-chain)", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
