# topmark:header:start
#
#   project      : TopMark
#   file         : cblock.py
#   file_relpath : src/topmark/pipeline/processors/cblock.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header processor for C-like block comments: /* ... */ with per-line *.

This is ideal for CSS and friends (SCSS, Less, Stylus), and works for any
format that accepts C-style block comments (SQL, Solidity, etc.).

Layout example:

/*
 * topmark:start
 *
 *   project : TopMark
 *   file    : styles.css
 *   ...
 *
 * topmark:end
 */

We emit the wrapper lines '/*' and '*/' and render inner lines as '* ...'.
"""

from __future__ import annotations

from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.processors.mixins import BlockCommentMixin


# Attach all relevant file types here; their concrete definitions live in filetypes/instances.py
@register_filetype("css")
@register_filetype("less")
@register_filetype("scss")
@register_filetype("solidity")
@register_filetype("sql")
@register_filetype("stylus")
class CBlockHeaderProcessor(BlockCommentMixin, HeaderProcessor):
    """Processor for C-style block comment headers (uses BlockCommentMixin)."""

    # We want:
    #   block wrapper:   /*  ...  */
    #   inner lines:     * <content>
    #
    # By using line_prefix="*" and line_indent="" we get "* content".
    block_prefix = "/*"
    block_suffix = "*/"
    line_prefix = "*"
    line_suffix = ""
    line_indent = "  "  # produce "* topmark:start" (single space comes from wrapper)

    def __init__(self) -> None:
        # Defer to base initializer; class attributes define affixes/indent.
        super().__init__()

    # Broaden matching so we also recognize headers whose inner lines were written
    # WITHOUT the leading "*" (older tools / formatters sometimes do that).
    def line_has_directive(self, line: str, directive: str) -> bool:
        """Check whether a line contains the directive with the expected affixes.

        This method is used by ``get_header_bounds()`` to locate header start/end markers.
        Subclasses may override this method for more flexible or format-specific matching.

        Args:
            line: The line of text to check (whitespace is trimmed internally).
            directive: The directive string to look for.

        Returns:
            ``True`` if the line contains the directive with the configured prefix/suffix,
            otherwise ``False``.
        """
        s: str = line.strip()
        # Case 1: "* <directive>"
        if s.startswith(self.line_prefix):
            candidate: str = s[len(self.line_prefix) :].strip()
            if candidate == directive:
                return True
        # Case 2: "<directive>" (no per-line prefix)
        return s == directive

    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        """Ensure sensible padding around the header.

        - At top-of-file: no leading blank; ensure >=1 trailing blank unless next line is blank/EOF.
        - After preceding content: ensure exactly one leading blank; ensure >=1 trailing blank.

        Args:
            original_lines: The original file lines.
            insert_index: Line index at which the header will be inserted.
            rendered_header_lines: The header lines to insert.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            Possibly modified header lines to insert at ``insert_index``.
        """
        out: list[str] = list(rendered_header_lines)

        # Leading padding
        if insert_index > 0:
            prev_is_blank: bool = (
                insert_index - 1 < len(original_lines)
                and original_lines[insert_index - 1].strip() == ""
            )
            if not prev_is_blank:
                out = [newline_style] + out

        # Trailing padding
        next_is_blank: bool = (
            insert_index < len(original_lines) and original_lines[insert_index].strip() == ""
        )
        if not next_is_blank:
            out = out + [newline_style]

        return out
