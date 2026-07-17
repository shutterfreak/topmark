# topmark:header:start
#
#   project      : TopMark
#   file         : test_markdown.py
#   file_relpath : tests/processors/test_markdown.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the MarkdownHeaderProcessor (HTML-style ``<!-- ... -->`` comments).

Exercises placement rules for Markdown (HTML comments).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import expected_block_lines_for
from tests.helpers.pipeline import find_line
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_insert
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.processors.builtins.markdown import MarkdownHeaderProcessor
from topmark.processors.types import BoundsKind

if TYPE_CHECKING:
    from pathlib import Path

    from tests.helpers.pipeline import BlockSignatures
    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.processors.types import HeaderBounds


def test_markdown_fenced_code_no_insertion_inside(tmp_path: Path) -> None:
    """Do not insert inside Markdown fenced code blocks.

    The header must be placed at the top of the document and the original fenced
    code block must remain intact.
    """
    f: Path = tmp_path / "FENCE.md"
    f.write_text(f"```html\n<!-- {TOPMARK_START_MARKER} -->\n```\nReal content\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    # Header should be at top (before the fenced block) and not inside it
    sig: BlockSignatures = expected_block_lines_for(f)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    assert f"<!-- {TOPMARK_START_MARKER} -->" in "".join(lines), (
        "Original fence content must remain untouched"
    )


def test_markdown_top_of_file_with_trailing_blank(tmp_path: Path) -> None:
    """Markdown supports HTML comments; insert at top with trailing blank.

    Confirms the HTML-comment-based header is added at the top (block-open at 0,
    start-line at 1) and that a blank line follows the block.
    """
    f: Path = tmp_path / "README.md"
    f.write_text("# Title\n\nSome text.\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(f)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines)
        assert lines[close_idx + 1].strip() == ""


def test_markdown_with_existing_banner_comment(tmp_path: Path) -> None:
    """Markdown: header precedes any existing banner comment.

    Confirms block placement and ordering of the prior banner comment after the
    TopMark header.
    """
    f: Path = tmp_path / "BANNER.md"
    f.write_text("<!-- md:banner -->\n# Title\n\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(f)

    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1

    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        banner_idx: int = find_line(lines, "<!-- md:banner -->")
        assert banner_idx > close_idx


def test_markdown_bounds_materialize_generator_once_and_preserve_indexes() -> None:
    """Fenced example markers are masked while real header indexes stay stable."""
    processor = MarkdownHeaderProcessor()
    fenced_example: list[str] = [
        "```text\n",
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "```\n",
    ]
    real_header: list[str] = [
        "<!--\n",
        f"{TOPMARK_START_MARKER}\n",
        f"{TOPMARK_END_MARKER}\n",
        "-->\n",
    ]
    original: list[str] = fenced_example + real_header
    original_copy: list[str] = list(original)

    bounds: HeaderBounds = processor.get_header_bounds(
        lines=(line for line in original),
        newline_style="\n",
    )

    assert bounds.kind is BoundsKind.NONE
    assert original == original_copy

    reordered: list[str] = real_header + fenced_example
    bounds = processor.get_header_bounds(
        lines=(line for line in reordered),
        newline_style="\n",
    )
    assert (bounds.kind, bounds.start, bounds.end) == (BoundsKind.SPAN, 0, 4)


def test_markdown_empty_input_has_no_bounds() -> None:
    """An empty Markdown input has no header bounds."""
    bounds: HeaderBounds = MarkdownHeaderProcessor().get_header_bounds(
        lines=iter(()), newline_style="\n"
    )

    assert bounds.kind is BoundsKind.NONE


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_markdown_unclosed_fence_hides_all_following_markers(
    fence: str,
) -> None:
    """An unclosed supported fence does not expose example markers as headers."""
    processor = MarkdownHeaderProcessor()
    lines: list[str] = [
        f"{fence}text\n",
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
    ]

    bounds: HeaderBounds = processor.get_header_bounds(lines=lines, newline_style="\n")

    assert bounds.kind is BoundsKind.NONE


@pytest.mark.parametrize(
    ("original_lines", "expected"),
    [
        (["# Heading\n"], ["header\n", "\n"]),
        (["\n", "# Heading\n"], ["header\n"]),
        ([], ["header\n"]),
    ],
)
def test_markdown_insertion_padding_is_owned_and_non_mutating(
    original_lines: list[str],
    expected: list[str],
) -> None:
    """Markdown adds only the required separator before body content."""
    processor = MarkdownHeaderProcessor()
    rendered: list[str] = ["header\n"]
    original_copy: list[str] = list(original_lines)

    prepared: list[str] = processor.prepare_header_for_insertion(
        original_lines=original_lines,
        insert_index=0,
        rendered_header_lines=rendered,
        newline_style="\n",
    )

    assert prepared == expected
    assert original_lines == original_copy
    assert rendered == ["header\n"]
