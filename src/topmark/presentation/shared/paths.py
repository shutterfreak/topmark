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
human-facing renderers. The helpers intentionally model presentation policy, not
machine-readable path serialization.

During the ProcessingContext-to-ProcessingResult migration these helpers accept
both volatile processing contexts and durable processing results. Context support
is still required by pre-reduction consumers such as probe rendering and patch
header generation, while result support lets check/strip presentation render from
the durable reduction boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.result import ProcessingResult

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


def get_display_path(
    ctx: ProcessingContext | ProcessingResult,
) -> str:
    """Return the user-facing path to display for processing output.

    TopMark may process *content-on-STDIN* by writing it to a temporary file.
    In that mode, `ProcessingContext.path` points at the temporary file on disk,
    while `ProcessingResult.display_path` captures the logical display path at
    the reduction boundary. Users expect messages to refer to the logical
    filename supplied via `--stdin-filename`.

    This helper centralizes the shared policy while both pre-reduction context
    consumers and post-reduction result consumers still need identical display
    labels.

    Args:
        ctx: Processing context or durable result to render.

    Returns:
        The logical filename in STDIN content mode, otherwise the processing path.
    """
    if isinstance(ctx, ProcessingResult):
        return ctx.display_path
    if ctx.run_options.stdin_mode and bool(ctx.run_options.stdin_filename):
        return ctx.run_options.stdin_filename
    return str(ctx.path)


def render_path_display_text(
    ctx: ProcessingContext | ProcessingResult,
) -> str:
    """Render a short TEXT path label for headings and guidance messages.

    This helper formats
    [`get_display_path()`][topmark.presentation.shared.paths.get_display_path]
    for human-facing TEXT output and annotates STDIN-backed content with `(via STDIN)`
    when a synthetic filename is available.

    Args:
        ctx: Processing context or durable result containing the path to display.

    Returns:
        Short TEXT label for per-file headings and guidance messages.
    """
    path: str = get_display_path(ctx)
    from_stdin: bool = (
        ctx.from_stdin
        if isinstance(ctx, ProcessingResult)
        else bool(ctx.run_options.stdin_mode and ctx.run_options.stdin_filename)
    )

    if from_stdin:
        return f"'{path}' (via STDIN)"

    return f"'{path}'"
