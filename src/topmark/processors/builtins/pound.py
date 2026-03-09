# topmark:header:start
#
#   project      : TopMark
#   file         : pound.py
#   file_relpath : src/topmark/processors/builtins/pound.py
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

from topmark.core.logging import get_logger
from topmark.processors.base import HeaderProcessor
from topmark.processors.mixins import LineCommentMixin

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


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
