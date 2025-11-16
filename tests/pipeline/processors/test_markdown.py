# topmark:header:start
#
#   project      : TopMark
#   file         : test_markdown.py
#   file_relpath : tests/pipeline/processors/test_markdown.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the MarkdownHeaderProcessor (HTML-style ``<!-- ... -->`` comments).

Exercises placement rules for Markdown (HTML comments).
"""

from pathlib import Path
from typing import TYPE_CHECKING

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import (
    BlockSignatures,
    expected_block_lines_for,
    find_line,
    materialize_updated_lines,
    run_insert,
)
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from topmark.pipeline.context import ProcessingContext


@mark_pipeline
# @pytest.mark.skip(
#     reason=(
#         "TODO: add MarkDown-specific header insertion checker to check whether "
#         "the header is in a codefenced block"
#     )
# )
def test_markdown_fenced_code_no_insertion_inside(tmp_path: Path) -> None:
    """Do not insert inside Markdown fenced code blocks.

    The header must be placed at the top of the document and the original fenced
    code block must remain intact.
    """
    f: Path = tmp_path / "FENCE.md"
    f.write_text(f"```html\n<!-- {TOPMARK_START_MARKER} -->\n```\nReal content\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
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


@mark_pipeline
def test_markdown_top_of_file_with_trailing_blank(tmp_path: Path) -> None:
    """Markdown supports HTML comments; insert at top with trailing blank.

    Confirms the HTML-comment-based header is added at the top (block-open at 0,
    start-line at 1) and that a blank line follows the block.
    """
    f: Path = tmp_path / "README.md"
    f.write_text("# Title\n\nSome text.\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
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


@mark_pipeline
def test_markdown_with_existing_banner_comment(tmp_path: Path) -> None:
    """Markdown: header precedes any existing banner comment.

    Confirms block placement and ordering of the prior banner comment after the
    TopMark header.
    """
    f: Path = tmp_path / "BANNER.md"
    f.write_text("<!-- md:banner -->\n# Title\n\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
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
