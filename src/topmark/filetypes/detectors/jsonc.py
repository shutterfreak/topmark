# topmark:header:start
#
#   project      : TopMark
#   file         : jsonc.py
#   file_relpath : src/topmark/filetypes/detectors/jsonc.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Detectors for JSON-with-comments (JSONC/CJSON)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def looks_like_jsonc(path: Path) -> bool:
    r"""Heuristic content matcher for JSON-with-comments (JSONC/CJSON).

    The detector avoids false positives from URLs or tokens embedded inside
    JSON strings by using a tiny state machine over a limited prefix.

    Strategy (fast, best-effort):
    - Read up to ~128 KiB, UTF-8 with surrogate escapes ignored.
    - Track states: in_string (JSON double-quoted), in_line_comment, in_block_comment.
    - Properly handle string escapes (e.g. ``\"``), including backslash runs.
    - Report True upon encountering ``//`` or ``/* ... */`` while **not** in a string
      and **not** in an existing block comment.
    """
    try:
        text: str = path.read_text(encoding="utf-8", errors="ignore")[:131072]
    except OSError:
        return False

    # Quick structural sanity: likely JSON if it contains braces/brackets.
    if not any(c in text for c in ("{", "[")):
        return False

    in_string = False
    in_line_comment = False
    in_block_comment = False
    i: int = 0
    n: int = len(text)

    while i < n:
        ch: str = text[i]

        # Handle end of line comments
        if in_line_comment:
            if ch == "\n" or ch == "\r":
                in_line_comment = False
            i += 1
            continue

        # Handle block comments
        if in_block_comment:
            if ch == "*" and i + 1 < n and text[i + 1] == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        # Not currently in any comment
        if in_string:
            # Inside a JSON string (double quotes only).
            if ch == "\\":
                # Skip a backslash-escaped code point (handles sequences like \\\" correctly)
                i += 2
                continue
            if ch == '"':
                # Count preceding backslashes to determine if escaped.
                bs = 0
                j: int = i - 1
                while j >= 0 and text[j] == "\\":
                    bs += 1
                    j -= 1
                if (bs % 2) == 0:
                    in_string = False
            i += 1
            continue

        # Not in string/any comment: check for comment starts first.
        if ch == "/" and i + 1 < n:
            nxt: str = text[i + 1]
            if nxt == "/":
                # Found a line comment outside strings ⇒ JSONC
                return True
            if nxt == "*":
                # Enter block comment outside strings ⇒ JSONC
                in_block_comment = True
                i += 2
                continue

        # Enter string?
        if ch == '"':
            in_string = True
            i += 1
            continue

        i += 1

    return False
