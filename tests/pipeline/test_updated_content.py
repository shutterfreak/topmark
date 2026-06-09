# topmark:header:start
#
#   project      : TopMark
#   file         : test_updated_content.py
#   file_relpath : tests/pipeline/test_updated_content.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Regression tests for repeatable updated-content views."""

from __future__ import annotations

from topmark.pipeline.views import UpdatedContent
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import compose_updated_content


def test_segment_updated_content_is_repeatable() -> None:
    """Segment-backed updated content can be consumed more than once."""
    content: UpdatedContent = compose_updated_content(
        ["prefix\n"],
        ["header\n"],
        ["body\n"],
    )

    assert list(content.iter_lines()) == ["prefix\n", "header\n", "body\n"]
    assert list(content.iter_lines()) == ["prefix\n", "header\n", "body\n"]


def test_updated_view_releases_segment_content() -> None:
    """UpdatedView release clears the composed content reference."""
    view = UpdatedView(lines=compose_updated_content(["a\n"], ["b\n"]))

    view.release()

    assert view.lines is None
