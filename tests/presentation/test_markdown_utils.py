# topmark:header:start
#
#   project      : TopMark
#   file         : test_markdown_utils.py
#   file_relpath : tests/presentation/test_markdown_utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Focused tests for low-level Markdown presentation helpers."""

from __future__ import annotations

import pytest

from topmark.presentation.markdown.utils import markdown_code_span
from topmark.presentation.markdown.utils import markdown_escape
from topmark.presentation.markdown.utils import render_markdown_table
from topmark.presentation.markdown.utils import render_toml_markdown


def test_markdown_code_span_grows_past_embedded_backticks() -> None:
    """Inline code spans should survive filenames containing backticks."""
    assert markdown_code_span("name`with``ticks") == "```name`with``ticks```"


def test_markdown_escape_pads_edge_backticks() -> None:
    """Legacy escape helper should pad text that starts or ends with a backtick."""
    assert markdown_escape("`edge`") == "`` `edge` ``"


def test_render_markdown_table_handles_empty_headers() -> None:
    """An empty table shape should render as an empty fragment."""
    assert render_markdown_table([], []) == ""


def test_render_markdown_table_rejects_inconsistent_rows() -> None:
    """Tables should fail loudly when row width differs from header width."""
    with pytest.raises(ValueError, match="same number of columns"):
        render_markdown_table(["A", "B"], [["only one cell"]])


def test_render_markdown_table_supports_right_and_center_alignment() -> None:
    """Markdown tables should render explicit right and center alignment markers."""
    output: str = render_markdown_table(
        ["Name", "Count", "Mode"],
        [["alpha", "2", "wide"]],
        align={1: "right", 2: "center"},
    )

    assert "| Name  | Count | Mode |" in output
    assert "| ----- | ----: | :--: |" in output
    assert "| alpha | 2     | wide |" in output


def test_render_toml_markdown_normalizes_heading_bounds_and_fence() -> None:
    """TOML Markdown rendering should clamp headings and avoid nested fences."""
    output: str = render_toml_markdown(
        heading="Config",
        heading_level=9,
        toml_text='key = "value"\n# ``` nested fence',
    )

    assert output.startswith("###### Config\n")
    assert "````toml" in output
    assert output.rstrip().endswith("````")


def test_render_toml_markdown_allows_no_heading() -> None:
    """TOML Markdown rendering should support code-block-only output."""
    output: str = render_toml_markdown(
        heading=None,
        toml_text="key = true\n",
    )

    assert output == "```toml\nkey = true\n```\n"
