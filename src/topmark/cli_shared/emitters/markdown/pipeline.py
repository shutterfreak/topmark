# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown pipeline rendering helpers for TopMark.

Click-free helpers that prepare Markdown for pipeline-oriented commands
(e.g. `check`, `strip`). Callers print the returned strings.

Notes:
    - TEXT (ANSI) output lives in
      [`topmark.cli.emitters.text.pipeline`][topmark.cli.emitters.text.pipeline].
    - Machine output is handled via domain machine serializers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.keys import CliShortOpt
from topmark.cli_shared.emitters.markdown.diagnostic import render_diagnostics_markdown
from topmark.cli_shared.emitters.markdown.utils import render_markdown_table
from topmark.pipeline.outcomes import OutcomeReasonCount
from topmark.pipeline.outcomes import ResultBucket
from topmark.pipeline.outcomes import collect_outcome_reason_counts
from topmark.pipeline.outcomes import map_bucket
from topmark.rendering.unified_diff import format_patch_plain

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.diagnostic.model import DiagnosticStats
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint

# Banner


def render_pipeline_banner_markdown(
    *,
    cmd: str,
    n_files: int,
) -> str:
    """Render the initial MarkDown banner for a pipeline command.

    Args:
      cmd: Command name.
      n_files: Number of files to be processed.

    Returns:
        The initial MarkDown banner for a pipeline command.
    """
    return "\n".join(
        [
            f"# TopMark {cmd} Results",
            "",
            f"Processing **{n_files}** file(s).",
        ]
    )


def render_pipeline_summary_counts_markdown(
    *,
    view_results: list[ProcessingContext],
    total: int,
) -> str:
    """Render summary counts grouped by `(outcome, reason)` as a Markdown table."""
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


def render_pipeline_per_file_guidance_markdown(
    *,
    view_results: list[ProcessingContext],
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    show_diffs: bool,
    verbosity_level: int,
) -> str:
    """Render per-file guidance in Markdown.

    The Markdown emitter mirrors the structure of the TEXT emitter:

    1. one summary line per file,
    2. optional guidance message,
    3. diagnostics block at verbosity >= 1,
    4. one hint at `-v`, or the full hint list at `-vv` and above,
    5. optional diff block.

    Args:
        view_results: Processing results to render.
        make_message: Optional per-file guidance message builder.
        apply_changes: Whether the command is in apply mode.
        show_diffs: Whether to include unified diffs.
        verbosity_level: Effective verbosity level controlling diagnostics and hint detail.

    Returns:
        Markdown fragment containing all per-file sections.
    """
    blocks: list[str] = []
    blocks.append("## Files")
    blocks.append("")

    for idx, r in enumerate(view_results, start=1):
        # At verbosity 0, keep output minimal: one summary line per file.
        #
        # 1. summary line
        blocks.append(
            f"{idx}. "
            + render_file_summary_line_markdown(
                ctx=r,
                verbosity_level=verbosity_level,
            )
        )

        # 2. guidance message (in case changes can be applied)
        msg: str | None = make_message(r, apply_changes)
        if msg:
            blocks.append(f"  - {msg}")

        # 3. diagnostics block (shown at verbosity >= 1)
        if verbosity_level > 0 and len(r.diagnostics) > 0:
            diag_md: str = render_diagnostics_markdown(
                diagnostics=r.diagnostics,
                verbosity_level=verbosity_level,
            ).rstrip()
            if diag_md:
                for line in diag_md.splitlines():
                    blocks.append(f"  {line}" if line else "")

        # 4. hints (one hint at `-v`, full list at `-vv` and above)
        hints: list[Hint] = r.diagnostic_hints.items
        hints_count: int = len(hints)
        if verbosity_level > 0 and hints_count > 0:
            extended_hint_info: str = (
                ""
                if verbosity_level > 1
                else f" (use `{CliShortOpt.VERBOSE}{CliShortOpt.VERBOSE[-1]}` to view all hints)"
            )
            blocks.append(f"  - Hints: {hints_count}{extended_hint_info}")

            # Only display the last hint when verbosity_level==1
            hints_to_show: list[Hint] = [hints[-1]] if verbosity_level == 1 else hints
            hints_to_show_count: int = len(hints_to_show)
            for idx, h in enumerate(hints_to_show, start=1):
                blocks.append(
                    render_hint_markdown(
                        hint=h,
                        last=idx == hints_to_show_count,
                        verbosity_level=verbosity_level,
                    )
                )

        # 5. optional diff block
        if show_diffs and r.views.diff and r.views.diff.text:
            diff_text: str = format_patch_plain(patch=r.views.diff.text).rstrip("\n")
            blocks.append("")
            blocks.append("```diff")
            blocks.append(diff_text)
            blocks.append("```")

        blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


def render_hint_markdown(
    hint: Hint,
    *,
    last: bool,
    verbosity_level: int,
) -> str:
    """Render a single hint as Markdown.

    Args:
        hint: The Hint object.
        last: Whether this is the last/decisive hint in the rendered subset.
        verbosity_level: Effective verbosity level.

    Returns:
        Markdown fragment for the hint (without trailing blank line).
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

    # Optional detail vs "use -vv" nudge
    if hint.detail:
        if verbosity_level > 1:
            for line in hint.detail.splitlines():
                lines.append(f"      {line}")
        else:
            lines.append(
                f"      (use `{CliShortOpt.VERBOSE}{CliShortOpt.VERBOSE[-1]}` "
                "to display detailed diagnostics)"
            )

    return "\n".join(lines)


def render_file_summary_line_markdown(
    *,
    ctx: ProcessingContext,
    verbosity_level: int,
) -> str:
    """Render a concise Markdown one-liner for a single file result.

    This helper mirrors `render_file_summary_line_text()` but emits plain
    Markdown rather than styled terminal text. The primary summary is driven by
    `map_bucket()`, and secondary suffixes summarize write status, diff presence,
    and compact diagnostic triage.

    Args:
        ctx: Processing context containing status and configuration.
        verbosity_level: Effective verbosity level. This only affects the
            inline diagnostic nudge such as ``"(use '-v' to view)"``.

    Returns:
        Human-readable Markdown one-line summary.
    """
    # File type, or <unknown> if resolution failed
    ft: str = ctx.file_type.name if ctx.file_type is not None else "<unknown>"

    # Resolve the public bucket for this context.
    apply_changes: bool = ctx.config.apply_changes is True
    bucket: ResultBucket = map_bucket(ctx, apply=apply_changes)
    key: str = bucket.outcome.value
    label: str = bucket.reason or "(no reason provided)"

    # Secondary hints: write status > diff marker > diagnostics
    parts: list[str] = []
    if ctx.status.has_write_outcome():
        parts.append(ctx.status.write.value)
    elif ctx.views.diff and ctx.views.diff.text:
        parts.append("diff")

    diag_show_hint: str = ""
    if ctx.diagnostics:
        # Compose a compact triage summary such as "1 error, 2 warnings".
        stats: DiagnosticStats = ctx.diagnostics.stats()
        triage_summary: str = stats.triage_summary()
        if triage_summary:
            parts.append(triage_summary)

        if verbosity_level <= 0 and stats.total > 0:
            diag_show_hint = f" (use `{CliShortOpt.VERBOSE}` to view)"

    suffix: str = (" — " + " - ".join(parts) + diag_show_hint) if parts else ""
    return f"`{ctx.path}` ({ft}) — `{key}`: {label}{suffix}"


def emit_pipeline_diffs_markdown(
    *,
    results: list[ProcessingContext],
    show_line_numbers: bool = False,
) -> str:
    """Print unified diffs for changed files (MarkDown format).

    Args:
        results: List of processing contexts to inspect.
        show_line_numbers: Prepend line numbers if True, render patch only (default).

    Returns:
        Unified diffs for all changed files.

    Notes:
        - Diffs are only printed in human (TEXT) output mode.
        - Files with no changes do not emit a diff.
    """
    # Keep Markdown diffs readable and copyable.
    blocks: list[str] = ["## Diffs", ""]
    for r in results:
        if r.views.diff and r.views.diff.text:
            diff_text: str = format_patch_plain(
                patch=r.views.diff.text,
                show_line_numbers=show_line_numbers,
            ).rstrip("\n")
            blocks.append(f"### `{r.path}`")
            blocks.append("")
            blocks.append("```diff")
            blocks.append(diff_text)
            blocks.append("```")
            blocks.append("")
    if len(blocks) > 2:
        blocks.append("")
    return "\n".join(blocks).rstrip()
