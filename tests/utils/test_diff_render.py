# topmark:header:start
#
#   project      : TopMark
#   file         : test_diff_render.py
#   file_relpath : tests/utils/test_diff_render.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# File path: tests/utils/test_diff_render.py
"""Diff utils: rendering from text or sequences and empty inputs.

Covers `render_patch` inputs and output type guarantees.
"""

from __future__ import annotations

from topmark.utils.diff import render_patch


def test_render_patch_accepts_str_and_list() -> None:
    """`render_patch` should accept both a diff string and an iterable of lines."""
    diff_text = "--- a\n+++ b\n-foo\n+bar\n"
    s1 = render_patch(diff_text)
    s2 = render_patch(diff_text.splitlines(False))

    # Both should render to non-empty strings.
    assert isinstance(s1, str) and isinstance(s2, str) and s1 and s2


def test_render_patch_empty_input_is_safe() -> None:
    """Empty diff input should not raise and should return a string."""
    s = render_patch("")
    assert isinstance(s, str)
