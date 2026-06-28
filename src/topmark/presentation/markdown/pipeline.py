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
    - TEXT pipeline output is implemented in
      [`topmark.presentation.text.pipeline`][topmark.presentation.text.pipeline].
    - Machine-readable output is handled via domain machine serializers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.errors import TopmarkCliPipelineError
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.logging import get_logger
from topmark.pipeline.outcomes import ResultActionIntent
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.pipeline.outcomes import determine_result_action_intent
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import WriteStatus
from topmark.presentation.formatters.unified_diff import format_patch_plain
from topmark.presentation.markdown.diagnostic import render_diagnostics_markdown
from topmark.presentation.markdown.paths import render_path_display_markdown
from topmark.presentation.markdown.utils import markdown_code_span
from topmark.presentation.markdown.utils import render_fenced_code_block_markdown
from topmark.presentation.markdown.utils import render_markdown_table
from topmark.presentation.shared.paths import get_display_path
from topmark.presentation.shared.pipeline import summarize_pipeline_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.outcomes import OutcomeReasonCount
    from topmark.pipeline.result import ProcessingResult
    from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
    from topmark.presentation.shared.pipeline import PipelineFileSummary


logger: TopmarkLogger = get_logger(__name__)

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
    pipeline_kind: PipelineKindLiteral,
    n_files: int,
) -> str:
    """Render the Markdown banner for a pipeline command.

    Args:
        pipeline_kind: Pipeline kind (`check`, `strip`, `probe`).
        n_files: Number of pipeline result entries before view filtering.

    Returns:
        Markdown banner shown before pipeline command output.
    """
    return "\n".join(
        [
            f"# TopMark {pipeline_kind} Results",
            "",
            f"Processing **{n_files}** file(s).",
        ]
    )


# ---- Command guidance rendering ----


def _render_apply_command_markdown(
    *,
    command: str,
    result: ProcessingResult,
) -> str:
    """Render the suggested apply command for Markdown guidance.

    The command uses the shared human-facing display-path policy so STDIN-backed
    content is represented by its logical `--stdin-filename` value while regular
    file processing uses the normal display path. The returned command is plain
    text; callers are responsible for Markdown escaping.

    Args:
        command: TopMark subcommand name.
        result: Durable processing result for the file.

    Returns:
        Suggested apply command for Markdown guidance output.
    """
    path_name: str = get_display_path(result)
    if result.from_stdin:
        return f"topmark {command} {CliOpt.APPLY_CHANGES} {CliOpt.STDIN_FILENAME} {path_name} -"
    return f"topmark {command} {CliOpt.APPLY_CHANGES} {path_name}"


def _render_check_guidance_message_markdown(
    result: ProcessingResult,
) -> str | None:
    """Render per-file guidance for `topmark check` results.

    Args:
        result: Durable processing result for the file.

    Returns:
        Guidance message for this file, or `None` when no check action is relevant.

    Raises:
        TopmarkCliPipelineError: If the resolved intent is invalid for the `check`
            pipeline.
    """
    if not result.outcome.effective_would_add_or_update:
        return None

    apply_changes: bool | None = result.execution_mode.apply_changes

    path_label: str = render_path_display_markdown(result)
    intent: ResultActionIntent = determine_result_action_intent(result)

    if apply_changes:
        if result.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {result.status.write.value}"
        if result.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_add_or_update is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return (
            f"➕ Adding header in {path_label}"
            if result.status.header == HeaderStatus.MISSING
            else f"✏️  Updating header in {path_label}"
        )

    apply_cmd: str = _render_apply_command_markdown(command=CliCmd.CHECK, result=result)

    if intent == ResultActionIntent.INSERT:
        action: str = "add a TopMark header to this file"
    elif intent == ResultActionIntent.UPDATE:
        action = "update the TopMark header in this file"
    else:
        raise TopmarkCliPipelineError(
            message=f"Unexpected intent {intent.value} in 'check' pipeline.",
        )
    cmd_md: str = markdown_code_span(apply_cmd)
    return f"🛠️  Run {cmd_md} to {action}."


def _render_strip_guidance_message_markdown(
    result: ProcessingResult,
) -> str | None:
    """Render per-file guidance for `topmark strip` results.

    Args:
        result: Durable processing result for the file.

    Returns:
        Guidance message for this file, or `None` when no strip action is relevant.

    Raises:
        TopmarkCliPipelineError: If the resolved intent is invalid for the `strip`
            pipeline.
    """
    if not result.outcome.effective_would_strip:
        return None

    apply_changes: bool | None = result.execution_mode.apply_changes

    path_label: str = render_path_display_markdown(result)
    intent: ResultActionIntent = determine_result_action_intent(result)

    if apply_changes:
        if result.status.write == WriteStatus.FAILED:
            return f"❌ Could not {intent.value} header: {result.status.write.value}"
        if result.status.write == WriteStatus.SKIPPED:
            # Defensive: should not happen when effective_would_strip is True,
            # but keeps CLI honest if a later step halts.
            return f"⚠️  Could not {intent.value} header (write skipped)."

        return f"🧹 Stripping header in {path_label}"

    apply_cmd: str = _render_apply_command_markdown(command=CliCmd.STRIP, result=result)

    if intent == ResultActionIntent.STRIP:
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
    result: ProcessingResult,
) -> str:
    """Render a concise one-line Markdown summary for one file.

    The summary is driven by [`map_bucket()`][topmark.pipeline.outcomes.map_bucket]
    and may append compact write, diff, or diagnostic hints.

    Args:
        result: Durable processing result containing status and display data.

    Returns:
        One-line Markdown summary for the file.
    """
    summary: PipelineFileSummary = summarize_pipeline_file(result)
    suffix: str = " - " + " - ".join(summary.secondary_parts) if summary.secondary_parts else ""

    if summary.file_type_label is not None:
        return (
            f"`{get_display_path(result)}` ({summary.file_type_label}) - "
            f"`{summary.key}`: {summary.label}{suffix}"
        )
    return f"`{get_display_path(result)}` - `{summary.key}`: {summary.label}{suffix}"


def _render_per_file_guidance_markdown(
    *,
    results: Sequence[ProcessingResult],
    make_message: Callable[[ProcessingResult], str | None],
    show_diffs: bool,
) -> str:
    """Render per-file Markdown sections.

    For each file, this includes:
        1. A summary line.
        2. An optional guidance message.
        3. Diagnostics when present.
        4. Diagnostic hints when present.
        5. An optional diff block.

    Unlike TEXT output, Markdown always renders available diagnostics and hints.

    Args:
        results: Durable processing results to render.
        make_message: Per-file guidance message builder.
        show_diffs: Whether to include unified diffs.

    Returns:
        Markdown fragment containing all rendered file sections.
    """
    blocks: list[str] = []

    if not results:
        return ""

    blocks.append("## Files")
    blocks.append("")

    for idx, result in enumerate(results, start=1):
        # 1. summary line.
        blocks.append(
            f"{idx}. "
            + _render_file_summary_line_markdown(
                result=result,
            )
        )

        # 2. guidance message for actionable check/strip outcomes.
        msg: str | None = make_message(result)
        if msg:
            blocks.append(f"  - {msg}")

        # 3. diagnostics block; Markdown shows diagnostics whenever present.
        if result.diagnostics:
            diag_md: str = render_diagnostics_markdown(
                diagnostics=result.diagnostics,
            ).rstrip()
            # Triage summary is nonempty if there are diagnostics:
            for line in diag_md.splitlines():
                blocks.append(f"  {line}" if line else "")

        # 4. hints; Markdown shows all hints whenever present.
        hints: list[Hint] = list(result.hints)
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
            patch: str | None = _render_diff_markdown(
                result.detail.diff_text,
            )

            if patch:
                blocks.append("")
                blocks.append(
                    render_fenced_code_block_markdown(
                        text=patch.rstrip("\n"),
                        language="diff",
                    )
                )

        blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


# ---- Diff rendering ----


def _render_diff_markdown(
    diff_text: str | None,
    *,
    show_line_numbers: bool = False,
) -> str | None:
    """Render a unified diff as plain Markdown-friendly text.

    Args:
        diff_text: Durable unified diff text to render.
        show_line_numbers: Whether to prepend line numbers.

    Returns:
        Rendered diff text, or `None` when no diff is available.
    """
    logger.debug("diff_text: %r", diff_text)
    if diff_text is None:
        return None

    if diff_text:
        patch: str = format_patch_plain(
            patch=diff_text,
            show_line_numbers=show_line_numbers,
        )

        return patch

    return None


def _render_pipeline_diffs_markdown(
    *,
    results: Sequence[ProcessingResult],
    show_line_numbers: bool = False,
) -> str:
    """Render a Markdown diff section for all files with diffs.

    Args:
        results: Durable processing results to inspect.
        show_line_numbers: Whether to prepend line numbers.

    Returns:
        Markdown diff section.
    """
    diff_blocks: list[str] = []
    for result in results:
        patch: str | None = _render_diff_markdown(
            result.detail.diff_text,
            show_line_numbers=show_line_numbers,
        )

        if patch:
            diff_blocks.append(f"### {render_path_display_markdown(result)}")
            diff_blocks.append("")
            diff_blocks.append(
                render_fenced_code_block_markdown(
                    text=patch.rstrip("\n"),
                    language="diff",
                )
            )
            diff_blocks.append("")

    if not diff_blocks:
        return ""

    # Keep Markdown diffs readable and copyable.
    blocks: list[str] = ["## Diffs", ""]
    blocks.extend(diff_blocks)
    blocks.append("")
    return "\n".join(blocks).rstrip()


def render_pipeline_diffs_markdown(
    *,
    results: Sequence[ProcessingResult],
    show_line_numbers: bool = False,
) -> str:
    """Render standalone Markdown diff output for a pipeline command.

    This output is separate from the human per-file report. Commands use it for
    `--diff` stdout payloads while routing guidance and summaries through the
    regular human report path.

    Args:
        results: Durable processing results to inspect for retained diffs.
        show_line_numbers: Whether to prepend line numbers.

    Returns:
        Markdown diff output, or an empty string when no diff is available.
    """
    return _render_pipeline_diffs_markdown(
        results=results,
        show_line_numbers=show_line_numbers,
    )


# ---- Summary rendering ----


def _render_summary_counts_markdown(
    *,
    view_results: Sequence[ProcessingResult],
    total: int,
) -> str:
    """Render summary counts grouped by `(outcome, reason)` as a Markdown table.

    Args:
        view_results: Durable processing results included in the rendered view.
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
    make_message: Callable[[ProcessingResult], str | None] | None = None
    if report.pipeline_kind == "check":
        make_message = _render_check_guidance_message_markdown
    elif report.pipeline_kind == "strip":
        make_message = _render_strip_guidance_message_markdown
    else:
        # Defensive guard.
        raise RuntimeError(f"Invalid pipeline kind selected: {report.pipeline_kind}")

    parts: list[str] = []

    # Markdown always starts with a document banner.
    parts.append(
        _render_pipeline_banner_markdown(
            pipeline_kind=report.pipeline_kind,
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
                results=report.view_results,
                make_message=make_message,
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
