# topmark:header:start
#
#   project      : TopMark
#   file         : test_bounds_inclusive.py
#   file_relpath : tests/pipeline/processors/test_bounds_inclusive.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for inclusive span semantics in header stripping.

This module verifies that `strip_header_block` treats the provided `(start, end)`
span as **inclusive** across all supported comment styles (Pound/Slash/XML).

The parameterized cases build a tiny file for each style, then pass a span
that explicitly covers the *start directive*, a *single payload line*, and the
*end directive*. The function must:

* return the same span `(0, 2)`, and
* remove the entire header block, leaving only the body content intact.

These tests are marked with `@pytest.mark.pipeline` to indicate they exercise
pipeline-level processor behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.processors import get_processor_for_file
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor

mark_pipeline: pytest.MarkDecorator = pytest.mark.pipeline


@pytest.mark.parametrize(
    "ext, header_open, header_line, header_close, body",
    [
        (
            ".py",
            f"# {TOPMARK_START_MARKER}\n",
            "# f\n",
            f"# {TOPMARK_END_MARKER}\n",
            "print('x')\n",
        ),
        (
            ".ts",
            f"// {TOPMARK_START_MARKER}\n",
            "// f\n",
            f"// {TOPMARK_END_MARKER}\n",
            "export {}\n",
        ),
        (
            ".html",
            f"<!-- {TOPMARK_START_MARKER} -->\n",
            "<!-- f -->\n",
            f"<!-- {TOPMARK_END_MARKER} -->\n",
            "<div/>\n",
        ),
    ],
)
@mark_pipeline
def test_strip_bounds_are_inclusive(
    tmp_path: Path, ext: str, header_open: str, header_line: str, header_close: str, body: str
) -> None:
    """`strip_header_block` must treat the span as *inclusive* (start..end).

    Builds a tiny file with a header block at the top and passes an explicit
    ``span`` covering the *directive lines and payload line*. The resulting
    file must contain only the body and the returned span must match exactly.

    Args:
        tmp_path: Temporary directory provided by pytest.
        ext: Extension that maps to the target processor.
        header_open: Start directive line including newline.
        header_line: A single payload line including newline.
        header_close: End directive line including newline.
        body: A single body line including newline.
    """
    f: Path = tmp_path / f"x{ext}"
    content: str = header_open + header_line + header_close + body
    f.write_text(content, encoding="utf-8")

    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None
    lines: list[str] = f.read_text(encoding="utf-8").splitlines(keepends=True)

    # span covers indices 0..2 (inclusive)
    new_lines: list[str] = []
    span: tuple[int, int] | None = None
    diag: StripDiagnostic
    new_lines, span, diag = proc.strip_header_block(lines=lines, span=(0, 2))
    assert diag.kind == StripDiagKind.REMOVED
    assert span == (0, 2)
    assert "".join(new_lines) == body
