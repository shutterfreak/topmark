# topmark:header:start
#
#   project      : TopMark
#   file         : probe.py
#   file_relpath : src/topmark/resolution/probe.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Probe result contracts for file type resolution diagnostics.

This module defines the immutable value objects returned by resolution probing.
The actual probing implementation lives in
[`topmark.resolution.filetypes`][topmark.resolution.filetypes] so it can reuse
the same private scoring helpers as effective file type resolution without
cross-module private imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ResolutionProbeStatus(str, Enum):
    """Machine-friendly status for the overall probe outcome."""

    RESOLVED = "resolved"
    UNSUPPORTED = "unsupported"
    NO_PROCESSOR = "no_processor"


class ResolutionProbeReason(str, Enum):
    """Machine-friendly reason explaining the probe outcome."""

    SELECTED_HIGHEST_SCORE = "selected_highest_score"
    SELECTED_BY_TIE_BREAK = "selected_by_tie_break"
    NO_CANDIDATES = "no_candidates"
    SELECTED_FILE_TYPE_HAS_NO_BOUND_PROCESSOR = "selected_file_type_has_no_bound_processor"


@dataclass(frozen=True, slots=True)
class ResolutionProbeMatchSignals:
    """Probe-visible match signals used while evaluating a file type candidate.

    Attributes:
        extension: Whether an extension rule matched the path basename.
        filename: Whether a filename or path-tail rule matched the path.
        pattern: Whether a regular-expression pattern matched the path basename.
        content_probe_allowed: Whether the file type content matcher was allowed to run.
        content_match: Whether the file type content matcher produced a positive match.
        content_error: Optional exception type name when content probing failed.
    """

    extension: bool
    filename: bool
    pattern: bool
    content_probe_allowed: bool
    content_match: bool
    content_error: str | None = None


@dataclass(frozen=True, slots=True)
class ResolutionProbeCandidate:
    """Probe-visible scored candidate considered by file type resolution.

    Attributes:
        qualified_key: Canonical namespace-qualified file type key.
        namespace: Candidate file type namespace.
        local_key: Candidate file type local key.
        score: Candidate precedence score used by the resolver; higher is better.
        selected: Whether this candidate is the effective winner.
        tie_break_rank: One-based deterministic rank after score and tie-break ordering.
        match: Probe-visible match signals for this candidate.
    """

    qualified_key: str
    namespace: str
    local_key: str
    score: int
    selected: bool
    tie_break_rank: int
    match: ResolutionProbeMatchSignals


@dataclass(frozen=True, slots=True)
class ResolutionProbeSelection:
    """Probe-visible selected file type or processor identity.

    Attributes:
        qualified_key: Canonical namespace-qualified key.
        namespace: Selected object namespace.
        local_key: Selected object local key.
        score: Selected file type score, or ``None`` for processor selections.
    """

    qualified_key: str
    namespace: str
    local_key: str
    score: int | None = None


@dataclass(frozen=True, slots=True)
class ResolutionProbeResult:
    """Probe result explaining file type and processor resolution for one path.

    Attributes:
        path: Filesystem path that was probed.
        status: Machine-friendly probe status.
        reason: Machine-friendly reason for the probe outcome.
        candidates: Scored file type candidates in deterministic resolution order.
        selected_file_type: Selected file type identity, or ``None`` when unsupported.
        selected_processor: Selected processor identity, or ``None`` when unsupported or unbound.
    """

    path: Path
    status: ResolutionProbeStatus
    reason: ResolutionProbeReason
    candidates: tuple[ResolutionProbeCandidate, ...]
    selected_file_type: ResolutionProbeSelection | None
    selected_processor: ResolutionProbeSelection | None
