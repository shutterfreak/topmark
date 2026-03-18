# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/cli_shared/emitters/shared/pipeline.py
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

from topmark.cli.errors import TopmarkCliPipelineError
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.outcomes import Intent
from topmark.pipeline.outcomes import determine_intent
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus
from topmark.rendering.unified_diff import format_patch_plain

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView


# High-level emitters


def render_diff_plain(
    *,
    result: ProcessingContext,
    show_line_numbers: bool = False,
) -> str | None:
    """Render a unified diff (plain-text).

    Args:
        result: List of processing contexts to inspect.
        show_line_numbers: Prepend line numbers if True, render patch only (default).

    Returns:
        The rendered diff or None if no changes / diff in view.

    Notes:
        - This is only used for human-facing formats (TEXT and MARKDOWN).
        - Machine formats should not embed diffs.
        - Files with no changes do not emit a diff.
    """
    diff_view: DiffView | None = result.views.diff
    if diff_view is None:
        return None
    diff_text: str | None = diff_view.text
    if diff_text:
        return format_patch_plain(
            patch=diff_text,
            show_line_numbers=show_line_numbers,
        )
    return None


# Per-command guidance messages


def check_msg(r: ProcessingContext, apply_changes: bool) -> str | None:
    """Generate a per-file guidance message for `topmark check` results."""
    if not effective_would_add_or_update(r):
        return None

    intent: Intent = determine_intent(r)
    if apply_changes:
        if r.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {r.status.write.value}"
        if r.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_add_or_update is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return (
            f"➕ Adding header in '{r.path}'"
            if r.status.header == HeaderStatus.MISSING
            else f"✏️  Updating header in '{r.path}'"
        )

    if intent == Intent.INSERT:
        action: str = "add a TopMark header to this file"
    elif intent == Intent.UPDATE:
        action = "update the TopMark header in this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in check pipeline.",
        )
    return f"🛠️  Run `topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} {r.path}` to {action}."


def strip_msg(r: ProcessingContext, apply_changes: bool) -> str | None:
    """Generate a per-file guidance message for `topmark strip` results."""
    if not effective_would_strip(r):
        return None

    intent: Intent = determine_intent(r)
    if apply_changes:
        if r.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {r.status.write.value}"
        if r.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_strip is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return f"🧹 Stripping header in '{r.path}'"

    if intent == Intent.STRIP:
        action: str = "strip the TopMark header from this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in check pipeline.",
        )
    return f"🛠️  Run `topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} {r.path}` to {action}."
