# topmark:header:start
#
#   file         : policy.py
#   file_relpath : src/topmark/filetypes/policy.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Policy describing how headers should be inserted for a file type."""

from dataclasses import dataclass

from ..config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FileTypeHeaderPolicy:
    """Policy describing how headers should be inserted for a file type.

    These traits are optional and allow processors to remain generic while
    file-type specifics (shebang presence, encoding declarations, spacing
    rules) are declared on the file type.

    Attributes:
        supports_shebang: Whether this file type commonly starts with a shebang.
        encoding_line_regex: Optional regex (string) to detect an encoding line
            immediately after a shebang (e.g., Python PEP 263).
        pre_header_blank_after_block: Desired number of blank lines between any
            preamble block (shebang/encoding) and the TopMark header. Typically 1.
        ensure_blank_after_header: Ensure there is at least one blank line after
            the TopMark header block.
    """

    supports_shebang: bool = False
    encoding_line_regex: str | None = None
    pre_header_blank_after_block: int = 1
    ensure_blank_after_header: bool = True

    allow_prolog: bool = True
    require_header_on_own_lines: bool = True
