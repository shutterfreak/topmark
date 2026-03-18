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


def display_path(r: ProcessingContext) -> str:
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
    if r.config.stdin_mode and r.config.stdin_filename:
        return r.config.stdin_filename
    return str(r.path)


def display_path_label(r: ProcessingContext) -> str:
    """Return a short user-facing path label for TEXT output.

    This is like [`display_path()`][topmark.cli_shared.emitters.shared.pipeline.display_path]
    but formats the path for human TEXT output:

    - The path is wrapped in single quotes for readability.
    - STDIN content mode is annotated with "(via STDIN)" to clarify that TopMark
      processed content from standard input using a temporary file.

    Args:
        r: Processing context to render.

    Returns:
        A short label suitable for TEXT messages.
    """
    path: str = display_path(r)
    if r.config.stdin_mode and r.config.stdin_filename:
        return f"'{path}' (via STDIN)"

    return f"'{path}'"


# Markdown helpers


def markdown_code_span(text: str) -> str:
    """Render `text` as a Markdown inline code span.

    This chooses a backtick fence that is one longer than the longest run of
    backticks in `text`, which safely supports filenames that contain backticks.

    Args:
        text: Raw text to wrap.

    Returns:
        Markdown inline code span.
    """
    max_run: int = 0
    run: int = 0
    for ch in text:
        if ch == "`":
            run += 1
            if run > max_run:
                max_run = run
        else:
            run = 0

    fence: str = "`" * (max_run + 1)
    return f"{fence}{text}{fence}"


def display_path_label_markdown(r: ProcessingContext) -> str:
    """Return a short user-facing path label for MARKDOWN output.

    This is like [`display_path()`][topmark.cli_shared.emitters.shared.pipeline.display_path]
    but formats the path for Markdown:

    - The path is rendered as an inline code span.
    - STDIN content mode is annotated with "(via STDIN)" (emphasized) to clarify
      that TopMark processed content from standard input.

    Args:
        r: Processing context to render.

    Returns:
        A short label suitable for Markdown headings and list items.
    """
    path: str = display_path(r)
    code: str = markdown_code_span(path)

    if r.config.stdin_mode and r.config.stdin_filename:
        return f"{code} _(via STDIN)_"

    return code


def check_msg_text(r: ProcessingContext, apply_changes: bool) -> str | None:
    """Generate a per-file guidance message for `topmark check` results."""
    if not effective_would_add_or_update(r):
        return None

    path_label: str = display_path_label(r)
    path_name: str = display_path(r)
    intent: Intent = determine_intent(r)

    if apply_changes:
        if r.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {r.status.write.value}"
        if r.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_add_or_update is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return (
            f"➕ Adding header in {path_label}"
            if r.status.header == HeaderStatus.MISSING
            else f"✏️  Updating header in {path_label}"
        )

    if r.config.stdin_mode and r.config.stdin_filename:
        apply_cmd: str = (
            f"topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} '{path_name}' -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} '{path_name}'"

    if intent == Intent.INSERT:
        action: str = "add a TopMark header to this file"
    elif intent == Intent.UPDATE:
        action = "update the TopMark header in this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in check pipeline.",
        )
    return f"🛠️  Run `{apply_cmd}` to {action}."


def strip_msg_text(r: ProcessingContext, apply_changes: bool) -> str | None:
    """Generate a per-file guidance message for `topmark strip` results."""
    if not effective_would_strip(r):
        return None

    path_label: str = display_path_label(r)
    path_name: str = display_path(r)
    intent: Intent = determine_intent(r)

    if apply_changes:
        if r.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {r.status.write.value}"
        if r.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_strip is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return f"🧹 Stripping header in {path_label}"

    if r.config.stdin_mode and r.config.stdin_filename:
        apply_cmd: str = (
            f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} '{path_name}' -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} '{path_name}'"

    if intent == Intent.STRIP:
        action: str = "strip the TopMark header from this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in check pipeline.",
        )
    return f"🛠️  Run `{apply_cmd}` to {action}."


def check_msg_markdown(r: ProcessingContext, apply_changes: bool) -> str | None:
    """Generate a per-file guidance message for `topmark check` (MARKDOWN output)."""
    if not effective_would_add_or_update(r):
        return None

    path_label: str = display_path_label_markdown(r)
    path_name: str = display_path(r)
    intent: Intent = determine_intent(r)

    if apply_changes:
        if r.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {r.status.write.value}"
        if r.status.write == WriteStatus.SKIPPED:
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return (
            f"➕ Adding header in {path_label}"
            if r.status.header == HeaderStatus.MISSING
            else f"✏️  Updating header in {path_label}"
        )

    if r.config.stdin_mode and r.config.stdin_filename:
        apply_cmd: str = (
            f"topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} '{path_name}' -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} '{path_name}'"

    if intent == Intent.INSERT:
        action: str = "add a TopMark header to this file"
    elif intent == Intent.UPDATE:
        action = "update the TopMark header in this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in check pipeline.",
        )
    return f"🛠️  Run `{apply_cmd}` to {action}."


def strip_msg_markdown(r: ProcessingContext, apply_changes: bool) -> str | None:
    """Generate a per-file guidance message for `topmark strip` (MARKDOWN output)."""
    if not effective_would_strip(r):
        return None

    path_label: str = display_path_label_markdown(r)
    path_name: str = display_path(r)
    intent: Intent = determine_intent(r)

    if apply_changes:
        if r.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {r.status.write.value}"
        if r.status.write == WriteStatus.SKIPPED:
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return f"🧹 Stripping header in {path_label}"

    if r.config.stdin_mode and r.config.stdin_filename:
        apply_cmd: str = (
            f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} '{path_name}' -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} '{path_name}'"

    if intent == Intent.STRIP:
        action: str = "strip the TopMark header from this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in check pipeline.",
        )
    return f"🛠️  Run `{apply_cmd}` to {action}."
