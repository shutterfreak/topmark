# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI utility helpers for TopMark.

This module provides utility functions shared across CLI commands, including
header defaults extraction, color handling, and summary rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Sequence

from topmark.api.view import collect_outcome_counts
from topmark.cli.console_helpers import get_console_safely
from topmark.cli_shared.console_api import ConsoleLike
from topmark.cli_shared.utils import OutputFormat
from topmark.config.logging import get_logger
from topmark.pipeline.hints import Cluster
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from collections.abc import Callable

    import click

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.views import DiffView, UpdatedView


logger: TopmarkLogger = get_logger(__name__)


def render_summary_counts(view_results: list[ProcessingContext], *, total: int) -> None:
    """Print the human summary (aligned counts by outcome)."""
    console: ConsoleLike = get_console_safely()
    console.print()
    console.print(console.styled("Summary by outcome:", bold=True, underline=True))

    counts: dict[str, tuple[int, str, Callable[[str], str]]] = collect_outcome_counts(view_results)
    label_width: int = max((len(v[1]) for v in counts.values()), default=0) + 1
    num_width: int = len(str(total))
    for _key, (n, label, color) in counts.items():
        console.print(color(f"  {label:<{label_width}}: {n:>{num_width}}"))


def render_per_file_guidance(
    view_results: list[ProcessingContext],
    *,
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
) -> None:
    """Echo one human guidance line per result (when not in --summary)."""
    console: ConsoleLike = get_console_safely()
    for r in view_results:
        console.print(r.summary)
        msg: str | None = make_message(r, apply_changes)
        if msg:
            console.print(console.styled(f"   {msg}", fg="yellow"))

        verbosity: int = r.config.verbosity_level or 0

        if verbosity > 0 and r.reason_hints:
            console.print(
                console.styled(
                    "  Hints (newest first):",
                    fg="white",
                    italic=True,
                    bold=True,
                )
            )
            for h in reversed(r.reason_hints):
                if h.cluster == Cluster.UNCHANGED.value:
                    color: str = "green"
                elif h.cluster in {Cluster.CHANGED.value, Cluster.WOULD_CHANGE.value}:
                    color = "bright_yellow"
                elif h.cluster in {Cluster.BLOCKED_POLICY.value, Cluster.SKIPPED.value}:
                    color = "bright_blue"
                elif h.cluster == Cluster.ERROR.value:
                    color = "bright_red"
                else:
                    color = "white"

                # Summary line
                summary: str = (
                    f"     {h.axis.value:10s}: {h.cluster:10s} - {h.code:16s}: "
                    f"{h.message}{' (terminal)' if h.terminal else ''}"
                )
                console.print(
                    console.styled(
                        summary,
                        fg=color,
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
                                    fg=color,
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


def emit_diffs(results: list[ProcessingContext], *, diff: bool, command: click.Command) -> None:
    """Print unified diffs for changed files in human output mode.

    Args:
      results (list[ProcessingContext]): List of processing contexts to inspect.
      diff (bool): If True, print unified diffs; if False, do nothing.
      command (click.Command): The Click command object (used for structured logging).

    Notes:
      - Diffs are only printed in human (DEFAULT) output mode.
      - Files with no changes do not emit a diff.
    """
    console: ConsoleLike = get_console_safely()
    for r in results:
        if diff:
            diff_view: DiffView | None = r.views.diff
            diff_text: str | None = diff_view.text if diff_view else None
            if diff_text:
                console.print(render_patch(diff_text))


def emit_machine_output(
    view_results: list[ProcessingContext], fmt: OutputFormat, summary_mode: bool
) -> None:
    """Emit JSON/NDJSON for machine consumption.

    Args:
      view_results (list[ProcessingContext]): Ordered list of per-file processing results.
      fmt (OutputFormat): Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).
      summary_mode (bool): If True, emit aggregated counts instead of per-file entries.

    Notes:
      - This function never prints ANSI color or diffs.
      - For NDJSON summary, one object per line is emitted.
    """
    import json as _json

    console: ConsoleLike = get_console_safely()
    if fmt == OutputFormat.NDJSON:
        if summary_mode:
            counts: dict[str, tuple[int, str, Callable[[str], str]]] = collect_outcome_counts(
                view_results
            )
            for key, (n, label, _color) in counts.items():
                console.print(_json.dumps({"key": key, "count": n, "label": label}))
        else:
            for r in view_results:
                console.print(_json.dumps(r.to_dict()))
    elif fmt == OutputFormat.JSON:
        if summary_mode:
            counts = collect_outcome_counts(view_results)
            data: dict[str, dict[str, int | str]] = {
                k: {"count": n, "label": label} for k, (n, label, _color) in counts.items()
            }
            console.print(_json.dumps(data, indent=2))
        else:
            payload: list[dict[str, object]] = [r.to_dict() for r in view_results]
            console.print(_json.dumps(payload, indent=2))


def emit_updated_content_to_stdout(results: list[ProcessingContext]) -> None:
    """Write updated content to stdout when applying to a single STDIN file."""
    console: ConsoleLike = get_console_safely()
    for r in results:
        updated_view: UpdatedView | None = r.views.updated
        if updated_view:
            updated_file_lines: Sequence[str] | Iterable[str] | None = updated_view.lines
            if updated_file_lines is not None:
                console.print("".join(updated_file_lines), nl=False)


def render_banner(ctx: click.Context, *, n_files: int) -> None:
    """Render the initial banner for a command.

    Args:
      ctx (click.Context): Click context (used to get the command name).
      n_files (int): Number of files to be processed.
    """
    console: ConsoleLike = get_console_safely()
    console.print(console.styled(f"\n🔍 Processing {n_files} file(s):\n", fg="blue"))
    console.print(
        console.styled(f"📋 TopMark {ctx.command.name} Results:", bold=True, underline=True)
    )
