# topmark:header:start
#
#   project      : TopMark
#   file         : test_multiple_headers.py
#   file_relpath : tests/pipeline/processors/test_multiple_headers.py
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
from typing import TYPE_CHECKING

from tests.pipeline.conftest import materialize_updated_lines, run_insert
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.processors import get_processor_for_file
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor


def _count_markers(text: str) -> int:
    return text.count(TOPMARK_START_MARKER)


def test_multiple_headers_insert_replaces_first_only_pound(tmp_path: Path) -> None:
    """Two headers: default command replaces only the first (Pound processor)."""
    f: Path = tmp_path / "dup.py"
    header_1: str = "test:header 1"
    header_2: str = "test:header 2"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n# {header_1}\n# {TOPMARK_END_MARKER}\n"
        "print('body')\n"
        f"# {TOPMARK_START_MARKER}\n# {header_2}\n# {TOPMARK_END_MARKER}\n",
        encoding="utf-8",
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    out: str = "".join(lines)

    # Still two headers remain, but the first was replaced to the expected format.
    assert _count_markers(out) == 2
    # Sanity: the second legacy payload survives.
    assert header_2 in out


def test_multiple_headers_strip_removes_first_only_xml(tmp_path: Path) -> None:
    """Two XML/HTML-comment headers: strip removes only the first."""
    f: Path = tmp_path / "dup.html"
    header1: str = "<!-- x -->\n"
    header2: str = "<!-- y -->\n"
    f.write_text(
        f"<!-- {TOPMARK_START_MARKER} -->\n{header1}<!-- {TOPMARK_END_MARKER} -->\n"
        "<p>body</p>\n"
        f"<!-- {TOPMARK_START_MARKER} -->\n{header2}<!-- {TOPMARK_END_MARKER} -->\n",
        encoding="utf-8",
    )

    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None

    lines: list[str] = f.read_text(encoding="utf-8").splitlines(keepends=True)
    new: list[str] = []
    span: tuple[int, int] | None = None
    diag: StripDiagnostic
    new, span, diag = proc.strip_header_block(lines=lines, span=None)

    assert diag.kind == StripDiagKind.REMOVED
    assert span is not None, "First header must be detected and removed"

    out: str = "".join(new)

    assert _count_markers(out) == 1, "Only the first header should be removed"
    assert header1 not in out, "First header content must be stripped"
    assert header2 in out, "Second header content must remain"
