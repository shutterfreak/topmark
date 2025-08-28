# topmark:header:start
#
#   file         : test_multiple_headers.py
#   file_relpath : tests/pipeline/processors/test_multiple_headers.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Behavior with multiple TopMark headers present in a file.

Covers:
- Default command replaces the **first** (top) header only; later header remains.
- `strip_header_block` removes the **first** header only; later header remains.

This reflects the policy-aware bounds (near insertion anchor) and guards against
touching header-like blocks far away in the body.
"""

from __future__ import annotations

from pathlib import Path

from tests.pipeline.conftest import run_insert
from topmark.config import Config
from topmark.pipeline.processors import get_processor_for_file


def _count_markers(text: str) -> int:
    return text.count("topmark:header:start")


def test_multiple_headers_insert_replaces_first_only_pound(tmp_path: Path) -> None:
    """Two headers: default command replaces only the first (Pound processor)."""
    f = tmp_path / "dup.py"
    f.write_text(
        "# topmark:header:start\n# x\n# topmark:header:end\n"
        "print('body')\n"
        "# topmark:header:start\n# y\n# topmark:header:end\n",
        encoding="utf-8",
    )

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)
    out = "".join(ctx.updated_file_lines or [])
    # Still two headers remain, but the first was replaced to the expected format.
    assert _count_markers(out) == 2
    # Sanity: the second legacy payload survives.
    assert "# y" in out


def test_multiple_headers_strip_removes_first_only_xml(tmp_path: Path) -> None:
    """Two XML/HTML-comment headers: strip removes only the first."""
    f = tmp_path / "dup.html"
    f.write_text(
        "<!-- topmark:header:start -->\n<!-- x -->\n<!-- topmark:header:end -->\n"
        "<p>body</p>\n"
        "<!-- topmark:header:start -->\n<!-- y -->\n<!-- topmark:header:end -->\n",
        encoding="utf-8",
    )

    proc = get_processor_for_file(f)
    assert proc is not None

    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
    new, span = proc.strip_header_block(lines=lines, span=None)
    assert span is not None, "First header must be detected and removed"
    out = "".join(new)
    assert _count_markers(out) == 1, "Only the first header should be removed"
    assert "<!-- y -->" in out, "Second header content must remain"
