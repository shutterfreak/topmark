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

from topmark.config.logging import get_logger
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.processors.mixins import LineCommentMixin

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger

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
