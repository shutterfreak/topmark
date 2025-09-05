# topmark:header:start
#
#   file         : slash.py
#   file_relpath : src/topmark/pipeline/processors/slash.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header processor for C-style comment formats.

This processor supports files using `//` line comments (and ecosystems that also
allow `/* ... */` block comments). It is intended for JSON-with-comments (JSONC)
files such as VS Code settings/extensions. We emit a header as `//` lines to
avoid interfering with tools that might not fully accept block comments.
"""

from __future__ import annotations

import logging

from topmark.file_resolver import detect_newline
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import HeaderProcessor

logger = logging.getLogger(__name__)


@register_filetype("c")
@register_filetype("cpp")
@register_filetype("cs")
@register_filetype("go")
@register_filetype("java")
@register_filetype("javascript")
@register_filetype("jsonc")
@register_filetype("kotlin")
@register_filetype("rust")
@register_filetype("swift")
@register_filetype("typescript")
@register_filetype("vscode-jsonc")
class SlashHeaderProcessor(HeaderProcessor):
    """Processor for files that accept C-style comments.

    We render the header as `//`-prefixed lines. Shebang handling is disabled.
    """

    def __init__(self) -> None:
        """Initialize a SlashHeaderProcessor instance."""
        super().__init__(line_prefix="//")

    def prepare_header_for_insertion(
        self,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
    ) -> list[str]:
        """Ensure a blank line after the header unless one already exists.

        We never add a leading blank at the top-of-file. We add exactly one
        trailing blank line if the next line isn't already blank or EOF.

        Args:
          original_lines (list[str]): Original file lines.
          insert_index (int): Line index where the header will be inserted.
          rendered_header_lines (list[str]): Header lines to insert.

        Returns:
          list[str]: Possibly modified header lines including any added padding.
        """
        # Detect newline style; default to "\n"
        nl = detect_newline(original_lines)
        out = list(rendered_header_lines)

        # Trailing padding: ensure one blank line after header if not already blank/EOF
        next_is_blank = (
            insert_index < len(original_lines) and original_lines[insert_index].strip() == ""
        )
        if not next_is_blank:
            out = out + [nl]

        return out
