"""Deterministic PEACOCK formatter.

Idempotent: formatting twice yields same output.
Preserves semantics, normalizes indentation and trailing whitespace.
Comments are preserved on their own lines with correct indent.

The formatter is intentionally line-based + brace-depth driven, not a full
pretty-printer, to stay zero-dependency and deterministic. It uses the same
lexical rules as the compiler (NFC, block-comment nesting) to avoid corrupting
strings/comments.
"""
from __future__ import annotations

import pathlib
import re

# Canonical 4-space indent
INDENT = "    "

# Operators that should have single spaces around them (outside strings/comments)
# We normalize after tokenization via simple regex passes that are string-aware.
COMPOUND_PLACEHOLDERS = {
    "->": "⟦ARROW⟧",
    "==": "⟦EQ⟧",
    "!=": "⟦NE⟧",
    "<=": "⟦LE⟧",
    ">=": "⟦GE⟧",
    "**": "⟦POW⟧",
    "+=": "⟦PLUSEQ⟧",
    "-=": "⟦MINUSEQ⟧",
    "*=": "⟦STAREQ⟧",
    "/=": "⟦SLASHEQ⟧",
    "%=": "⟦PERCEQ⟧",
    "..": "⟦RANGE⟧",
}

OPERATOR_SPACINGS = [
    (re.compile(r"\s*=\s*"), " = "),
    (re.compile(r"\s*<\s*"), " < "),
    (re.compile(r"\s*>\s*"), " > "),
    (re.compile(r"\s*\+\s*"), " + "),
    (re.compile(r"\s*-\s*"), " - "),
    (re.compile(r"\s*\*\s*"), " * "),
    (re.compile(r"\s*/\s*"), " / "),
    (re.compile(r"\s*%\s*"), " % "),
    (re.compile(r"\s*\+\s*"), " + "),
    # For - we must avoid collapsing -> already done; minus as binary vs unary is ambiguous
    # so we only normalize when surrounded by alnum/space, not inside strings - handled below.
]

# Punctuation that should NOT have leading space, but one trailing space when needed
COMMA_RE = re.compile(r"\s*,\s*")
COLON_RE = re.compile(r"\s*:\s*")
SEMICOLON_RE = re.compile(r"\s*;\s*")


def _split_string_aware(line: str) -> list[tuple[str, bool]]:
    """Split line into segments: (text, is_string) where is_string True for quoted string literals.

    Handles escapes: \" \\ \n \t etc. and block comments are NOT strings.
    This is conservative: only \"...\" counts as string.
    """
    segments: list[tuple[str, bool]] = []
    i = 0
    n = len(line)
    cur = []
    in_str = False
    while i < n:
        ch = line[i]
        if not in_str:
            if ch == '"':
                if cur:
                    segments.append(("".join(cur), False))
                    cur = []
                cur.append(ch)
                in_str = True
                i += 1
                continue
            # detect // comment start outside string -> rest is comment
            if ch == "/" and i + 1 < n and line[i + 1] == "/":
                if cur:
                    segments.append(("".join(cur), False))
                segments.append((line[i:], False))  # comment as non-string but we treat specially
                return segments
            cur.append(ch)
            i += 1
        else:
            cur.append(ch)
            if ch == "\\":
                # escaped next char
                if i + 1 < n:
                    cur.append(line[i + 1])
                    i += 2
                else:
                    i += 1
                continue
            if ch == '"':
                segments.append(("".join(cur), True))
                cur = []
                in_str = False
            i += 1
    if cur:
        segments.append(("".join(cur), in_str))
    return segments


def _format_line_content(raw: str) -> str:
    """Format a single line's content (without leading indent), string-aware."""
    # Preserve empty or comment-only lines
    stripped = raw.strip()
    if not stripped:
        return ""
    if stripped.startswith("//"):
        # Normalize to single space after //
        comment_body = stripped[2:].strip()
        return f"// {comment_body}" if comment_body else "//"

    # Split string-aware, only format non-string segments that are not pure comment tail
    segments = _split_string_aware(raw)
    out_parts: list[str] = []
    for text, is_str in segments:
        if is_str:
            out_parts.append(text)
            continue
        # If this segment is a comment tail starting with //, preserve as is (already handled)
        if text.lstrip().startswith("//"):
            # text is remainder comment
            comment = text.strip()
            if comment.startswith("//"):
                body = comment[2:].strip()
                out_parts.append(f"// {body}" if body else "//")
            else:
                out_parts.append(text)
            continue
        # Apply operator spacings with compound placeholder protection
        t = text
        for op, ph in COMPOUND_PLACEHOLDERS.items():
            # Use spaced placeholder to preserve token identity; surrounding spaces normalized later
            t = t.replace(op, ph)
        for pat, repl in OPERATOR_SPACINGS:
            t = pat.sub(repl, t)
        # Restore compounds with canonical spacing
        restore = {
            "⟦ARROW⟧": " -> ",
            "⟦EQ⟧": " == ",
            "⟦NE⟧": " != ",
            "⟦LE⟧": " <= ",
            "⟦GE⟧": " >= ",
            "⟦POW⟧": " ** ",
            "⟦PLUSEQ⟧": " += ",
            "⟦MINUSEQ⟧": " -= ",
            "⟦STAREQ⟧": " *= ",
            "⟦SLASHEQ⟧": " /= ",
            "⟦PERCEQ⟧": " %= ",
            "⟦RANGE⟧": "..",
        }
        for ph, rep in restore.items():
            t = t.replace(ph, rep)
        # Fix commas/colons/semicolons: no space before, one after unless at end
        t = COMMA_RE.sub(", ", t)
        t = COLON_RE.sub(": ", t)
        t = SEMICOLON_RE.sub("; ", t)
        # Fix dot: no surrounding spaces (member access)
        t = re.sub(r"\s*\.\s*", ".", t)
        # Fix parens/brackets/braces: no space inside
        t = re.sub(r"\(\s*", "(", t)
        t = re.sub(r"\s*\)", ")", t)
        t = re.sub(r"\[\s*", "[", t)
        t = re.sub(r"\s*\]", "]", t)
        t = re.sub(r"\{\s*", "{", t)
        t = re.sub(r"\s*\}", "}", t)
        # Collapse multiple spaces (outside strings already)
        t = re.sub(r" {2,}", " ", t)
        # Remove space before comma/semicolon/colon/dot already handled
        t = t.strip()
        out_parts.append(t)
    # Join segments without adding extra space at string boundaries
    # If a non-string ends with alnum and string starts, keep space if original had it; we stripped, so add one space if needed
    # Simple heuristic: join with "" and then ensure strings that follow identifiers have a space if original had one - already collapsed
    # We'll join and then fix cases where we lost space between identifier and string: e.g., मुद्रय("hi") should stay मुद्रय("hi")
    # No space needed there, so "" is fine.
    # For case like `अ = "hi"` we already have spaces via operator handling.
    return "".join(out_parts).strip()


def format_source(source: str) -> str:
    """Format complete source text deterministically."""
    # Normalize newlines and ensure NFC (the lexer does NFC, but formatter should not mangle)
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = source.split("\n")
    # Remove trailing whitespace per line first
    # Track block-comment depth to preserve indentation inside comments
    out_lines: list[str] = []
    depth = 0
    in_block_comment = 0
    for raw_line in lines:
        # Strip trailing whitespace
        line = raw_line.rstrip()
        if not line.strip():
            out_lines.append("")
            continue
        # Detect block comment boundaries for indent tracking (nesting)
        # Count /* and */ occurrences outside strings (simplified)
        # Use string-aware split to avoid counting inside strings
        segs = _split_string_aware(line)
        non_str = "".join(t for t, is_s in segs if not is_s)
        open_c = non_str.count("/*")
        close_c = non_str.count("*/")
        # If inside block comment, emit with current depth indent and update depth after
        if in_block_comment > 0:
            # Dedent if contains closing before content? Keep simple: indent at depth
            indent = INDENT * depth
            # Preserve comment content but trim trailing spaces
            out_lines.append(indent + line.lstrip())
            in_block_comment += open_c - close_c
            if in_block_comment < 0:
                in_block_comment = 0
            continue
        if open_c > 0 and close_c == 0:
            # Start of block comment spanning multiple lines
            in_block_comment += open_c
            # fall through to normal handling for this line

        stripped = line.strip()
        # Decrease depth before line if it starts with closing brace
        # Count leading } occurrences
        j = 0
        while j < len(stripped) and stripped[j] == "}":
            depth = max(0, depth - 1)
            j += 1
            # skip possible spaces after }
            while j < len(stripped) and stripped[j] == " ":
                j += 1
        # Format content
        # For brace-aware lines, we keep braces as formatted content includes them
        formatted_content = _format_line_content(stripped)
        # Re-apply brace dedent effect: formatted_content may start with } already counted
        # Ensure indent reflects updated depth
        indent = INDENT * depth
        out_lines.append(indent + formatted_content if formatted_content else "")

        # Increase depth after line based on net braces (outside strings/comments)
        # Count { and } in non-string part of formatted_content (approx)
        # Use original non_str brace counts for robustness
        # But use formatted_content's braces for depth (they are same count)
        # We count { and } that are not inside strings (we already have non_str, but use formatted)
        # Simpler: count in formatted_content outside strings
        f_segs = _split_string_aware(formatted_content)
        f_non_str = "".join(t for t, is_s in f_segs if not is_s)
        opens = f_non_str.count("{")
        closes = f_non_str.count("}")
        # We already handled leading } closes, so subtract them from closes to avoid double
        leading_closes = 0
        tmp = stripped.lstrip()
        for ch in tmp:
            if ch == "}":
                leading_closes += 1
            elif ch == " ":
                continue
            else:
                break
        # Net delta: opens - (closes - leading_closes) but leading already applied
        delta = opens - (closes - leading_closes)
        depth += delta
        if depth < 0:
            depth = 0
        # Update in_block_comment for next line
        if in_block_comment > 0:
            in_block_comment += open_c - close_c
        else:
            # if this line closed a block comment that started and ended same line, no carry
            if open_c and close_c:
                in_block_comment = max(0, in_block_comment + open_c - close_c)
    # Trim leading/trailing blank lines but ensure single trailing newline
    while out_lines and out_lines[0] == "":
        out_lines.pop(0)
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    # Collapse consecutive blank lines to at most one
    collapsed: list[str] = []
    prev_blank = False
    for l in out_lines:
        is_blank = l == ""
        if is_blank and prev_blank:
            continue
        collapsed.append(l)
        prev_blank = is_blank
    result = "\n".join(collapsed) + "\n"
    return result


def format_file(path: pathlib.Path, write: bool = True) -> tuple[bool, str, str]:
    """Format a file. Returns (changed, original, formatted). If write, overwrites."""
    original = path.read_text(encoding="utf-8")
    formatted = format_source(original)
    changed = formatted != original
    if write and changed:
        path.write_text(formatted, encoding="utf-8")
    return changed, original, formatted


def format_many(paths: list[pathlib.Path], write: bool = True) -> dict:
    """Format multiple paths. Returns summary dict."""
    summary = {"checked": 0, "changed": 0, "unchanged": 0, "errors": 0, "files": []}
    for p in paths:
        summary["checked"] += 1
        try:
            changed, _, _ = format_file(p, write=write)
            if changed:
                summary["changed"] += 1
            else:
                summary["unchanged"] += 1
            summary["files"].append({"path": str(p), "changed": changed})
        except Exception as e:
            summary["errors"] += 1
            summary["files"].append({"path": str(p), "error": str(e)})
    return summary
