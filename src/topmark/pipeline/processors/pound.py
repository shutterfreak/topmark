# topmark:header:start
#
#   file         : pound.py
#   file_relpath : src/topmark/pipeline/processors/pound.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""
Header processor for pound-prefixed comment formats.

This processor supports files using `#`-style comments, such as Python, shell scripts,
and Makefiles. It delegates header processing to the core pipeline dispatcher.
"""

import re

from topmark.config.logging import get_logger
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
    """
    Processor for files with pound-prefixed comments.

    This processor handles files that use `#` for comments, such as Python scripts,
    shell scripts, and Makefiles. It processes the header using the pipeline dispatcher.
    """

    def __init__(self) -> None:
        """Initialize a PoundHeaderProcessor instance."""
        super().__init__(
            line_prefix="#",
        )

    def get_header_insertion_index(self, file_lines: list[str]) -> int:
        """Determine where to insert the header based on file type and syntax.

        Two pathways:
        - Top-of-file (no shebang): return 0.
        - After shebang (+ optional encoding): return the first non-blank line
          after that block, consuming at most one existing blank line so the
          blank (if present) sits between shebang/encoding and the header.

        Args:
            file_lines: List of lines from the file being processed.

        Returns:
            Index at which to insert the TopMark header.
        """
        logger.info(f"{self.__class__.__name__}.file_type = {self.file_type}")

        assert self.file_type is not None, (
            f"{self.__class__.__name__} is not linked to a FileType via @register_filetype"
        )
        policy = getattr(self.file_type, "header_policy", None)

        index = 0
        shebang_present = False

        # Shebang handling based on policy
        if policy and policy.supports_shebang and file_lines and file_lines[0].startswith("#!"):
            shebang_present = True
            index = 1

            # Optional encoding line immediately after shebang (e.g., Python)
            if policy.encoding_line_regex and len(file_lines) > index:
                if re.search(policy.encoding_line_regex, file_lines[index]):
                    index += 1

        # If a shebang block exists and the next line is already blank, consume exactly one
        if shebang_present and index < len(file_lines) and file_lines[index].strip() == "":
            index += 1

        return index

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
        """

        # Detect newline style; default to "\n"
        def detect_newline(lines: list[str]) -> str:
            for ln in lines:
                if ln.endswith("\r\n"):
                    return "\r\n"
                if ln.endswith("\n"):
                    return "\n"
                if ln.endswith("\r"):
                    return "\r"
            return "\n"

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
