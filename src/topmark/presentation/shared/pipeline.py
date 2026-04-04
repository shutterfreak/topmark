# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/presentation/shared/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared pipeline rendering utilities (Click-free).

This module provides small rendering primitives and per-command guidance helpers used by both
`TEXT` (ANSI) and `MARKDOWN` pipeline emitters.

It is intentionally CLI-framework independent: no Click usage and no direct console output. Callers
are responsible for printing or styling the returned strings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext


def get_display_path(
    r: ProcessingContext,
) -> str:
    """Return the user-facing path to display for a processing result.

    TopMark may process *content-on-STDIN* by writing it to a temporary file.
    In that mode, `ProcessingContext.path` points at the temporary file on disk,
    but users expect messages to refer to the logical filename supplied via
    `--stdin-filename`.

    This helper centralizes that policy so all human-facing emitters (TEXT and
    MARKDOWN) remain consistent.

    Args:
        r: Processing context to render.

    Returns:
        The logical filename in STDIN content mode, otherwise the actual file path.
    """
    if r.run_options.stdin_mode and bool(r.run_options.stdin_filename):
        return r.run_options.stdin_filename
    return str(r.path)


# High-level emitters
