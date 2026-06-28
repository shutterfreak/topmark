# topmark:header:start
#
#   project      : TopMark
#   file         : probe.py
#   file_relpath : src/topmark/presentation/shared/probe.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared probe presentation helpers.

This module contains Click-free formatting helpers shared by human-facing probe
renderers. The helpers intentionally return plain, presentation-neutral text so
format-specific renderers can apply Markdown escaping, code spans, or TEXT
styling at the boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.result import ProbeCandidateSnapshot
    from topmark.pipeline.result import ProbeMatchSnapshot


def format_probe_match_signals(
    candidate: ProbeCandidateSnapshot,
) -> str:
    """Format candidate match signals as compact plain text.

    Args:
        candidate: Probe candidate whose match signals should be rendered.

    Returns:
        Compact match-signal summary without format-specific escaping or styling.
    """
    match: ProbeMatchSnapshot = candidate.match
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
