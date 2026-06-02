# topmark:header:start
#
#   project      : TopMark
#   file         : paths.py
#   file_relpath : src/topmark/presentation/markdown/paths.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown-specific human-facing path presentation helpers.

This module adapts shared display-path policy to Markdown output by applying
Markdown-specific escaping and STDIN annotations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.presentation.markdown.utils import markdown_code_span
from topmark.presentation.shared.paths import get_display_path

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


def render_path_display_markdown(ctx: ProcessingContext) -> str:
    """Render a short Markdown path label for headings and list items.

    This helper formats
    [`get_display_path()`][topmark.presentation.shared.paths.get_display_path]
    for Markdown and annotates STDIN-backed content with ``_(via STDIN)_`` when a
    synthetic filename is available.

    The shared display-path policy determines the raw path label; this helper then
    applies Markdown-specific code-span escaping and STDIN annotation rendering.

    Args:
        ctx: Processing context containing the path to display.

    Returns:
        Short Markdown label for per-file headings and guidance messages.
    """
    path: str = get_display_path(ctx)
    code: str = markdown_code_span(path)

    if ctx.run_options.stdin_mode and bool(ctx.run_options.stdin_filename):
        return f"{code} _(via STDIN)_"

    return code
