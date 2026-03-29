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

from topmark.cli.errors import TopmarkCliPipelineError
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.formats import OutputFormat
from topmark.core.presentation import StyleRole
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.outcomes import Intent
from topmark.pipeline.outcomes import determine_intent
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus
from topmark.presentation.markdown.pipeline import render_pipeline_banner_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_diffs_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_per_file_guidance_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_summary_counts_markdown
from topmark.presentation.markdown.utils import markdown_code_span
from topmark.presentation.text.pipeline import render_pipeline_banner_text
from topmark.presentation.text.pipeline import render_pipeline_diffs_text
from topmark.presentation.text.pipeline import render_pipeline_per_file_guidance_text
from topmark.presentation.text.pipeline import render_pipeline_summary_counts_text
from topmark.rendering.unified_diff import format_patch_plain

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView


# High-level emitters


def display_path_label_markdown(r: ProcessingContext) -> str:
    """Return a short user-facing path label for MARKDOWN output.

    This is like [`display_path()`][topmark.presentation.shared.pipeline.display_path]
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

    This is like [`display_path()`][topmark.presentation.shared.pipeline.display_path]
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


def check_msg_text(
    r: ProcessingContext,
    apply_changes: bool,
) -> str | None:
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


def strip_msg_text(
    r: ProcessingContext,
    apply_changes: bool,
) -> str | None:
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


def check_msg_markdown(
    r: ProcessingContext,
    apply_changes: bool,
) -> str | None:
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


def strip_msg_markdown(
    r: ProcessingContext,
    apply_changes: bool,
) -> str | None:
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


def render_pipeline_hidden_unsupported_footer_human(
    *,
    fmt: OutputFormat,
    unsupported_count: int,
    styled: bool,
) -> str:
    """Render the footer after a pipeline 'apply' command.

    Args:
        fmt: Output format.
        unsupported_count: Count of unsupported files.
        styled: Whether to render the TEXT output with ANSI styles.

    Returns:
        Footer as plain string.
    """
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    warning_styler: TextStyler = style_for_role(StyleRole.WARNING, styled=styled)

    if fmt == OutputFormat.TEXT:
        return warning_styler(
            f"⚠️  Unsupported: {unsupported_count} file(s) "
            f"(use {CliOpt.REPORT}={ReportScope.NONCOMPLIANT.value} to list)",
        )
    elif fmt == OutputFormat.MARKDOWN:
        return (
            f"\n> ⚠️ Unsupported: {unsupported_count} file(s) "
            f"(use {CliOpt.REPORT}={ReportScope.NONCOMPLIANT.value} to list)\n"
        )
    return ""


# Pipeline command helpers (check/strip)


def render_pipeline_human_output(
    *,
    cmd: str,
    file_list_total: int,
    view_results: list[ProcessingContext],
    report: ReportScope,
    unsupported_count: int,
    fmt: OutputFormat,
    verbosity_level: int,
    summary_mode: bool,
    show_diffs: bool,
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    enable_color: bool,
) -> str:
    """Emit human-facing output for pipeline commands.

    This unifies TEXT (ANSI) and MARKDOWN output for pipeline-oriented
    commands like `check` and `strip`.

    Notes:
        This helper only supports `TEXT` and `MARKDOWN`.

    Args:
        cmd: Command name (e.g. "check", "strip").
        file_list_total: Total number of candidate files (before view filtering).
        view_results: Filtered results to render.
        report: Controls which per-file entries are rendered for human output.
        unsupported_count: Unsupported file count.
        fmt: Human output format.
        verbosity_level: Effective verbosity for gating banners/details.
        summary_mode: If True, show outcome counts only.
        show_diffs: If True, render unified diffs (human formats only).
        make_message: Per-file guidance message factory.
        apply_changes: Whether changes are being applied (vs dry-run).
        enable_color: Whether ANSI output should be colorized.

    Returns:
        Human output rendered as single string.

    Raises:
        ValueError: When an unsupported human output format was provided.
    """
    if fmt not in (OutputFormat.TEXT, OutputFormat.MARKDOWN):
        raise ValueError(f"Unsupported human output format: {fmt}")

    parts: list[str] = []

    # Banner (verbosity-gated)
    if verbosity_level > 0:
        if fmt == OutputFormat.TEXT:
            parts.append(
                render_pipeline_banner_text(
                    cmd=cmd,
                    n_files=file_list_total,
                    styled=enable_color,
                )
            )
        else:
            parts.append(
                render_pipeline_banner_markdown(
                    cmd=cmd,
                    n_files=file_list_total,
                )
            )
            parts.append("")

    # Summary mode (grouped by `(outcome, reason)`)
    if summary_mode:
        if show_diffs:
            if fmt == OutputFormat.TEXT:
                parts.append(
                    render_pipeline_diffs_text(
                        results=view_results,
                        color=enable_color,
                    )
                )
            else:
                parts.append(render_pipeline_diffs_markdown(results=view_results))
        if fmt == OutputFormat.TEXT:
            parts.append(
                render_pipeline_summary_counts_text(
                    view_results=view_results,
                    total=file_list_total,
                    styled=enable_color,
                )
            )
        else:
            parts.append(
                render_pipeline_summary_counts_markdown(
                    view_results=view_results,
                    total=file_list_total,
                )
            )

    # Per-file guidance
    elif fmt == OutputFormat.TEXT:
        parts.append(
            render_pipeline_per_file_guidance_text(
                view_results=view_results,
                make_message=make_message,
                apply_changes=apply_changes,
                show_diffs=show_diffs,
                verbosity_level=verbosity_level,
                color=enable_color,
            )
        )
    else:
        parts.append(
            render_pipeline_per_file_guidance_markdown(
                view_results=view_results,
                make_message=make_message,
                apply_changes=apply_changes,
                show_diffs=show_diffs,
                verbosity_level=verbosity_level,
            ),
        )

    # In actionable mode, unsupported files are hidden from the per-file listing but summarized
    # for visibility.
    if (not summary_mode) and (report == ReportScope.ACTIONABLE) and (unsupported_count > 0):
        parts.append(
            render_pipeline_hidden_unsupported_footer_human(
                fmt=fmt,
                unsupported_count=unsupported_count,
                styled=enable_color,
            )
        )

    return "\n".join(parts)


def render_pipeline_apply_summary_human(
    *,
    fmt: OutputFormat,
    command_path: str,
    written: int,
    failed: int,
    styled: bool,
) -> str:
    """Emit a short human-facing apply summary footer.

    This is only for human formats (TEXT/MARKDOWN). Machine formats must never emit
    human summaries.

    Args:
        fmt: Human output format (TEXT or MARKDOWN).
        command_path: Command path (e.g. "topmark check", "topmark strip").
        written: Number of files written.
        failed: Number of files that failed to write.
        styled: Whether to style the output with ANSI styles.

    Returns:
        Summary rendered as single string.
    """
    if fmt not in (OutputFormat.TEXT, OutputFormat.MARKDOWN):
        return ""

    parts: list[str] = []
    if fmt == OutputFormat.TEXT:
        # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
        changed_styler: TextStyler = style_for_role(
            StyleRole.CHANGED,
            styled=styled,
        )
        warning_styler: TextStyler = style_for_role(StyleRole.WARNING, styled=styled)
        if written:
            msg: str = f"\n✅ {command_path}: applied changes to {written} file(s)."
        else:
            msg = f"\n✅ {command_path}: no changes to apply."
        parts.append(changed_styler(msg))
        if failed:
            parts.append(
                warning_styler(
                    f"\n⚠️ {command_path}: failed to write {failed} file(s). See log for details.",
                )
            )
        return "\n".join(parts)

    # MARKDOWN
    cmd_md: str = markdown_code_span(command_path)
    if written:
        parts.append(f"\n✅ {cmd_md}: applied changes to **{written}** file(s).\n")
    else:
        parts.append(f"\n✅ {cmd_md}: no changes to apply.\n")
    if failed:
        parts.append(
            f"\n> ⚠️ {cmd_md}: failed to write **{failed}** file(s). See log for details.\n"
        )

    return "\n".join(parts)
