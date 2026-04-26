# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/presentation/markdown/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown pipeline renderers for the TopMark CLI.

This module renders human-facing Markdown output for pipeline-oriented commands
such as `topmark check` and `topmark strip`.

Markdown output is document-oriented: it intentionally ignores TEXT-only
verbosity, quiet, and styling controls. Pipeline content is controlled by
semantic command options such as `--summary`, `--report`, and `--diff`.

Notes:
    - TEXT output is implemented in [`topmark.presentation.text`][topmark.presentation.text].
    - Machine output is handled via domain machine serializers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.errors import TopmarkCliPipelineError
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.outcomes import Intent
from topmark.pipeline.outcomes import ResultBucket
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.pipeline.outcomes import determine_intent
from topmark.pipeline.outcomes import map_bucket
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus
from topmark.presentation.markdown.diagnostic import render_diagnostics_markdown
from topmark.presentation.markdown.utils import markdown_code_span
from topmark.presentation.markdown.utils import render_markdown_table
from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
from topmark.presentation.shared.pipeline import get_display_path
from topmark.rendering.unified_diff import format_patch_plain

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.diagnostic.model import DiagnosticStats
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.outcomes import OutcomeReasonCount
    from topmark.pipeline.views import DiffView

# ---- Path rendering ----


def _render_path_display_markdown(ctx: ProcessingContext) -> str:
    """Render a short Markdown path label for headings and list items.

    This helper formats
    [`get_display_path()`][topmark.presentation.shared.pipeline.get_display_path]
    for Markdown and annotates STDIN-backed content with ``_(via STDIN)_`` when a
    synthetic filename is available.

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


# ---- Hint rendering ----


def _render_hint_markdown(
    hint: Hint,
    *,
    last: bool,
) -> str:
    """Render a single hint as Markdown.

    Args:
        hint: Hint to render.
        last: Whether this is the last/decisive hint in the rendered subset.

    Returns:
        Markdown fragment for one hint entry.
    """
    lines: list[str] = []

    # Prepend a marker for terminal hints or the last (directive) hint
    marker: str = "⏹" if hint.terminal else ("▶" if last else "•")
    axis: str = hint.axis.value
    cluster: str = hint.cluster or ""
    code: str = hint.code
    message: str = hint.message
    terminal_suffix: str = " (terminal)" if hint.terminal else ""

    lines.append(f"    - {marker} **{axis}** (`{cluster}`) `{code}`: {message}{terminal_suffix}")

    # Optional detail
    if hint.detail:
        for line in hint.detail.splitlines():
            lines.append(f"      {line}")

    return "\n".join(lines)


# ---- Banner rendering ----


def _render_pipeline_banner_markdown(
    *,
    cmd: str,
    n_files: int,
) -> str:
    """Render the Markdown banner for a pipeline command.

    Args:
        cmd: Command name.
        n_files: Number of candidate files.

    Returns:
        Markdown banner shown before the main pipeline output.
    """
    return "\n".join(
        [
            f"# TopMark {cmd} Results",
            "",
            f"Processing **{n_files}** file(s).",
        ]
    )


# ---- Command guidance rendering ----


def _render_check_guidance_message_markdown(
    ctx: ProcessingContext,
    apply_changes: bool,
) -> str | None:
    """Render per-file guidance for `topmark check` results.

    Args:
        ctx: Processing context for the file.
        apply_changes: Whether the command runs in apply mode.

    Returns:
        Guidance message for this file, or `None` when no check action is relevant.

    Raises:
        TopmarkCliPipelineError: If the resolved intent is invalid for the `check`
            pipeline.
    """
    if not effective_would_add_or_update(ctx):
        return None

    path_label: str = _render_path_display_markdown(ctx)
    path_name: str = get_display_path(ctx)
    intent: Intent = determine_intent(ctx)

    if apply_changes:
        if ctx.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {ctx.status.write.value}"
        if ctx.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_add_or_update is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return (
            f"➕ Adding header in {path_label}"
            if ctx.status.header == HeaderStatus.MISSING
            else f"✏️  Updating header in {path_label}"
        )

    if ctx.run_options.stdin_mode and ctx.run_options.stdin_filename:
        apply_cmd: str = (
            f"topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} {path_name} -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} {path_name}"

    if intent == Intent.INSERT:
        action: str = "add a TopMark header to this file"
    elif intent == Intent.UPDATE:
        action = "update the TopMark header in this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in 'check' pipeline.",
        )
    cmd_md: str = markdown_code_span(apply_cmd)
    return f"🛠️  Run {cmd_md} to {action}."


def _render_strip_guidance_message_markdown(
    ctx: ProcessingContext,
    apply_changes: bool,
) -> str | None:
    """Render per-file guidance for `topmark strip` results.

    Args:
        ctx: Processing context for the file.
        apply_changes: Whether the command runs in apply mode.

    Returns:
        Guidance message for this file, or `None` when no strip action is relevant.

    Raises:
        TopmarkCliPipelineError: If the resolved intent is invalid for the `strip`
            pipeline.
    """
    if not effective_would_strip(ctx):
        return None

    path_label: str = _render_path_display_markdown(ctx)
    path_name: str = get_display_path(ctx)
    intent: Intent = determine_intent(ctx)

    if apply_changes:
        if ctx.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {ctx.status.write.value}"
        if ctx.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_strip is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return f"🧹 Stripping header in {path_label}"

    if ctx.run_options.stdin_mode and ctx.run_options.stdin_filename:
        apply_cmd: str = (
            f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} {path_name} -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} {path_name}"

    if intent == Intent.STRIP:
        action: str = "strip the TopMark header from this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in 'strip' pipeline.",
        )
    cmd_md: str = markdown_code_span(apply_cmd)
    return f"🛠️  Run {cmd_md} to {action}."


# ---- Per-file rendering ----


def _render_file_summary_line_markdown(
    *,
    ctx: ProcessingContext,
) -> str:
    """Render a concise one-line Markdown summary for one file.

    The summary is driven by [`map_bucket()`][topmark.pipeline.outcomes.map_bucket]
    and may append compact write, diff, or diagnostic hints.

    Args:
        ctx: Processing context containing status and view data.

    Returns:
        One-line Markdown summary for the file.
    """
    # File type, or <unknown> if resolution failed
    ft: str = ctx.file_type.local_key if ctx.file_type is not None else "<unknown>"

    # Resolve the public bucket for this context.
    apply_changes: bool = ctx.run_options.apply_changes is True
    bucket: ResultBucket = map_bucket(ctx, apply=apply_changes)
    key: str = bucket.outcome.value
    label: str = bucket.reason or "(no reason provided)"

    # Secondary hints: write status > diff marker > diagnostics
    parts: list[str] = []
    if ctx.status.has_write_outcome():
        parts.append(ctx.status.write.value)
    elif ctx.views.diff and ctx.views.diff.text:
        parts.append("diff")

    if ctx.diagnostics:
        # Compose a compact triage summary such as "1 error, 2 warnings".
        stats: DiagnosticStats = ctx.diagnostics.stats()
        triage_summary: str = stats.triage_summary()
        if triage_summary:
            parts.append(triage_summary)

    suffix: str = (" — " + " - ".join(parts)) if parts else ""
    return f"`{get_display_path(ctx)}` ({ft}) — `{key}`: {label}{suffix}"


def _render_per_file_guidance_markdown(
    *,
    view_results: list[ProcessingContext],
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    show_diffs: bool,
) -> str:
    """Render per-file Markdown sections.

    For each file, this includes:
        1. A summary line.
        2. An optional guidance message.
        3. Diagnostics when present.
        4. Diagnostic hints when present.
        5. An optional diff block.

    Unlike TEXT output, Markdown always renders available diagnostics and hints,

    Args:
        view_results: Processing contexts to render.
        make_message: Per-file guidance message builder.
        apply_changes: Whether the command runs in apply mode.
        show_diffs: Whether to include unified diffs.

    Returns:
        Markdown fragment containing all rendered file sections.
    """
    blocks: list[str] = []
    blocks.append("## Files")
    blocks.append("")

    for idx, ctx in enumerate(view_results, start=1):
        # 1. summary line.
        blocks.append(
            f"{idx}. "
            + _render_file_summary_line_markdown(
                ctx=ctx,
            )
        )

        # 2. guidance message (in case changes can be applied)
        msg: str | None = make_message(ctx, apply_changes)
        if msg:
            blocks.append(f"  - {msg}")

        # 3. diagnostics block; Markdown shows diagnostics whenever present.
        if len(ctx.diagnostics) > 0:
            diag_md: str = render_diagnostics_markdown(
                diagnostics=ctx.diagnostics,
            ).rstrip()
            if diag_md:
                for line in diag_md.splitlines():
                    blocks.append(f"  {line}" if line else "")

        # 4. hints; Markdown shows all hints whenever present.
        hints: list[Hint] = ctx.diagnostic_hints.items
        hints_count: int = len(hints)
        if hints_count > 0:
            blocks.append(f"  - Hints: {hints_count}")

            for i, h in enumerate(hints, start=1):
                blocks.append(
                    _render_hint_markdown(
                        hint=h,
                        last=i == hints_count,
                    )
                )

        # 5. optional diff block
        if show_diffs:
            diff: str | None = _render_diff_markdown(ctx.views.diff)
            if diff:
                blocks.append("")
                blocks.append("```diff")
                blocks.append(diff.rstrip("\n"))
                blocks.append("```")

        blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


# ---- Diff rendering ----


def _render_diff_markdown(
    diff_view: DiffView | None,
    *,
    show_line_numbers: bool = False,
) -> str | None:
    """Render a unified diff as plain Markdown-friendly text.

    Args:
        diff_view: Diff view to render.
        show_line_numbers: Whether to prepend line numbers.

    Returns:
        Rendered diff text, or `None` when no diff is available.
    """
    if diff_view is None:
        return None
    diff_text: str | None = diff_view.text
    if diff_text:
        return format_patch_plain(
            patch=diff_text,
            show_line_numbers=show_line_numbers,
        )
    return None


def _render_pipeline_diffs_markdown(
    *,
    results: list[ProcessingContext],
    show_line_numbers: bool = False,
) -> str:
    """Render a Markdown diff section for all files with diffs.

    Args:
        results: Processing contexts to inspect.
        show_line_numbers: Whether to prepend line numbers.

    Returns:
        Markdown diff section.
    """
    # Keep Markdown diffs readable and copyable.
    blocks: list[str] = ["## Diffs", ""]
    for ctx in results:
        diff: str | None = _render_diff_markdown(
            ctx.views.diff,
            show_line_numbers=show_line_numbers,
        )
        if diff:
            blocks.append(f"### {_render_path_display_markdown(ctx)}")
            blocks.append("")
            blocks.append("```diff")
            blocks.append(diff.rstrip("\n"))
            blocks.append("```")
            blocks.append("")
    if len(blocks) > 2:
        blocks.append("")
    return "\n".join(blocks).rstrip()


# ---- Summary rendering ----


def _render_summary_counts_markdown(
    *,
    view_results: list[ProcessingContext],
    total: int,
) -> str:
    """Render summary counts grouped by `(outcome, reason)` as a Markdown table.

    Args:
        view_results: Processing contexts included in the rendered view.
        total: Total number of candidate files before view filtering.

    Returns:
        Markdown summary table with grouped outcome counts.
    """
    counts: list[OutcomeReasonCount] = collect_outcome_reason_counts(view_results)

    headers: list[str] = ["Outcome", "Reason", "Count"]
    rows: list[list[str]] = []
    for row in counts:
        rows.append([row.outcome.value, row.reason, str(row.count)])

    table: str = render_markdown_table(headers, rows, align={2: "right"}).rstrip()

    return "\n".join(
        [
            "## Summary by outcome",
            "",
            table,
            "",
            f"Total files: **{total}**",
        ]
    )


# ---- Public entry points ----


def render_pipeline_output_markdown(
    report: PipelineCommandHumanReport,
) -> str:
    """Render human-facing Markdown output for a pipeline command.

    Args:
        report: Prepared human report for the pipeline command.

    Returns:
        Rendered Markdown output.

    Raises:
        RuntimeError: If an invalid pipeline kind was selected.
    """
    make_message: Callable[[ProcessingContext, bool], str | None] | None = None
    if report.pipeline_kind == CliCmd.CHECK:
        make_message = _render_check_guidance_message_markdown
    elif report.pipeline_kind == CliCmd.STRIP:
        make_message = _render_strip_guidance_message_markdown
    else:
        # Defensive guard.
        raise RuntimeError(f"Invalid pipeline kind selected: {report.pipeline_kind}")

    parts: list[str] = []

    # Markdown always starts with a document banner.
    parts.append(
        _render_pipeline_banner_markdown(
            cmd=report.cmd,
            n_files=report.file_list_total,
        )
    )
    parts.append("")

    # Summary mode (grouped by `(outcome, reason)`).
    if report.summary_mode:
        if report.show_diffs:
            parts.append(
                _render_pipeline_diffs_markdown(
                    results=report.view_results,
                )
            )
        parts.append(
            _render_summary_counts_markdown(
                view_results=report.view_results,
                total=report.file_list_total,
            )
        )
    else:
        # Per-file guidance
        parts.append(
            _render_per_file_guidance_markdown(
                view_results=report.view_results,
                make_message=make_message,
                apply_changes=report.apply_changes,
                show_diffs=report.show_diffs,
            ),
        )

    # In actionable mode, unsupported files are hidden from the per-file listing but summarized
    # for visibility.
    if (
        (not report.summary_mode)
        and (report.report_scope == ReportScope.ACTIONABLE)
        and (report.unsupported_count > 0)
    ):
        parts.append(
            f"\n> ⚠️ Unsupported: {report.unsupported_count} file(s) "
            f"(use {CliOpt.REPORT}={ReportScope.NONCOMPLIANT.value} to list)\n"
        )

    return "\n".join(parts)


def render_pipeline_apply_summary_markdown(
    *,
    command_path: str,
    written: int,
    failed: int,
) -> str:
    """Render the apply-summary footer for Markdown output.

    Args:
        command_path: Command path, such as `topmark check`.
        written: Number of files written.
        failed: Number of files that failed to write.

    Returns:
        Rendered Markdown footer.
    """
    parts: list[str] = []
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
