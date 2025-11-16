# topmark:header:start
#
#   project      : TopMark
#   file         : markdown.py
#   file_relpath : src/topmark/pipeline/processors/markdown.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Processor for files with HTML/XML-style block comments (<!-- ... -->).

This processor treats Markdown as a **line-based** format that happens to support
HTML comment blocks (`<!-- ... -->`) for the TopMark header. It does **not**
use XML positional logic or prolog/doctype handling; headers are inserted at
the top of the document (line-based strategy).

Markdown-specific behavior:
    * Uses HTML block comments (`<!-- ... -->`) as the header block wrapper.
    * Inserts the TopMark header at the logical top of the file (index 0) so it
      precedes any existing banner comments or headings.
    * Ignores TopMark markers that appear inside fenced code blocks (``` / ~~~),
      even if they look like partial or malformed headers. This keeps README
      examples from being treated as real headers and allows Builder/Planner to
      insert a header at the top when appropriate.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.processors.mixins import BlockCommentMixin
from topmark.pipeline.processors.types import BoundsKind, HeaderBounds

if TYPE_CHECKING:
    from collections.abc import Iterable
    from re import Pattern

    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


@register_filetype("markdown")
class MarkdownHeaderProcessor(BlockCommentMixin, HeaderProcessor):
    """Header processor for Markdown formats (HTML comment–based, line-oriented).

    This processor uses `<!-- ... -->` block comments for the TopMark header and
    relies on the **line-based** placement strategy from `HeaderProcessor`. It
    adds Markdown-specific safeguards to ignore header-like markers that appear
    inside fenced code blocks (``` or ~~~).
    """

    def __init__(self) -> None:
        # Use HTML-style block comment delimiters for the header block.
        super().__init__(
            block_prefix="<!--",
            block_suffix="-->",
        )

    # --- Markdown-specific fence handling ---------------------------------

    def _compute_fence_mask(self, lines: Iterable[str]) -> list[bool]:
        """Return a boolean mask marking lines inside fenced code blocks.

        A simple fence detector that toggles state on lines starting with
        ``` or ~~~ (after optional leading whitespace). This is intentionally
        minimal but sufficient for avoiding TopMark markers in fenced blocks.
        """
        fence_re: Pattern[str] = re.compile(r"^\s*(```|~~~)")
        in_fence = False
        mask: list[bool] = []
        for ln in lines:
            if fence_re.match(ln):
                # The fence marker line itself is considered inside the fence
                in_fence: bool = not in_fence
                mask.append(True)
            else:
                mask.append(in_fence)
        return mask

    def get_header_bounds(
        self,
        *,
        lines: Iterable[str],
        newline_style: str,
    ) -> "HeaderBounds":
        """Detect the TopMark header in Markdown, ignoring fenced code blocks.

        This override delegates to the base header-bounds logic after hiding any
        TopMark markers that appear inside fenced code blocks (``` or ~~~). Markers
        in fenced regions are treated as plain text so README examples do not affect
        header detection.
        """
        # Materialize once to avoid exhausting generators multiple times.
        buf: list[str] = list(lines)
        if not buf:
            return HeaderBounds(kind=BoundsKind.NONE)

        # Compute fence mask on the concrete buffer.
        fence_mask: list[bool] = self._compute_fence_mask(buf)

        # Create a filtered copy where markers inside fences are removed so the
        # base get_header_bounds logic never sees them.
        filtered: list[str] = list(buf)
        for i, ln in enumerate(buf):
            if fence_mask[i]:
                filtered[i] = ln.replace(TOPMARK_START_MARKER, "").replace(TOPMARK_END_MARKER, "")

        # Delegate to the base logic using the filtered view. Indices in the
        # returned HeaderBounds still correspond to the original buffer because
        # we preserved length and line ordering.
        return super().get_header_bounds(lines=filtered, newline_style=newline_style)

    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        """Ensure a single blank line after the header block in Markdown.

        - Insert at top of file (index 0) with no leading blank.
        - If body content follows and the first body line is *not* blank,
          append exactly one blank line after the header block.
        """
        out: list[str] = list(rendered_header_lines)

        # If there is body content at the insert site, ensure a blank between
        # the header block and that content.
        if insert_index < len(original_lines):
            next_line: str = original_lines[insert_index]
            if next_line.strip() != "":
                # Add one blank line after the block
                out.append(newline_style)

        return out
