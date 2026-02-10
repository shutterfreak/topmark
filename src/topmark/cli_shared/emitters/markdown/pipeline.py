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
    - DEFAULT (ANSI) output lives in
      [`topmark.cli.emitters.default.pipeline`][topmark.cli.emitters.default.pipeline].
    - Machine output is handled via domain machine serializers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli_shared.emitters.markdown.utils import render_markdown_table
from topmark.cli_shared.outcomes import collect_outcome_counts
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.pipeline.context.model import ProcessingContext


def render_pipeline_banner_markdown(*, cmd: str, n_files: int) -> str:
    """Render a Markdown banner for a pipeline command."""
    return "\n".join(
        [
            f"# TopMark {cmd} Results",
            "",
            f"Processing **{n_files}** file(s).",
        ]
    )


def render_file_summary_line_markdown(*, ctx: ProcessingContext) -> str:
    """Render a concise Markdown one-liner for a single file result."""
    ft: str = ctx.file_type.name if ctx.file_type is not None else "<unknown>"

    if not ctx.diagnostic_hints:
        key = "no_hint"
        label = "No diagnostic hints"
    else:
        head = ctx.diagnostic_hints.headline()
        if head is None:
            key = "no_hint"
            label = "No diagnostic hints"
        else:
            key = head.code
            label = f"{head.axis.value.title()}: {head.message}"

    extras: list[str] = []
    if ctx.status.has_write_outcome():
        extras.append(ctx.status.write.value)
    elif ctx.views.diff and ctx.views.diff.text:
        extras.append("diff")

    if ctx.diagnostics:
        stats = ctx.diagnostics.stats()
        if stats.n_error:
            extras.append(f"{stats.n_error} error" + ("s" if stats.n_error != 1 else ""))
        if stats.n_warning:
            extras.append(f"{stats.n_warning} warning" + ("s" if stats.n_warning != 1 else ""))
        if stats.n_info and not (stats.n_error or stats.n_warning):
            extras.append(f"{stats.n_info} info" + ("s" if stats.n_info != 1 else ""))

    suffix = (" — " + ", ".join(extras)) if extras else ""
    return f"- `{ctx.path}` ({ft}) — `{key}`: {label}{suffix}"


def render_summary_counts_markdown(*, view_results: list[ProcessingContext], total: int) -> str:
    """Render outcome counts as a Markdown table."""
    counts = collect_outcome_counts(view_results)

    headers = ["Outcome", "Count"]
    rows: list[list[str]] = []
    for _key, (n, label) in counts.items():
        rows.append([label, str(n)])

    table = render_markdown_table(headers, rows, align={1: "right"}).rstrip()

    return "\n".join(
        [
            "## Summary by outcome",
            "",
            table,
            "",
            f"Total files: **{total}**",
        ]
    )


def render_per_file_guidance_markdown(
    *,
    view_results: list[ProcessingContext],
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    show_diffs: bool,
) -> str:
    """Render per-file guidance in Markdown."""
    blocks: list[str] = []
    blocks.append("## Files")
    blocks.append("")

    for r in view_results:
        blocks.append(render_file_summary_line_markdown(ctx=r))
        msg = make_message(r, apply_changes)
        if msg:
            blocks.append(f"  - {msg}")

        if show_diffs and r.views.diff and r.views.diff.text:
            diff_text = render_patch(patch=r.views.diff.text, color=False).rstrip("\n")
            blocks.append("")
            blocks.append("```diff")
            blocks.append(diff_text)
            blocks.append("```")

    return "\n".join(blocks).rstrip() + "\n"
