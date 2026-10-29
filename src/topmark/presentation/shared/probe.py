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

from topmark.config.assignments import AssignmentRule
from topmark.config.assignments import FileTypeRule
from topmark.utils.path import format_config_source_path

if TYPE_CHECKING:
    from topmark.pipeline.result import ProbeCandidateSnapshot
    from topmark.pipeline.result import ProbeMatchSnapshot
    from topmark.pipeline.result import ProbeSnapshot


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


def format_probe_rule_details(
    probe: ProbeSnapshot,
    *,
    include_superseded: bool,
) -> list[str]:
    """Explain the winning rule and optionally its superseded matches.

    Keep a concise winning-rule explanation available at every detail level.
    Callers can include earlier actual matches in precedence order.

    Args:
        probe: Durable resolution snapshot.
        include_superseded: Whether to include superseded rules.

    Returns:
        Plain text explanations suitable for human output.
    """
    matches: tuple[tuple[FileTypeRule, str], ...] = (
        probe.rule_matches if include_superseded else probe.rule_matches[-1:]
    )
    lines: list[str] = []
    for rule, pattern in matches:
        winner: bool = (rule, pattern) == probe.rule_matches[-1]
        target: str = rule.file_type if isinstance(rule, AssignmentRule) else "automatic inference"
        lines.append(
            f"{'winning' if winner else 'superseded'} {rule.action}: {target}; "
            f"pattern={pattern!r}; source={format_config_source_path(rule.source)}; "
            f"base={rule.base.as_posix()}; "
            f"scope={rule.scope.as_posix() if rule.scope else '<global>'}; "
            f"precedence={rule.precedence}; order={rule.order}"
        )
    return lines
