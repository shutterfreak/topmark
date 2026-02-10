# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/cli/emitters/default/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Default (ANSI) pipeline emitters for TopMark CLI.

This module contains Click-dependent / console-styled helpers used to *emit*
human-facing (DEFAULT) output for pipeline-oriented commands (e.g. `check`, `strip`).

Notes:
    - These helpers print to the active `ConsoleLike` obtained via
      [`get_console_safely()`][topmark.cli.console_helpers.get_console_safely].
    - Machine formats (JSON/NDJSON) are handled elsewhere.
    - Markdown output is implemented in the Click-free package
      [`topmark.cli_shared.emitters.markdown`][topmark.cli_shared.emitters.markdown].
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from yachalk import chalk

from topmark.cli.console_helpers import get_console_safely
from topmark.cli_shared.console_api import ConsoleLike
from topmark.cli_shared.outcomes import collect_outcome_counts_colored
from topmark.config.logging import get_logger
from topmark.core.enum_mixins import enum_from_name
from topmark.diagnostic.model import DiagnosticLevel, DiagnosticStats
from topmark.pipeline.hints import Cluster, Hint
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
    from topmark.core.presentation import Colorizer
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import DiffView, UpdatedView

logger: TopmarkLogger = get_logger(__name__)


def emit_banner(
    *,
    cmd: str,
    n_files: int,
) -> None:
    """Emit the initial banner for a pipeline command.

    Args:
      cmd: Command name.
      n_files: Number of files to be processed.
    """
    console: ConsoleLike = get_console_safely()
    console.print(console.styled(f"\n🔍 Processing {n_files} file(s):\n", fg="blue"))
    console.print(console.styled(f"📋 TopMark {cmd} Results:", bold=True, underline=True))


def render_file_summary_line(
    *,
    ctx: ProcessingContext,
    color: bool = True,
) -> str:
    """Return a concise, human-readable one-liner for this file.

    The summary is aligned with TopMark's pipeline phases and mirrors what
    comparable tools (e.g., *ruff*, *black*, *prettier*) surface: a clear
    primary outcome plus a few terse hints.

    Rendering rules:
        1. Primary bucket comes from the view-layer classification helper
            `map_bucket()` in [`topmark.pipeline.outcomes`][topmark.pipeline.outcomes].
            This ensures stable wording
            across commands and pipelines.
        2. If a write outcome is known (e.g., `PREVIEWED`, `WRITTEN`, `INSERTED`, `REMOVED`),
            append it as a trailing hint.
        3. If there is a diff but no write outcome (e.g., check/summary with
            `--diff`), append a "diff" hint.
        4. If diagnostics exist, append the diagnostic count as a hint.

    Verbose per-line diagnostics are emitted only when `Config.verbosity_level >= 1`
    (treats `None` as `0`).

    Examples (colors omitted here):
        path/to/file.py: python - would insert header - previewed
        path/to/file.py: python - up-to-date
        path/to/file.py: python - would strip header - diff - 2 issues

    Args:
        ctx: Processing context containing status and configuration.
        color: Render in color if `True`, else as plain text.

    Returns:
        Human-readable one-line summary, possibly followed by additional lines for
        verbose diagnostics depending on the configuration verbosity level.
    """
    verbosity_level: int = ctx.config.verbosity_level or 0

    parts: list[str] = [f"{ctx.path}:"]

    # File type (dim), or <unknown> if resolution failed
    if ctx.file_type is not None:
        parts.append(chalk.dim(ctx.file_type.name))
    else:
        parts.append(chalk.dim("<unknown>"))

    head: Hint | None = None
    if not ctx.diagnostic_hints:
        key: str = "no_hint"
        label: str = "No diagnostic hints"
    else:
        head = ctx.diagnostic_hints.headline()
        if head is None:
            key = "no_hint"
            label = "No diagnostic hints"
        else:
            key = head.code
            label = f"{head.axis.value.title()}: {head.message}"
            logger.debug("Key: '%s', label: '%s'", key, label)

    # Color choice can still be simple or based on cluster:
    cluster: str | None = head.cluster if head else None
    # head.cluster now carries the cluster value (e.g. "changed") but
    # enum_from_name(Cluster, cluster) looks up by enum name (e.g. "CHANGED").
    # Hence we use case insensitive lookup:
    cluster_elem: Cluster | None = enum_from_name(
        Cluster,
        cluster,
        case_insensitive=True,
    )
    color_fn: Colorizer = cluster_elem.color if cluster_elem else chalk.red.italic

    parts.append("-")
    parts.append(color_fn(f"{key}: {label}"))

    # Secondary hints: write status > diff marker > diagnostics

    if ctx.status.has_write_outcome():
        parts.append("-")
        parts.append(ctx.status.write.color(ctx.status.write.value))
    elif ctx.views.diff and ctx.views.diff.text:
        parts.append("-")
        parts.append(chalk.yellow("diff"))

    diag_show_hint: str = ""
    if ctx.diagnostics:
        stats: DiagnosticStats = ctx.diagnostics.stats()
        n_info: int = stats.n_info
        n_warn: int = stats.n_warning
        n_err: int = stats.n_error

        parts.append("-")
        # Compose a compact triage summary like "1 error, 2 warnings"
        triage: list[str] = []
        if verbosity_level <= 0:
            diag_show_hint = chalk.dim.italic(" (use '-v' to view)")
        if n_err:
            triage.append(chalk.red_bright(f"{n_err} error" + ("s" if n_err != 1 else "")))
        if n_warn:
            triage.append(chalk.yellow(f"{n_warn} warning" + ("s" if n_warn != 1 else "")))
        if n_info and not (n_err or n_warn):
            # Only show infos when there are no higher severities
            triage.append(chalk.blue(f"{n_info} info" + ("s" if n_info != 1 else "")))
        parts.append(", ".join(triage) if triage else chalk.blue("info"))

    result: str = " ".join(parts) + diag_show_hint

    # Optional verbose diagnostic listing (gated by verbosity level)
    if ctx.diagnostics and verbosity_level > 0:
        details: list[str] = []
        for d in ctx.diagnostics:
            prefix: str = {
                DiagnosticLevel.ERROR: chalk.red_bright("error"),
                DiagnosticLevel.WARNING: chalk.yellow("warning"),
                DiagnosticLevel.INFO: chalk.blue("info"),
            }[d.level]
            details.append(f"  [{prefix}] {d.message}")
        result += "\n" + "\n".join(details)

    return result


def emit_summary_counts(
    *,
    view_results: list[ProcessingContext],
    total: int,
) -> None:
    """Emit outcome counts summary (DEFAULT format)."""
    console: ConsoleLike = get_console_safely()
    console.print()
    console.print(console.styled("Summary by outcome:", bold=True, underline=True))

    counts = collect_outcome_counts_colored(view_results)
    label_width: int = max((len(v[1]) for v in counts.values()), default=0) + 1
    num_width: int = len(str(total))
    for _key, (n, label, color) in counts.items():
        console.print(color(f"  {label:<{label_width}}: {n:>{num_width}}"))


def emit_per_file_guidance(
    *,
    view_results: list[ProcessingContext],
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    show_diffs: bool,
) -> None:
    """Emit per-file detailed guidance (DEFAULT format)."""
    console: ConsoleLike = get_console_safely()
    line_width: Final[int] = console.get_line_width()

    # Use the Box Drawing Light Horizontal character (U+2500) for a solid line
    diff_start_fence: Final[str] = " diff - start ".center(line_width, "─")
    diff_end_fence: Final[str] = " diff - end ".center(line_width, "─")

    for r in view_results:
        console.print(render_file_summary_line(ctx=r))
        msg: str | None = make_message(r, apply_changes)
        if msg:
            console.print(console.styled(f"   {msg}", fg="yellow"))

        verbosity: int = r.config.verbosity_level or 0

        if verbosity > 0 and r.diagnostic_hints:
            console.print(
                console.styled(
                    "  Hints (newest first):",
                    fg="white",
                    italic=True,
                    bold=True,
                )
            )
            for h in reversed(r.diagnostic_hints.items):
                if h.cluster == Cluster.UNCHANGED.value:
                    fg: str = "green"
                elif h.cluster in {Cluster.CHANGED.value, Cluster.WOULD_CHANGE.value}:
                    fg = "bright_yellow"
                elif h.cluster in {Cluster.BLOCKED_POLICY.value, Cluster.SKIPPED.value}:
                    fg = "bright_blue"
                elif h.cluster == Cluster.ERROR.value:
                    fg = "bright_red"
                else:
                    fg = "white"

                # Summary line
                summary: str = (
                    f"     {h.axis.value:10s}: {h.cluster:10s} - {h.code:16s}: "
                    f"{h.message}{' (terminal)' if h.terminal else ''}"
                )
                console.print(
                    console.styled(
                        summary,
                        fg=fg,
                        italic=True,
                    )
                )

                # Optional detail vs "use -vv" nudge
                if h.detail:
                    if verbosity > 1:
                        for line in h.detail.splitlines():
                            console.print(
                                console.styled(
                                    f"         {line}",
                                    fg=fg,
                                    italic=True,
                                )
                            )
                    else:
                        console.print(
                            console.styled(
                                "         (use -vv to display detailed diagnostics)",
                                fg="white",
                                italic=True,
                            )
                        )

        # Optional diff
        if show_diffs:
            diff = render_diff(
                result=r,
                color=True,  # TODO: improve color handling in CLI
            )
            if diff:
                console.print(
                    console.styled(
                        f"\n{diff_start_fence}",
                        fg="white",
                        dim=True,
                    )
                )
                console.print(diff)
                console.print(
                    console.styled(
                        diff_end_fence,
                        fg="white",
                        dim=True,
                    )
                )

        # Separate records with blank line
        console.print()


def render_diff(
    *,
    result: ProcessingContext,
    color: bool,
    show_line_numbers: bool = False,
) -> str | None:
    """Render a unified diff (DEFAULT format).

    Args:
        result: List of processing contexts to inspect.
        color: Render in color if True, as plain text otherwise.
        show_line_numbers: Prepend line numbers if True, render patch only (default).

    Returns:
        The rendered diff or None if no changes / diff in view.

    Notes:
        - Diffs should only be printed in human (DEFAULT) output mode.
        - Files with no changes do not emit a diff.
    """
    diff_view: DiffView | None = result.views.diff
    diff_text: str | None = diff_view.text if diff_view else None
    if diff_text:
        return render_patch(
            patch=diff_text,
            color=color,
            show_line_numbers=show_line_numbers,
        )
    return None


def emit_diffs(
    *,
    results: list[ProcessingContext],
    color: bool,
    show_line_numbers: bool = False,
) -> None:
    """Print unified diffs for changed files (DEFAULT format).

    Args:
        results: List of processing contexts to inspect.
        color: Render in color if True, as plain text otherwise.
        show_line_numbers: Prepend line numbers if True, render patch only (default).

    Notes:
        - Diffs are only printed in human (DEFAULT) output mode.
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
        diff: str | None = render_diff(
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
