# topmark:header:start
#
#   project      : TopMark
#   file         : test_anchor_helper.py
#   file_relpath : tests/pipeline/processors/test_anchor_helper.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the compute_insertion_anchor helper (line-based facade)."""

from __future__ import annotations

from topmark.pipeline.processors.base import NO_LINE_ANCHOR, HeaderProcessor


class _FakeLine(HeaderProcessor):
    """Stub that returns a fixed line index from get_header_insertion_index."""

    def get_header_insertion_index(self, file_lines: list[str]) -> int:
        return 3


class _FakeNoLine(HeaderProcessor):
    """Stub that signals char-offset insertion via NO_LINE_ANCHOR."""

    def get_header_insertion_index(self, file_lines: list[str]) -> int:
        return NO_LINE_ANCHOR


def test_compute_insertion_anchor_delegates_default() -> None:
    """Delegates to get_header_insertion_index (line index)."""
    p = _FakeLine()
    assert p.compute_insertion_anchor(["a", "b"]) == 3


def test_compute_insertion_anchor_propagates_no_line_anchor() -> None:
    """Propagates NO_LINE_ANCHOR for char-offset processors."""
    p = _FakeNoLine()
    assert p.compute_insertion_anchor(["a"]) == NO_LINE_ANCHOR
