# topmark:header:start
#
#   project      : TopMark
#   file         : pound.py
#   file_relpath : src/topmark/pipeline/processors/pound.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header processor for pound-prefixed comment formats.

This processor supports files using `#`-style comments, such as Python, shell scripts,
and Makefiles. It delegates header processing to the core pipeline dispatcher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.file_resolver import detect_newline
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import (
    HeaderProcessor,
)
from topmark.pipeline.processors.mixins import LineCommentMixin

if TYPE_CHECKING:
    from topmark.filetypes.policy import FileTypeHeaderPolicy

logger: TopmarkLogger = get_logger(__name__)


@register_filetype("dockerfile")
@register_filetype("env")
@register_filetype("git-meta")
@register_filetype("ini")
@register_filetype("julia")
@register_filetype("makefile")
@register_filetype("perl")
@register_filetype("python")
@register_filetype("python-requirements")
@register_filetype("python-stub")
@register_filetype("r")
@register_filetype("ruby")
@register_filetype("shell")
@register_filetype("toml")
@register_filetype("yaml")
class PoundHeaderProcessor(LineCommentMixin, HeaderProcessor):
    """Header processor for line-comment `#` files (uses LineCommentMixin).

    This processor handles files that use `#` for comments, such as Python scripts,
    shell scripts, and Makefiles. It processes the header using the pipeline dispatcher.

    Respects FileTypeHeaderPolicy for shebang and encoding line handling.
    """

    # LineCommentMixin:
    line_prefix = "#"

    def __init__(self) -> None:
        # Rely on the class attribute for LineCommentMixin; just run base init.
        super().__init__()

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
        nl: str = detect_newline(original_lines)
        out: list[str] = list(rendered_header_lines)

        policy: FileTypeHeaderPolicy | None = (
            self.file_type.header_policy if self.file_type else None
        )

        want_leading: int = 0
        want_trailing: bool = True
        if policy is not None:
            want_leading = max(0, int(policy.pre_header_blank_after_block))
            want_trailing = bool(policy.ensure_blank_after_header)

        # Leading padding
        if insert_index == 0:
            # Top-of-file: never add a leading blank
            pass
        else:
            if want_leading > 0:
                prev_is_blank: bool = (insert_index - 1) < len(original_lines) and original_lines[
                    insert_index - 1
                ].strip() == ""
                if not prev_is_blank:
                    out = [nl] + out

        # Trailing padding
        if want_trailing:
            next_is_blank: bool = insert_index < len(original_lines) and (
                original_lines[insert_index].strip() == ""
            )
            if not next_is_blank:
                out = out + [nl]

        return out
