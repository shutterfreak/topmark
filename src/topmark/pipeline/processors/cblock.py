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

from topmark.file_resolver import detect_newline
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import HeaderProcessor


# Attach all relevant file types here; their concrete definitions live in filetypes/instances.py
@register_filetype("css")
@register_filetype("less")
@register_filetype("scss")
@register_filetype("solidity")
@register_filetype("sql")
@register_filetype("stylus")
class CBlockHeaderProcessor(HeaderProcessor):
    """Processor for C-style block comment headers."""

    def __init__(self) -> None:
        # We want:
        #   block wrapper:   /*  ...  */
        #   inner lines:     * <content>
        #
        # By using line_prefix="*" and line_indent="" we get "* content".
        super().__init__(
            block_prefix="/*",
            block_suffix="*/",
            line_prefix="*",
            line_suffix="",
            line_indent="  ",  # produce "* topmark:start" (single space comes from wrapper)
        )

    # Broaden matching so we also recognize headers whose inner lines were written
    # WITHOUT the leading "*" (older tools / formatters sometimes do that).
    def line_has_directive(self, line: str, directive: str) -> bool:
        """Check whether a line contains the directive with the expected affixes.

        This method is used by ``get_header_bounds()`` to locate header start/end markers.
        Subclasses may override this method for more flexible or format-specific matching.

        Args:
            line (str): The line of text to check (whitespace is trimmed internally).
            directive (str): The directive string to look for.

        Returns:
            bool: ``True`` if the line contains the directive with the configured
                prefix/suffix, otherwise ``False``.
        """
        s: str = line.strip()
        # Case 1: "* <directive>"
        if s.startswith(self.line_prefix):
            candidate: str = s[len(self.line_prefix) :].strip()
            if candidate == directive:
                return True
        # Case 2: "<directive>" (no per-line prefix)
        if s == directive:
            return True
        return False

    def prepare_header_for_insertion(
        self,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
    ) -> list[str]:
        """Ensure sensible padding around the header.

        - At top-of-file: no leading blank; ensure >=1 trailing blank unless next line is blank/EOF.
        - After preceding content: ensure exactly one leading blank; ensure >=1 trailing blank.
        """
        nl: str = detect_newline(original_lines)
        out: list[str] = list(rendered_header_lines)

        # Leading padding
        if insert_index > 0:
            prev_is_blank: bool = (
                insert_index - 1 < len(original_lines)
                and original_lines[insert_index - 1].strip() == ""
            )
            if not prev_is_blank:
                out = [nl] + out

        # Trailing padding
        next_is_blank: bool = (
            insert_index < len(original_lines) and original_lines[insert_index].strip() == ""
        )
        if not next_is_blank:
            out = out + [nl]

        return out
