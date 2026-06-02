# topmark:header:start
#
#   project      : TopMark
#   file         : paths.py
#   file_relpath : src/topmark/presentation/shared/paths.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared human-facing path presentation helpers.

This module contains frontend-neutral display helpers for path labels used by
human-facing renderers. These helpers intentionally model presentation policy,
not machine-readable path serialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


def get_display_path(
    ctx: ProcessingContext,
) -> str:
    """Return the user-facing path to display for a processing result.

    TopMark may process *content-on-STDIN* by writing it to a temporary file.
    In that mode, `ProcessingContext.path` points at the temporary file on disk,
    but users expect messages to refer to the logical filename supplied via
    `--stdin-filename`.

    This helper centralizes that policy so all human-facing renderers display
    the same path labels.

    Args:
        ctx: Processing context to render.

    Returns:
        The logical filename in STDIN content mode, otherwise the actual file path.
    """
    if ctx.run_options.stdin_mode and bool(ctx.run_options.stdin_filename):
        return ctx.run_options.stdin_filename
    return str(ctx.path)


def render_path_display_text(ctx: ProcessingContext) -> str:
    """Render a short TEXT path label for headings and guidance messages.

    This helper formats
    [`get_display_path()`][topmark.presentation.shared.paths.get_display_path]
    for human-facing TEXT output and annotates STDIN-backed content with `(via STDIN)`
    when a synthetic filename is available.

    Args:
        ctx: Processing context containing the path to display.

    Returns:
        Short TEXT label for per-file headings and guidance messages.
    """
    path: str = get_display_path(ctx)
    if ctx.run_options.stdin_mode and bool(ctx.run_options.stdin_filename):
        return f"'{path}' (via STDIN)"

    return f"'{path}'"
