# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/cli/emitters/text/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Text (ANSI-capable) pipeline emitters for the TopMark CLI.

This module contains console-styled helpers used to *emit* human-facing TEXT output for
pipeline-oriented commands (for example, `check` and `strip`).

Notes:
    - These helpers print to the active `ConsoleLike` obtained via
      [`get_console_safely()`][topmark.cli.console_helpers.get_console_safely].
    - ANSI styling primitives (for example, conditional colorization) live in
      [`topmark.cli.presentation`][topmark.cli.presentation].
    - Machine formats (JSON/NDJSON) are handled elsewhere.
    - Markdown output is implemented in the Click-free package
      [`topmark.cli_shared.emitters.markdown`][topmark.cli_shared.emitters.markdown].
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

from topmark.cli.console_helpers import get_console_safely
from topmark.cli.emitters.text.diagnostic import render_diagnostics_text
from topmark.cli.keys import CliShortOpt
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import maybe_style
from topmark.cli.presentation import style_for_role
from topmark.cli.rendering.unified_diff import format_patch_styled
from topmark.cli_shared.console_api import ConsoleLike
from topmark.cli_shared.outcomes import collect_outcome_counts_styled
from topmark.cli_shared.outcomes import get_outcome_style_role
from topmark.core.presentation import StyleRole
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import Hint
from topmark.pipeline.outcomes import ResultBucket
from topmark.pipeline.outcomes import map_bucket

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Sequence

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.diagnostic.model import DiagnosticStats
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.outcomes import OutcomeReasonCount
    from topmark.pipeline.views import DiffView
    from topmark.pipeline.views import UpdatedView


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


def _hint_styler(cluster: str | None, *, styled: bool) -> TextStyler:
    """Return the semantic styler for a hint cluster."""
    role: StyleRole = _HINT_CLUSTER_STYLE_ROLE.get(cluster or "", StyleRole.MUTED)
    return style_for_role(role, styled=styled)


# Banner


def emit_pipeline_banner_text(
    *,
    cmd: str,
    n_files: int,
) -> None:
    """Emit the initial banner for a pipeline command (TEXT format).

    Args:
        cmd: Command name.
        n_files: Number of files to be processed.
    """
    console: ConsoleLike = get_console_safely()
    console.print(console.styled(f"\n🔍 Processing {n_files} file(s):\n", fg="blue"))
    console.print(console.styled(f"📋 TopMark {cmd} Results:", bold=True, underline=True))


def emit_pipeline_summary_counts_text(
    *,
    view_results: list[ProcessingContext],
    total: int,
) -> None:
    """Emit summary counts grouped by `(outcome, reason)` (TEXT format)."""
    console: ConsoleLike = get_console_safely()
    console.print()
    console.print(console.styled("Summary by outcome:", bold=True, underline=True))

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
        outcome_text: str = console.styled(
            color(f"{row.outcome.value:<{outcome_width}}"),
            bold=True,
        )
        reason_text: str = console.styled(
            color(f"{row.reason:<{reason_width}}"),
            italic=True,
        )
        count_text: str = console.styled(
            color(f"{row.count:>{num_width}}"),
        )
        console.print(f"  {outcome_text}  {reason_text} : {count_text}")

    if counts:
        # Only render a horizontal line before the totals if there were outcome counts
        sep_width: int = 2 + outcome_width + 2 + reason_width + 3 + num_width
        console.print("─" * sep_width)

    total_outcome: str = "TOTAL"
    total_reason: str = ""
    console.print(
        console.styled(
            f"  {total_outcome:<{outcome_width}}"
            f"  {total_reason:<{reason_width}} : {total:>{num_width}}",
            bold=True,
        )
    )


def emit_pipeline_per_file_guidance_text(
    *,
    view_results: list[ProcessingContext],
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    show_diffs: bool,
    verbosity_level: int,
    color: bool,
) -> None:
    """Emit per-file detailed guidance (TEXT format)."""
    console: ConsoleLike = get_console_safely()
    line_width: Final[int] = console.get_line_width()

    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=color)
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=color)

    # Use the Box Drawing Light Horizontal character (U+2500) for a solid line
    diff_start_fence: Final[str] = " diff - start ".center(line_width, "─")
    diff_end_fence: Final[str] = " diff - end ".center(line_width, "─")

    for r in view_results:
        # At verbosity 0, keep output minimal: one summary line per file.
        #
        # 1. summary line
        console.print(
            render_file_summary_line_text(
                ctx=r,
                verbosity_level=verbosity_level,
            )
        )

        # 2. guidance message (in case changes can be applied)
        msg: str | None = make_message(r, apply_changes)
        if msg:
            console.print(maybe_style(emphasis_styler, f"  {msg}", styled=color))

        # 3. diagnostics log (shown at verbosity >= 1)
        if verbosity_level > 0 and len(r.diagnostics) > 0:
            render_diagnostics_text(
                diagnostics=r.diagnostics,
                verbosity_level=verbosity_level,
                color=color,
            )

        # 4. hints (one hint at `-v`, full list at `-vv` and above)
        hints_count: int = len(r.diagnostic_hints)
        if verbosity_level > 0 and hints_count > 0:
            hints: list[Hint] = r.diagnostic_hints.items
            extended_hint_info: str = (
                ""
                if verbosity_level > 1
                else f" (use {CliShortOpt.VERBOSE}{CliShortOpt.VERBOSE[-1]} to view all hints)"
            )
            console.print(
                maybe_style(
                    emphasis_styler,
                    f"  Hints: {len(hints)}{extended_hint_info}",
                    styled=color,
                )
            )

            # Only display the last hint when verbosity_level==1
            hints_to_show: list[Hint] = [hints[-1]] if verbosity_level == 1 else hints
            hints_to_show_count: int = len(hints_to_show)
            for idx, h in enumerate(hints_to_show, start=1):
                console.print(
                    render_hint_text(
                        h,
                        last=idx == hints_to_show_count,
                        verbosity_level=verbosity_level,
                        color=color,
                    )
                )

        # 5. optional diff block
        if show_diffs:
            diff: str | None = render_diff_styled(
                result=r,
                color=True,  # TODO: improve color handling in CLI
            )
            if diff:
                console.print("")
                console.print(maybe_style(muted_styler, diff_start_fence, styled=color))
                console.print(diff)
                console.print(maybe_style(muted_styler, diff_end_fence, styled=color))

        # 6. blank line between file records
        console.print()


def render_hint_text(
    hint: Hint,
    *,
    last: bool,
    verbosity_level: int,
    color: bool,
) -> str:
    """Render a hint for human output formats.

    Args:
        hint: The Hint object.
        last: Whether this is the last/decisive hint in the rendered subset.
        verbosity_level: Effective verbosity level.
        color: Render in color if `True`, else as plain text.

    Returns:
        The rendered Hint.
    """
    lines: list[str] = []
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=color)
    hint_styler: TextStyler = _hint_styler(hint.cluster, styled=color)

    # Prepend a marker for terminal hints or the last (directive) hint
    marker: str = "⏹" if hint.terminal else ("▶" if last else "•")
    summary: str = (
        f"   {marker} {hint.axis.value:10s}: {(hint.cluster or ''):14s} - {hint.code:20s}: "
        f"{hint.message}{' (terminal)' if hint.terminal else ''}"
    )
    lines.append(maybe_style(hint_styler, summary, styled=color))

    # Optional detail vs "use -vv" nudge
    if hint.detail:
        if verbosity_level > 1:
            for line in hint.detail.splitlines():
                lines.append(
                    maybe_style(
                        hint_styler,
                        f"         {line}",
                        styled=color,
                    )
                )
        else:
            lines.append(
                maybe_style(
                    muted_styler,
                    f"         (use '{CliShortOpt.VERBOSE}{CliShortOpt.VERBOSE[-1]}' "
                    "to display detailed diagnostics)",
                    styled=color,
                )
            )

    return "\n".join(lines)


def render_file_summary_line_text(
    *,
    ctx: ProcessingContext,
    verbosity_level: int,
    color: bool = True,
) -> str:
    """Return a concise, human-readable one-line summary for this file.

    The summary is aligned with TopMark's public bucketing logic and mirrors
    the style of comparable tools (for example, *ruff*, *black*, and *prettier*):
    a clear primary outcome plus a few terse trailing hints.

    Rendering rules:
        1. The primary outcome comes from `map_bucket()` in
           [`topmark.pipeline.outcomes`][topmark.pipeline.outcomes].
        2. If a write outcome is known (for example, `WRITTEN`, `SKIPPED`, or
           `FAILED`), append it as a trailing hint.
        3. If there is a diff but no write outcome, append a `diff` hint.
        4. If diagnostics exist, append a compact triage suffix such as
           ``"1 error, 2 warnings"``.

    Example-style outputs (colors omitted here):
        path/to/file.py: python - would insert: header missing, changes found
        path/to/file.py: python - unchanged: up-to-date
        path/to/file.py: python - skipped: known file type, headers not supported - 1 info

    Args:
        ctx: Processing context containing status and configuration.
        verbosity_level: Effective verbosity level. This only affects the
            inline diagnostic nudge such as ``"(use '-v' to view)"``.
        color: Render in color if `True`, else as plain text.

    Returns:
        Human-readable one-line summary.
    """
    parts: list[str] = [f"{ctx.path}:"]

    # Prepare stylers for roles to avoid repeated calls
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=color)

    # File type (dim), or <unknown> if resolution failed
    parts.append(
        maybe_style(
            muted_styler,
            ctx.file_type.name if ctx.file_type is not None else "<unknown>",
            styled=color,
        )
    )

    parts.append("-")

    # Resolve the public bucket for this context and style the summary from its
    # semantic outcome role.
    apply_changes: bool = ctx.config.apply_changes is True
    bucket: ResultBucket = map_bucket(ctx, apply=apply_changes)
    key: str = bucket.outcome.value
    label: str = bucket.reason or "(no reason provided)"

    # Retrieve the bucket's text styler based on the bucket outcome's semantic style role:
    outcome_styler: TextStyler = style_for_role(
        get_outcome_style_role(bucket.outcome),
        styled=color,
    )

    parts.append(
        maybe_style(
            outcome_styler,
            f"{key}: {label}",
            styled=color,
        )
    )

    # Secondary hints: write status > diff marker > diagnostics
    if ctx.status.has_write_outcome():
        parts.append("-")
        write_styler: TextStyler = style_for_role(
            ctx.status.write.role,
            styled=color,
        )
        parts.append(
            maybe_style(
                write_styler,
                ctx.status.write.value,
                styled=color,
            )
        )
    elif ctx.views.diff and ctx.views.diff.text:
        parts.append("-")
        diff_styler: TextStyler = style_for_role(
            StyleRole.WOULD_CHANGE,
            styled=color,
        )
        parts.append(maybe_style(diff_styler, "diff", styled=color))

    diag_show_hint: str = ""
    if ctx.diagnostics:
        # Compose a compact triage summary such as "1 error, 2 warnings".
        stats: DiagnosticStats = ctx.diagnostics.stats()
        triage_summary: str = stats.triage_summary()
        if triage_summary:
            parts.append("-")
            parts.append(triage_summary)

        if verbosity_level <= 0 and stats.total > 0:
            diag_show_hint = maybe_style(
                muted_styler,
                f" (use '{CliShortOpt.VERBOSE}' to view)",
                styled=color,
            )

    result: str = " ".join(parts) + diag_show_hint
    return result


def render_diff_styled(
    *,
    result: ProcessingContext,
    show_line_numbers: bool = False,
    color: bool,
) -> str | None:
    """Render a unified diff (human formats).

    Args:
        result: List of processing contexts to inspect.
        show_line_numbers: Prepend line numbers if True, render patch only (default).
        color: Render in color if True, as plain text otherwise.

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
        return format_patch_styled(
            patch=diff_text,
            color=color,
            show_line_numbers=show_line_numbers,
        )
    return None


def emit_pipeline_diffs_text(
    *,
    results: list[ProcessingContext],
    show_line_numbers: bool = False,
    color: bool,
) -> None:
    """Print unified diffs for changed files (TEXT format).

    Args:
        results: List of processing contexts to inspect.
        show_line_numbers: Prepend line numbers if True, render patch only (default).
        color: Render in color if True, as plain text otherwise.

    Notes:
        - Diffs are only printed in human (TEXT) output mode.
        - Files with no changes do not emit a diff.
    """
    console: ConsoleLike = get_console_safely()
    line_width: Final[int] = console.get_line_width()

    # Use the Box Drawing Light Horizontal character (U+2500) for a solid line
    diffs_start_fence: Final[str] = " diffs - start ".center(line_width, "─")
    diffs_end_fence: Final[str] = " diffs - end ".center(line_width, "─")

    console.print(
        console.styled(
            f"{diffs_start_fence}",
            fg="white",
            dim=True,
        )
    )

    for r in results:
        diff: str | None = render_diff_styled(
            result=r,
            color=color,
            show_line_numbers=show_line_numbers,
        )
        if diff:
            console.print(diff)

    console.print(
        console.styled(
            diffs_end_fence,
            fg="white",
            dim=True,
        )
    )


def emit_updated_content_to_stdout(
    *,
    results: list[ProcessingContext],
) -> None:
    """Write updated content to stdout when applying to a single STDIN file.

    Args:
        results: the processing results.
    """
    console: ConsoleLike = get_console_safely()
    for r in results:
        updated_view: UpdatedView | None = r.views.updated
        if updated_view:
            updated_file_lines: Sequence[str] | Iterable[str] | None = updated_view.lines
            if updated_file_lines is not None:
                console.print("".join(updated_file_lines), nl=False)
