# topmark:header:start
#
#   project      : TopMark
#   file         : slash.py
#   file_relpath : src/topmark/processors/slash.py
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

from topmark.core.logging import get_logger
from topmark.processors.base import HeaderProcessor
from topmark.processors.mixins import LineCommentMixin
from topmark.processors.registry import register_processor_for_filetype

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


@register_processor_for_filetype("c")
@register_processor_for_filetype("cpp")
@register_processor_for_filetype("cs")
@register_processor_for_filetype("go")
@register_processor_for_filetype("java")
@register_processor_for_filetype("javascript")
@register_processor_for_filetype("jsonc")
@register_processor_for_filetype("kotlin")
@register_processor_for_filetype("rust")
@register_processor_for_filetype("swift")
@register_processor_for_filetype("typescript")
@register_processor_for_filetype("vscode-jsonc")
class SlashHeaderProcessor(LineCommentMixin, HeaderProcessor):
    """Processor for files that accept C-style comments.

    We render the header as `//`-prefixed lines. Shebang handling is disabled.
    """

    # LineCommentMixin:
    line_prefix = "//"

    def __init__(self) -> None:
        # Rely on the class attribute for LineCommentMixin; just run base init.
        super().__init__()
