# topmark:header:start
#
#   project      : TopMark
#   file         : slash.py
#   file_relpath : src/topmark/pipeline/processors/slash.py
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

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.processors.mixins import LineCommentMixin

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


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
class SlashHeaderProcessor(LineCommentMixin, HeaderProcessor):
    """Processor for files that accept C-style comments.

    We render the header as `//`-prefixed lines. Shebang handling is disabled.
    """

    # LineCommentMixin:
    line_prefix = "//"

    def __init__(self) -> None:
        # Rely on the class attribute for LineCommentMixin; just run base init.
        super().__init__()
