# topmark:header:start
#
#   project      : TopMark
#   file         : probe.py
#   file_relpath : src/topmark/presentation/markdown/probe.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown presentation for the `topmark probe` command.

This module renders resolution probe diagnostics as document-oriented Markdown.
Markdown probe output intentionally ignores TEXT-only verbosity and quiet controls
and always includes selected resolution details and candidate tables when
available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.presentation.markdown.diagnostic import render_diagnostics_markdown
from topmark.presentation.markdown.paths import render_path_display_markdown
from topmark.presentation.markdown.utils import markdown_code_span
from topmark.presentation.markdown.utils import render_markdown_table

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.presentation.shared.pipeline import ProbeCommandHumanReport
    from topmark.resolution.probe import ResolutionProbeCandidate
    from topmark.resolution.probe import ResolutionProbeMatchSignals
    from topmark.resolution.probe import ResolutionProbeResult


# ---- Banner rendering ----


def _render_probe_banner_markdown(
    *,
    n_files: int,
) -> str:
    """Render the Markdown banner for probe diagnostics.

    Args:
        n_files: Number of probe result entries.

    Returns:
        Markdown banner shown before the probe report.
    """
    return "\n".join(
        [
            "# TopMark Resolution Probe Results",
            "",
            f"Probing **{n_files}** file(s).",
        ]
    )


# ---- Probe rendering ----


def _render_probe_missing_markdown(ctx: ProcessingContext) -> str:
    """Render a probe section when no resolution probe result is available.

    Args:
        ctx: Processing context to render.

    Returns:
        Markdown fragment for a missing probe result.
    """
    path_label: str = render_path_display_markdown(ctx)
    return "\n".join(
        [
            f"### {path_label}",
            "",
            "- **Status:** `probe-missing`",
            "- **Reason:** no resolution probe result was recorded",
        ]
    )


def _render_probe_selected_details_markdown(probe: ResolutionProbeResult) -> list[str]:
    """Render selected probe details for Markdown output.

    Args:
        probe: Resolution probe result to render.

    Returns:
        Markdown lines for the selected probe outcome.
    """
    selected_file_type: str = (
        markdown_code_span(probe.selected_file_type.qualified_key)
        if probe.selected_file_type is not None
        else markdown_code_span("<none>")
    )
    selected_file_type_score: str = (
        f" (score={probe.selected_file_type.score})"
        if probe.selected_file_type is not None and probe.selected_file_type.score is not None
        else ""
    )
    selected_processor: str = (
        markdown_code_span(probe.selected_processor.qualified_key)
        if probe.selected_processor is not None
        else markdown_code_span("<none>")
    )

    return [
        f"- **Status:** `{probe.status.value}`",
        f"- **Reason:** `{probe.reason.value}`",
        f"- **Selected file type:** {selected_file_type}{selected_file_type_score}",
        f"- **Selected processor:** {selected_processor}",
        f"- **Candidates:** {len(probe.candidates)}",
    ]


def _render_probe_match_signals_markdown(candidate: ResolutionProbeCandidate) -> str:
    """Render candidate match signals as compact Markdown text.

    Args:
        candidate: Probe candidate whose match signals should be rendered.

    Returns:
        Compact Markdown-safe match signal summary.
    """
    match: ResolutionProbeMatchSignals = candidate.match
    parts: list[str] = [
        f"extension={str(match.extension).lower()}",
        f"filename={str(match.filename).lower()}",
        f"pattern={str(match.pattern).lower()}",
        f"content_probe={str(match.content_probe_allowed).lower()}",
        f"content_match={str(match.content_match).lower()}",
    ]
    if match.content_error is not None:
        parts.append(f"content_error={match.content_error}")
    return markdown_code_span(" ".join(parts))


def _render_probe_candidates_markdown(probe: ResolutionProbeResult) -> str:
    """Render candidate details for probe Markdown output.

    Args:
        probe: Resolution probe result whose candidates should be rendered.

    Returns:
        Markdown table for candidates, or an empty string when there are none.
    """
    if not probe.candidates:
        return ""

    rows: list[list[str]] = []
    for candidate in probe.candidates:
        rows.append(
            [
                str(candidate.tie_break_rank),
                markdown_code_span(candidate.qualified_key),
                str(candidate.score),
                "yes" if candidate.selected else "no",
                _render_probe_match_signals_markdown(candidate),
            ]
        )

    return render_markdown_table(
        ["Rank", "File Type", "Score", "Selected", "Match Signals"],
        rows,
        align={0: "right", 2: "right"},
    ).rstrip()


def _render_probe_result_markdown(ctx: ProcessingContext, probe: ResolutionProbeResult) -> str:
    """Render one resolution probe result as Markdown.

    Args:
        ctx: Processing context containing the probe result.
        probe: Resolution probe result to render.

    Returns:
        Markdown fragment for one probed file.
    """
    path_label: str = render_path_display_markdown(ctx)
    lines: list[str] = [
        f"### {path_label}",
        "",
    ]
    lines.extend(_render_probe_selected_details_markdown(probe))

    if len(ctx.diagnostics) > 0:
        diag_md: str = render_diagnostics_markdown(
            diagnostics=ctx.diagnostics,
        ).rstrip()
        if diag_md:
            lines.append("")
            lines.append("#### Diagnostics")
            lines.append("")
            lines.append(diag_md)

    candidate_table: str = _render_probe_candidates_markdown(probe)
    if candidate_table:
        lines.append("")
        lines.append("#### Candidates")
        lines.append("")
        lines.append(candidate_table)

    return "\n".join(lines)


def _render_probe_results_markdown(
    *,
    view_results: Sequence[ProcessingContext],
) -> str:
    """Render probe-specific per-file Markdown sections.

    Args:
        view_results: Processing contexts to render.

    Returns:
        Markdown fragment containing all rendered probe sections.
    """
    blocks: list[str] = ["## Files", ""]

    for ctx in view_results:
        probe: ResolutionProbeResult | None = ctx.resolution_probe
        if probe is None:
            blocks.append(_render_probe_missing_markdown(ctx))
        else:
            blocks.append(_render_probe_result_markdown(ctx, probe))
        blocks.append("")

    return "\n".join(blocks).rstrip() + "\n"


def render_probe_output_markdown(
    report: ProbeCommandHumanReport,
) -> str:
    """Render human-facing Markdown output for the probe command.

    Args:
        report: Prepared human report for the probe command.

    Returns:
        Rendered Markdown output for the prepared probe report.
    """
    parts: list[str] = []

    parts.append(
        _render_probe_banner_markdown(
            n_files=report.file_list_total,
        )
    )
    parts.append("")
    parts.append(
        _render_probe_results_markdown(
            view_results=report.view_results,
        )
    )

    return "\n".join(parts)
