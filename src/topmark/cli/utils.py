# topmark:header:start
#
#   file         : utils.py
#   file_relpath : src/topmark/cli/utils.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI utility helpers for TopMark.

This module provides utility functions shared across CLI commands, including
header defaults extraction, color handling, and summary rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.console_helpers import get_console_safely
from topmark.cli_shared.utils import OutputFormat, count_by_outcome
from topmark.config.logging import get_logger
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from collections.abc import Callable

    import click

    from topmark.pipeline.context import ProcessingContext


logger = get_logger(__name__)


def render_summary_counts(view_results: list[ProcessingContext], *, total: int) -> None:
    """Print the human summary (aligned counts by outcome)."""
    console = get_console_safely()
    console.print()
    console.print(console.styled("Summary by outcome:", bold=True, underline=True))

    counts = count_by_outcome(view_results)
    label_width = max((len(v[1]) for v in counts.values()), default=0) + 1
    num_width = len(str(total))
    for _key, (n, label, color) in counts.items():
        console.print(color(f"  {label:<{label_width}}: {n:>{num_width}}"))


def render_per_file_guidance(
    view_results: list[ProcessingContext],
    *,
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
) -> None:
    """Echo one human guidance line per result (when not in --summary)."""
    console = get_console_safely()
    for r in view_results:
        console.print(r.summary)
        msg = make_message(r, apply_changes)
        if msg:
            console.print(console.styled(f"   {msg}", fg="yellow"))


def emit_diffs(results: list[ProcessingContext], *, diff: bool, command: click.Command) -> None:
    """Print unified diffs for changed files in human output mode.

    Args:
      results: List of processing contexts to inspect.
      diff: If True, print unified diffs; if False, do nothing.
      command: The Click command object (used for structured logging).

    Notes:
      - Diffs are only printed in human (DEFAULT) output mode.
      - Files with no changes do not emit a diff.
    """
    import pprint

    console = get_console_safely()
    logger.debug("topmark %s: diff: %s, entries: %d", command.name, diff, len(results))
    for r in results:
        logger.trace("topmark %s: diff: %s, result: %s", command.name, diff, pprint.pformat(r, 2))
        if diff and r.header_diff:
            console.print(render_patch(r.header_diff))


def emit_machine_output(
    view_results: list[ProcessingContext], fmt: OutputFormat, summary_mode: bool
) -> None:
    """Emit JSON/NDJSON for machine consumption.

    Args:
      view_results: Ordered list of per-file processing results.
      fmt: Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).
      summary_mode: If True, emit aggregated counts instead of per-file entries.

    Notes:
      - This function never prints ANSI color or diffs.
      - For NDJSON summary, one object per line is emitted.
    """
    import json as _json

    console = get_console_safely()
    if fmt == OutputFormat.NDJSON:
        if summary_mode:
            counts = count_by_outcome(view_results)
            for key, (n, label, _color) in counts.items():
                console.print(_json.dumps({"key": key, "count": n, "label": label}))
        else:
            for r in view_results:
                console.print(_json.dumps(r.to_dict()))
    elif fmt == OutputFormat.JSON:
        if summary_mode:
            counts = count_by_outcome(view_results)
            data = {k: {"count": n, "label": label} for k, (n, label, _color) in counts.items()}
            console.print(_json.dumps(data, indent=2))
        else:
            payload = [r.to_dict() for r in view_results]
            console.print(_json.dumps(payload, indent=2))


def emit_updated_content_to_stdout(results: list[ProcessingContext]) -> None:
    """Write updated content to stdout when applying to a single STDIN file."""
    console = get_console_safely()
    for r in results:
        if r.updated_file_lines is not None:
            console.print("".join(r.updated_file_lines), nl=False)


def render_banner(ctx: click.Context, *, n_files: int) -> None:
    """Render the initial banner for a command.

    Args:
      ctx: Click context (used to get the command name).
      n_files: Number of files to be processed.
    """
    console = get_console_safely()
    console.print(console.styled(f"\n🔍 Processing {n_files} file(s):\n", fg="blue"))
    console.print(
        console.styled(f"📋 TopMark {ctx.command.name} Results:", bold=True, underline=True)
    )
