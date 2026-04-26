# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/presentation/text/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT pipeline renderers for the TopMark CLI.

This module renders human-facing TEXT output for pipeline-oriented commands
such as `topmark check` and `topmark strip`.

TEXT output is console-oriented: it may use `verbosity_level` for progressive
disclosure, `styled` for ANSI-capable semantic styling, and compact hints that
refer to `-v` / `-vv`. Markdown and machine output are rendered by separate
presentation and machine-output layers.

Notes:
    - ANSI styling primitives (for example, conditional colorization) live in
      [`topmark.cli.presentation`][topmark.cli.presentation].
    - Markdown output is implemented in the Click-free package
      [`topmark.presentation.markdown`][topmark.presentation.markdown].
    - Machine output is handled via domain machine serializers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

from topmark.cli.console.utils import get_console_line_width
from topmark.cli.errors import TopmarkCliPipelineError
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.keys import CliShortOpt
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.cli.rendering.unified_diff import format_patch_styled
from topmark.core.presentation import StyleRole
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.hints import Cluster
from topmark.pipeline.outcomes import Intent
from topmark.pipeline.outcomes import ResultBucket
from topmark.pipeline.outcomes import determine_intent
from topmark.pipeline.outcomes import map_bucket
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus
from topmark.presentation.shared.outcomes import collect_outcome_counts_styled
from topmark.presentation.shared.outcomes import get_outcome_style_role
from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
from topmark.presentation.shared.pipeline import get_display_path
from topmark.presentation.text.diagnostic import render_diagnostics_text

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.diagnostic.model import DiagnosticStats
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.outcomes import OutcomeReasonCount
    from topmark.pipeline.views import DiffView


_HINT_CLUSTER_STYLE_ROLE: Final[dict[str, StyleRole]] = {
    Cluster.PENDING.value: StyleRole.PENDING,
    Cluster.UNCHANGED.value: StyleRole.UNCHANGED,
    Cluster.WOULD_CHANGE.value: StyleRole.WOULD_CHANGE,
    Cluster.CHANGED.value: StyleRole.CHANGED,
    Cluster.SKIPPED.value: StyleRole.SKIPPED,
    Cluster.UNSUPPORTED.value: StyleRole.UNSUPPORTED,
    Cluster.BLOCKED_POLICY.value: StyleRole.BLOCKED_POLICY,
    Cluster.ERROR.value: StyleRole.ERROR,
}


# ---- Path rendering ----


def _render_path_display_text(ctx: ProcessingContext) -> str:
    """Render a short TEXT path label for guidance messages.

    This helper formats
    [`get_display_path()`][topmark.presentation.shared.pipeline.get_display_path]
    for human-facing TEXT output and annotates STDIN-backed content with `(via STDIN)`
    when a synthetic filename is available.

    Args:
        ctx: Processing context containing the path to display.

    Returns:
        Short TEXT label for guidance messages.
    """
    path: str = get_display_path(ctx)
    if ctx.run_options.stdin_mode and bool(ctx.run_options.stdin_filename):
        return f"'{path}' (via STDIN)"

    return f"'{path}'"


# ---- Hint rendering ----


def _hint_styler(cluster: str | None, *, styled: bool) -> TextStyler:
    """Return the semantic text styler for a hint cluster.

    Args:
        cluster: Hint cluster name, if available.
        styled: Whether ANSI styling is enabled.

    Returns:
        Text styler for the hint cluster.
    """
    role: StyleRole = _HINT_CLUSTER_STYLE_ROLE.get(cluster or "", StyleRole.MUTED)
    return style_for_role(role, styled=styled)


def _render_hint_text(
    hint: Hint,
    *,
    last: bool,
    verbosity_level: int,
    styled: bool,
) -> str:
    """Render a single hint as TEXT output.

    Args:
        hint: Hint to render.
        last: Whether this is the last hint in the rendered subset.
        verbosity_level: Effective TEXT verbosity controlling detail rendering.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        Rendered text for one hint entry.
    """
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)
    hint_styler: TextStyler = _hint_styler(hint.cluster, styled=styled)

    lines: list[str] = []

    # Prepend a marker for terminal hints or the last (directive) hint
    marker: str = "⏹" if hint.terminal else ("▶" if last else "•")
    axis: str = hint.axis.value
    cluster: str = hint.cluster or ""
    code: str = hint.code
    message: str = hint.message
    terminal_suffix: str = " (terminal)" if hint.terminal else ""
    summary: str = (
        f"   {marker} {axis:10s}: {(cluster or ''):14s} - {code:20s}: {message}{terminal_suffix}"
    )
    lines.append(
        hint_styler(
            summary,
        )
    )

    # TEXT uses -vv as the progressive-disclosure threshold for hint details.
    if hint.detail:
        if verbosity_level > 1:
            for line in hint.detail.splitlines():
                lines.append(
                    hint_styler(
                        f"         {line}",
                    )
                )
        else:
            lines.append(
                muted_styler(
                    f"         (use '{CliShortOpt.VERBOSE}{CliShortOpt.VERBOSE[-1]}' "
                    "to display detailed hints)",
                )
            )

    return "\n".join(lines)


# ---- Banner rendering ----


def _render_pipeline_banner_text(
    *,
    cmd: str,
    n_files: int,
    styled: bool,
) -> str:
    """Render the TEXT banner for a pipeline command.

    Args:
        cmd: Command name.
        n_files: Number of candidate files.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        TEXT banner shown before the main pipeline output.
    """
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=styled)
    info_styler: TextStyler = style_for_role(StyleRole.INFO, styled=styled)

    return "\n".join(
        [
            heading_styler(f"📋 TopMark {cmd} Results"),
            "",
            info_styler(f"\n🔍 Processing {n_files} file(s):"),
        ]
    )


# ---- Command guidance rendering ----


def _render_check_guidance_message_text(
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

    path_label: str = _render_path_display_text(ctx)
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
            message=f"Unexpected intent {intent.value} in 'check' pipeline.",
        )
    return f"🛠️  Run `{apply_cmd}` to {action}."


def _render_strip_guidance_message_text(
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

    path_label: str = _render_path_display_text(ctx)
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
            f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} '{path_name}' -"
        )
    else:
        apply_cmd = f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} '{path_name}'"

    if intent == Intent.STRIP:
        action: str = "strip the TopMark header from this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in 'strip' pipeline.",
        )
    return f"🛠️  Run `{apply_cmd}` to {action}."


# ---- Per-file rendering ----


def _render_file_summary_line_text(
    *,
    ctx: ProcessingContext,
    verbosity_level: int,
    styled: bool = True,
) -> str:
    """Render a concise one-line TEXT summary for one file.

    The summary is driven by [`map_bucket()`][topmark.pipeline.outcomes.map_bucket]
    and may append compact write, diff, or diagnostic hints.

    Args:
        ctx: Processing context containing status and view data.
        verbosity_level: Effective TEXT verbosity for inline diagnostic nudges.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        One-line TEXT summary for the file.
    """
    parts: list[str] = [f"{get_display_path(ctx)}:"]  # TODO FIXME

    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)

    # File type (dim), or <unknown> if resolution failed
    parts.append(
        muted_styler(
            ctx.file_type.local_key if ctx.file_type is not None else "<unknown>",
        )
    )

    parts.append("-")

    # Resolve the public bucket for this context and style the summary from its
    # semantic outcome role.
    apply_changes: bool = ctx.run_options.apply_changes is True
    bucket: ResultBucket = map_bucket(ctx, apply=apply_changes)
    key: str = bucket.outcome.value
    label: str = bucket.reason or "(no reason provided)"

    # Retrieve the bucket's text styler based on the bucket outcome's semantic style role:
    outcome_styler: TextStyler = style_for_role(
        get_outcome_style_role(bucket.outcome),
        styled=styled,
    )

    parts.append(
        outcome_styler(
            f"{key}: {label}",
        )
    )

    # Secondary hints: write status > diff marker > diagnostics
    if ctx.status.has_write_outcome():
        parts.append("-")
        write_styler: TextStyler = style_for_role(
            ctx.status.write.role,
            styled=styled,
        )
        parts.append(
            write_styler(
                ctx.status.write.value,
            )
        )
    elif ctx.views.diff and ctx.views.diff.text:
        parts.append("-")
        diff_styler: TextStyler = style_for_role(
            StyleRole.WOULD_CHANGE,
            styled=styled,
        )
        parts.append(
            diff_styler(
                "diff",
            )
        )

    diag_show_hint: str = ""
    if ctx.diagnostics:
        # Compose a compact triage summary such as "1 error, 2 warnings".
        stats: DiagnosticStats = ctx.diagnostics.stats()
        triage_summary: str = stats.triage_summary()
        if triage_summary:
            parts.append("-")
            parts.append(triage_summary)

        if verbosity_level <= 0 and stats.total > 0:
            diag_show_hint = muted_styler(
                f" (use '{CliShortOpt.VERBOSE}' to view)",
            )

    result: str = " ".join(parts) + diag_show_hint
    return result


def _render_per_file_guidance_text(
    *,
    view_results: list[ProcessingContext],
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    show_diffs: bool,
    verbosity_level: int,
    styled: bool,
) -> str:
    """Render per-file TEXT sections.

    For each file, this includes:
        1. A summary line.
        2. An optional guidance message.
        3. Diagnostics at `-v` and above.
        4. One hint at `-v`, or all hints at `-vv` and above.
        5. An optional diff block.

    Args:
        view_results: Processing contexts to render.
        make_message: Per-file guidance message builder.
        apply_changes: Whether the command runs in apply mode.
        show_diffs: Whether to include unified diffs.
        verbosity_level: Effective TEXT verbosity level.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        TEXT fragment containing all rendered file sections.
    """
    line_width: Final[int] = get_console_line_width()

    parts: list[str] = []

    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=styled)

    # Use the Box Drawing Light Horizontal character (U+2500) for a solid line
    diff_start_fence: Final[str] = " diff - start ".center(line_width, "─")
    diff_end_fence: Final[str] = " diff - end ".center(line_width, "─")

    for ctx in view_results:
        # 1. summary line; at verbosity 0, keep output compact.
        parts.append(
            _render_file_summary_line_text(
                ctx=ctx,
                verbosity_level=verbosity_level,
            )
        )

        # 2. guidance message (in case changes can be applied)
        msg: str | None = make_message(ctx, apply_changes)
        if msg:
            parts.append(
                emphasis_styler(
                    f"  {msg}",
                )
            )

        # 3. diagnostics log (shown at -v and above)
        if verbosity_level > 0 and len(ctx.diagnostics) > 0:
            parts.append(
                render_diagnostics_text(
                    diagnostics=ctx.diagnostics,
                    verbosity_level=verbosity_level,
                    color=styled,
                )
            )

        # 4. hints (one hint at -v, full list at -vv and above)
        hints_count: int = len(ctx.diagnostic_hints)
        if verbosity_level > 0 and hints_count > 0:
            hints: list[Hint] = ctx.diagnostic_hints.items
            extended_hint_info: str = (
                ""
                if verbosity_level > 1
                else f" (use {CliShortOpt.VERBOSE}{CliShortOpt.VERBOSE[-1]} to view all hints)"
            )
            parts.append(
                emphasis_styler(
                    f"  Hints: {len(hints)}{extended_hint_info}",
                )
            )

            # Only display the last hint when verbosity_level==1
            hints_to_show: list[Hint] = [hints[-1]] if verbosity_level == 1 else hints
            hints_to_show_count: int = len(hints_to_show)
            for i, h in enumerate(hints_to_show, start=1):
                parts.append(
                    _render_hint_text(
                        h,
                        last=i == hints_to_show_count,
                        verbosity_level=verbosity_level,
                        styled=styled,
                    )
                )

        # 5. optional diff block
        if show_diffs:
            diff: str | None = _render_diff_text(
                ctx.views.diff,
                styled=styled,
            )
            if diff:
                parts.append("")
                parts.append(
                    muted_styler(
                        diff_start_fence,
                    )
                )
                parts.append(diff)
                parts.append(
                    muted_styler(
                        diff_end_fence,
                    )
                )

        # 6. blank line between file records
        parts.append("")

    return "\n".join(parts)


# ---- Diff rendering ----


def _render_diff_text(
    diff_view: DiffView | None,
    *,
    show_line_numbers: bool = False,
    styled: bool,
) -> str | None:
    """Render a unified diff as TEXT output.

    Args:
        diff_view: Diff view to render.
        show_line_numbers: Whether to prepend line numbers.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        Rendered diff text, or `None` when no diff is available.
    """
    if diff_view is None:
        return None
    diff_text: str | None = diff_view.text
    if diff_text:
        return format_patch_styled(
            patch=diff_text,
            color=styled,
            show_line_numbers=show_line_numbers,
        )
    return None


def _render_pipeline_diffs_text(
    *,
    results: list[ProcessingContext],
    show_line_numbers: bool = False,
    styled: bool,
) -> str:
    """Render a TEXT diff section for all files with diffs.

    Args:
        results: Processing contexts to inspect.
        show_line_numbers: Whether to prepend line numbers.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        TEXT diff section.
    """
    line_width: Final[int] = get_console_line_width()

    parts: list[str] = []

    # Use the Box Drawing Light Horizontal character (U+2500) for a solid line
    diffs_start_fence: Final[str] = " diffs - start ".center(line_width, "─")
    diffs_end_fence: Final[str] = " diffs - end ".center(line_width, "─")

    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    diff_fence_style: TextStyler = style_for_role(StyleRole.DIFF_LINE_NO, styled=styled)

    parts.append(
        diff_fence_style(
            f"{diffs_start_fence}",
        )
    )

    for ctx in results:
        diff: str | None = _render_diff_text(
            ctx.views.diff,
            styled=styled,
            show_line_numbers=show_line_numbers,
        )
        if diff:
            parts.append(diff)

    parts.append(
        diff_fence_style(
            diffs_end_fence,
        )
    )

    return "\n".join(parts)


# ---- Summary rendering ----


def _render_summary_counts_text(
    *,
    view_results: list[ProcessingContext],
    total: int,
    styled: bool,
) -> str:
    """Render summary counts grouped by `(outcome, reason)` as TEXT output.

    Args:
        view_results: Processing contexts included in the rendered view.
        total: Total number of candidate files before view filtering.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        TEXT summary grouped by outcome and reason.
    """
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=styled)
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=styled)
    italic_styler: TextStyler = style_for_role(StyleRole.ITALIC, styled=styled)

    parts: list[str] = []

    parts.append("")
    parts.append(heading_styler("Summary by outcome:"))

    counts: list[tuple[OutcomeReasonCount, Callable[[str], str]]] = collect_outcome_counts_styled(
        view_results
    )
    outcome_width: int = max(
        max((len(row.outcome.value) for row, _ in counts), default=0),
        len("TOTAL"),
    )
    reason_width: int = max((len(row.reason) for row, _ in counts), default=0)
    num_width: int = len(str(total))

    for row, color in counts:
        outcome_text: str = emphasis_styler(
            color(f"{row.outcome.value:<{outcome_width}}"),
        )
        reason_text: str = italic_styler(color(f"{row.reason:<{reason_width}}"))

        count_text: str = color(f"{row.count:>{num_width}}")

        parts.append(f"  {outcome_text}  {reason_text} : {count_text}")

    if counts:
        # Only render a horizontal line before the totals if there were outcome counts
        sep_width: int = 2 + outcome_width + 2 + reason_width + 3 + num_width
        parts.append("─" * sep_width)

    total_outcome: str = "TOTAL"
    total_reason: str = ""
    parts.append(
        emphasis_styler(
            f"  {total_outcome:<{outcome_width}}"
            f"  {total_reason:<{reason_width}} : {total:>{num_width}}",
        )
    )

    return "\n".join(parts)


# ---- Public entry points ----


def render_pipeline_output_text(
    report: PipelineCommandHumanReport,
) -> str:
    """Render human-facing TEXT output for a pipeline command.

    Args:
        report: Prepared human report for the pipeline command.

    Returns:
        Rendered TEXT output for the prepared pipeline report.

    Raises:
        RuntimeError: If an invalid pipeline kind was selected.
    """
    make_message: Callable[[ProcessingContext, bool], str | None] | None = None
    if report.pipeline_kind == CliCmd.CHECK:
        make_message = _render_check_guidance_message_text
    elif report.pipeline_kind == CliCmd.STRIP:
        make_message = _render_strip_guidance_message_text
    else:
        # Defensive guard.
        raise RuntimeError(f"Invalid pipeline kind selected: {report.pipeline_kind}")

    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    warning_styler: TextStyler = style_for_role(StyleRole.WARNING, styled=report.styled)

    parts: list[str] = []

    # TEXT banner is shown at -v and above.
    if report.verbosity_level > 0:
        parts.append(
            _render_pipeline_banner_text(
                cmd=report.cmd,
                n_files=report.file_list_total,
                styled=report.styled,
            )
        )

    # Summary mode (grouped by `(outcome, reason)`)
    if report.summary_mode:
        if report.show_diffs:
            parts.append(
                _render_pipeline_diffs_text(
                    results=report.view_results,
                    styled=report.styled,
                )
            )
        parts.append(
            _render_summary_counts_text(
                view_results=report.view_results,
                total=report.file_list_total,
                styled=report.styled,
            )
        )
    else:
        # Per-file guidance
        parts.append(
            _render_per_file_guidance_text(
                view_results=report.view_results,
                make_message=make_message,
                apply_changes=report.apply_changes,
                show_diffs=report.show_diffs,
                verbosity_level=report.verbosity_level,
                styled=report.styled,
            )
        )

    # In actionable mode, unsupported files are hidden from the per-file listing but summarized
    # for visibility.

    if (
        (not report.summary_mode)
        and (report.report_scope == ReportScope.ACTIONABLE)
        and (report.unsupported_count > 0)
    ):
        parts.append(
            warning_styler(
                f"⚠️  Unsupported: {report.unsupported_count} file(s) "
                f"(use {CliOpt.REPORT}={ReportScope.NONCOMPLIANT.value} to list)"
            )
        )

    return "\n".join(parts)


def render_pipeline_apply_summary_text(
    *,
    command_path: str,
    written: int,
    failed: int,
    styled: bool,
) -> str:
    """Render the apply-summary footer for TEXT output.

    Args:
        command_path: Command path, such as `topmark check`.
        written: Number of files written.
        failed: Number of files that failed to write.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        Rendered TEXT footer.
    """
    parts: list[str] = []
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    changed_styler: TextStyler = style_for_role(StyleRole.CHANGED, styled=styled)
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
