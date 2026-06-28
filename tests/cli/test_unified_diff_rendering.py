# topmark:header:start
#
#   project      : TopMark
#   file         : test_unified_diff_rendering.py
#   file_relpath : tests/cli/test_unified_diff_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Unit tests for CLI unified diff rendering helpers.

These tests focus on the structure-aware formatter used by TEXT presentation:
header-slot handling, hunk-body classification, escaped control characters, and
line-number gutters. They intentionally avoid asserting exact Rich styles beyond
checking that styled output remains ANSI-enabled where requested.
"""

from __future__ import annotations

from topmark.cli.rendering.unified_diff import format_patch_styled


def test_format_patch_styled_accepts_sequence_and_renders_plain_diff() -> None:
    """Sequence input should be normalized and rendered without styling."""
    rendered: str = format_patch_styled(
        patch=[
            "--- old.py",
            "+++ new.py",
            "@@ -1 +1 @@",
            "-old",
            "+new",
            " context",
        ],
        styled=False,
    )

    assert rendered == "--- old.py\n+++ new.py\n@@ -1 +1 @@\n-old\n+new\n context\n"


def test_format_patch_styled_escapes_control_characters_in_sequence_input() -> None:
    """Rendered previews should make embedded CR/LF characters explicit."""
    rendered: str = format_patch_styled(
        patch=[
            "--- old.py\r\n",
            "+++ new.py\n",
            "@@ -1 +1 @@",
            "-old\r",
            "+new\n",
        ],
        styled=False,
    )

    assert "--- old.py\\r\\n" in rendered
    assert "+++ new.py\\n" in rendered
    assert "-old\\r" in rendered
    assert "+new\\n" in rendered
    assert "\r" not in rendered


def test_format_patch_styled_renders_no_newline_marker_as_metadata() -> None:
    """No-newline markers should be emitted as diff metadata lines."""
    rendered: str = format_patch_styled(
        patch="--- old.py\n+++ new.py\n@@ -1 +1 @@\n-old\n+new\n\\ No newline at end of file",
        styled=False,
    )

    assert rendered.endswith("\\ No newline at end of file\n")


def test_format_patch_styled_does_not_classify_plus_minus_outside_hunks() -> None:
    """Leading plus/minus content outside hunks should remain literal text."""
    rendered: str = format_patch_styled(
        patch=[
            "--- old.py",
            "+++ new.py",
            "+not an addition outside a hunk",
            "-not a deletion outside a hunk",
            "---> not an old-file header",
        ],
        styled=False,
    )

    assert "+not an addition outside a hunk" in rendered
    assert "-not a deletion outside a hunk" in rendered
    assert "---> not an old-file header" in rendered


def test_format_patch_styled_line_numbers_are_plain_when_styling_is_disabled() -> None:
    """Plain line-number gutters should be deterministic."""
    rendered: str = format_patch_styled(
        patch=["--- old.py", "+++ new.py"],
        styled=False,
        show_line_numbers=True,
    )

    assert rendered == "0001|--- old.py\n0002|+++ new.py\n"


def test_format_patch_styled_line_numbers_are_styled_when_requested() -> None:
    """Styled line-number gutters should keep text content while emitting ANSI."""
    rendered: str = format_patch_styled(
        patch=["--- old.py", "+++ new.py", "@@ -1 +1 @@", "-old", "+new"],
        styled=True,
        show_line_numbers=True,
    )

    assert "0001|" in rendered
    assert "--- old.py" in rendered
    assert "0005|" in rendered
    assert "+new" in rendered
    assert "\x1b[" in rendered
