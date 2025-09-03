# topmark:header:start
#
#   file         : pound.py
#   file_relpath : src/topmark/pipeline/processors/pound.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header processor for pound-prefixed comment formats.

This processor supports files using `#`-style comments, such as Python, shell scripts,
and Makefiles. It delegates header processing to the core pipeline dispatcher.
"""

from topmark.config.logging import get_logger
from topmark.file_resolver import detect_newline
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import (
    HeaderProcessor,
)

logger = get_logger(__name__)


@register_filetype("dockerfile")
@register_filetype("env")
@register_filetype("git-meta")
@register_filetype("ini")
@register_filetype("julia")
@register_filetype("makefile")
@register_filetype("perl")
@register_filetype("python")
@register_filetype("python-requirements")
@register_filetype("r")
@register_filetype("ruby")
@register_filetype("shell")
@register_filetype("toml")
@register_filetype("yaml")
class PoundHeaderProcessor(HeaderProcessor):
    """Processor for files with pound-prefixed comments.

    This processor handles files that use `#` for comments, such as Python scripts,
    shell scripts, and Makefiles. It processes the header using the pipeline dispatcher.
    """

    def __init__(self) -> None:
        """Initialize a PoundHeaderProcessor instance."""
        super().__init__(
            line_prefix="#",
        )

    def prepare_header_for_insertion(
        self,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
    ) -> list[str]:
        """Apply context-aware padding around the header based on file type policy.

        - If inserting at top-of-file (index 0): do not add a leading blank; ensure
          at least one trailing blank unless the next line is already blank/EOF.
        - If inserting after a preamble (index > 0): ensure exactly one blank before
          the header (by checking the previous line); ensure at least one trailing blank
          unless the next line is already blank/EOF.

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

        policy = getattr(self.file_type, "header_policy", None) if self.file_type else None
        want_leading = 0
        want_trailing = True
        if policy is not None:
            want_leading = max(0, int(policy.pre_header_blank_after_block))
            want_trailing = bool(policy.ensure_blank_after_header)

        # Leading padding
        if insert_index == 0:
            # Top-of-file: never add a leading blank
            pass
        else:
            if want_leading > 0:
                prev_is_blank = (insert_index - 1) < len(original_lines) and original_lines[
                    insert_index - 1
                ].strip() == ""
                if not prev_is_blank:
                    out = [nl] + out

        # Trailing padding
        if want_trailing:
            next_is_blank = insert_index < len(original_lines) and (
                original_lines[insert_index].strip() == ""
            )
            if not next_is_blank:
                out = out + [nl]

        return out
