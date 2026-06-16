# topmark:header:start
#
#   project      : TopMark
#   file         : probe.py
#   file_relpath : src/topmark/presentation/text/probe.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT presentation for the `topmark probe` command.

This module renders resolution probe diagnostics for console-oriented TEXT output.
Unlike check/strip pipeline renderers, probe output is explanatory rather than
actionable: it reports resolution status, selected file type and processor,
scored candidates, and match signals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.presentation.shared.paths import get_display_path
from topmark.presentation.text.diagnostic import render_diagnostics_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.presentation.shared.pipeline import ProbeCommandHumanReport
    from topmark.resolution.probe import ResolutionProbeCandidate
    from topmark.resolution.probe import ResolutionProbeMatchSignals
    from topmark.resolution.probe import ResolutionProbeResult

# ---- Banner rendering ----


def _render_probe_banner_text(
    *,
    n_files: int,
    styled: bool,
) -> str:
    """Render the TEXT banner for probe diagnostics.

    Args:
        n_files: Number of probe result entries.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        TEXT banner shown before verbose probe output.
    """
    # The banner is only emitted for verbose TEXT output; the stylers still
    # respect the command's color policy.
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=styled)
    info_styler: TextStyler = style_for_role(StyleRole.INFO, styled=styled)

    return "\n".join(
        [
            heading_styler("📋 TopMark Resolution Probe Results"),
            "",
            info_styler(f"\n🔍 Probing {n_files} file(s):"),
        ]
    )


# ---- Probe rendering ----


def _render_probe_missing_text(
    *,
    ctx: ProcessingContext,
    styled: bool,
) -> str:
    """Render a probe line when no resolution probe result is available.

    Args:
        ctx: Processing context to render.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        Probe-specific TEXT line for a missing probe result.
    """
    warning_styler: TextStyler = style_for_role(StyleRole.WARNING, styled=styled)
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)
    return " ".join(
        [
            f"{get_display_path(ctx)}:",
            warning_styler("probe-missing"),
            "-",
            muted_styler("no resolution probe result was recorded"),
        ]
    )


def _render_probe_summary_line_text(
    *,
    ctx: ProcessingContext,
    probe: ResolutionProbeResult,
    styled: bool,
) -> str:
    """Render a compact one-line TEXT summary for one probe result.

    Args:
        ctx: Processing context containing the probe result.
        probe: Resolution probe result to render.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        One-line probe summary.
    """
    status_role: StyleRole = (
        StyleRole.UNCHANGED if probe.status.value == "resolved" else StyleRole.UNSUPPORTED
    )
    status_styler: TextStyler = style_for_role(status_role, styled=styled)
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)

    parts: list[str] = [f"{get_display_path(ctx)}:"]

    if probe.selected_file_type is None:
        label: str = "<filtered>" if probe.status.value == "filtered" else "<unknown>"
        parts.append(muted_styler(label))
        parts.append("-")
        parts.append(status_styler(f"{probe.status.value}: {probe.reason.value}"))
        return " ".join(parts)

    selected_file_type: str = probe.selected_file_type.local_key
    selected_processor: str = (
        probe.selected_processor.local_key if probe.selected_processor is not None else "<none>"
    )
    score_suffix: str = (
        f", score={probe.selected_file_type.score}"
        if probe.selected_file_type.score is not None
        else ""
    )

    parts.append(muted_styler(selected_file_type))
    parts.append("-")
    parts.append(
        status_styler(f"{probe.status.value}: processor={selected_processor}{score_suffix}")
    )

    return " ".join(parts)


def _render_probe_selected_details_text(
    *,
    probe: ResolutionProbeResult,
    styled: bool,
) -> list[str]:
    """Render selected probe details for verbose TEXT output.

    Args:
        probe: Resolution probe result to render.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        Detail lines for the selected probe outcome.
    """
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=styled)
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)

    lines: list[str] = [
        f"  status: {emphasis_styler(probe.status.value)}",
        f"  reason: {muted_styler(probe.reason.value)}",
        f"  candidates: {len(probe.candidates)}",
    ]

    if probe.selected_file_type is None:
        lines.append("  selected file type: <none>")
    else:
        score_suffix: str = (
            f" (score={probe.selected_file_type.score})"
            if probe.selected_file_type.score is not None
            else ""
        )
        lines.append(
            f"  selected file type: {probe.selected_file_type.qualified_key}{score_suffix}"
        )

    if probe.selected_processor is None:
        lines.append("  selected processor: <none>")
    else:
        lines.append(f"  selected processor: {probe.selected_processor.qualified_key}")

    return lines


def _format_probe_match_signals_text(candidate: ResolutionProbeCandidate) -> str:
    """Format candidate match signals as compact TEXT.

    Args:
        candidate: Probe candidate whose match signals should be rendered.

    Returns:
        Compact match-signal summary.
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
    return " ".join(parts)


def _render_probe_candidates_text(
    *,
    probe: ResolutionProbeResult,
    styled: bool,
) -> list[str]:
    """Render candidate details for high-verbosity probe TEXT output.

    Args:
        probe: Resolution probe result to render.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        Candidate detail lines.
    """
    if not probe.candidates:
        return []

    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=styled)
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=styled)
    selected_styler: TextStyler = style_for_role(StyleRole.UNCHANGED, styled=styled)

    lines: list[str] = ["  candidates:"]
    for candidate in probe.candidates:
        selected_suffix: str = " (selected)" if candidate.selected else ""
        candidate_label: str = (
            f"    {candidate.tie_break_rank}. {candidate.qualified_key} "
            f"score={candidate.score}{selected_suffix}"
        )
        lines.append(
            selected_styler(candidate_label)
            if candidate.selected
            else emphasis_styler(candidate_label)
        )
        lines.append(muted_styler(f"       match: {_format_probe_match_signals_text(candidate)}"))
    return lines


def _render_probe_results_text(
    *,
    view_results: Sequence[ProcessingContext],
    verbosity_level: int,
    styled: bool,
) -> str:
    """Render probe-specific per-file TEXT sections.

    At verbosity 0, each file is rendered as a compact one-line resolution
    summary. At verbosity 1, selected file type, processor, reason, and candidate
    count are included. At verbosity 2 and above, all scored candidates and match
    signals are rendered.

    Args:
        view_results: Processing contexts to render.
        verbosity_level: Effective TEXT verbosity level.
        styled: Whether ANSI-capable styling is enabled.

    Returns:
        TEXT fragment containing all rendered probe sections.
    """
    parts: list[str] = []

    for ctx in view_results:
        probe: ResolutionProbeResult | None = ctx.resolution_probe
        if probe is None:
            parts.append(
                _render_probe_missing_text(
                    ctx=ctx,
                    styled=styled,
                )
            )
        else:
            parts.append(
                _render_probe_summary_line_text(
                    ctx=ctx,
                    probe=probe,
                    styled=styled,
                )
            )

            if verbosity_level > 0:
                parts.extend(
                    _render_probe_selected_details_text(
                        probe=probe,
                        styled=styled,
                    )
                )

            if verbosity_level > 1:
                parts.extend(
                    _render_probe_candidates_text(
                        probe=probe,
                        styled=styled,
                    )
                )

        if verbosity_level > 0 and len(ctx.diagnostics) > 0:
            parts.append(
                render_diagnostics_text(
                    diagnostics=ctx.diagnostics,
                    verbosity_level=verbosity_level,
                    color=styled,
                )
            )

        parts.append("")

    return "\n".join(parts)


def render_probe_output_text(
    report: ProbeCommandHumanReport,
) -> str:
    """Render human-facing TEXT output for the probe command.

    Args:
        report: Prepared human report for the probe command.

    Returns:
        Rendered TEXT output for the prepared probe report.
    """
    parts: list[str] = []

    # TEXT banner is shown at -v and above.
    if report.verbosity_level > 0:
        parts.append(
            _render_probe_banner_text(
                n_files=report.file_list_total,
                styled=report.styled,
            )
        )
        parts.append("")

    # Probe-specific per-file resolution diagnostics.
    parts.append(
        _render_probe_results_text(
            view_results=report.view_results,
            verbosity_level=report.verbosity_level,
            styled=report.styled,
        )
    )

    return "\n".join(parts)
