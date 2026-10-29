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
from enum import StrEnum
from typing import TYPE_CHECKING

from topmark.config.assignments import FileTypeRuleAction

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.assignments import FileTypeRule
    from topmark.filetypes.model import FileTypeActivation


class FileTypeSelectionMethod(StrEnum):
    """Origin of the effective registered file-type selection."""

    ASSIGNMENT = "assignment"
    INFERENCE = "inference"


class ResolutionProbeStatus(StrEnum):
    """Machine-friendly status for the overall probe outcome.

    Attributes:
        FILTERED: Discovery or effective-type filters excluded this path.
        RESOLVED: A file type and processor were successfully selected.
        UNSUPPORTED: No file type candidates matched the path.
        NO_PROCESSOR: A file type was selected, but no processor was bound.
        ACTIVATION_BLOCKED: A selected file type is not currently authorized
            for processing.
    """

    FILTERED = "filtered"
    RESOLVED = "resolved"
    UNSUPPORTED = "unsupported"
    NO_PROCESSOR = "no_processor"
    ACTIVATION_BLOCKED = "activation_blocked"


class ResolutionProbeReason(StrEnum):
    """Machine-friendly reason explaining the probe outcome.

    Attributes:
        EXCLUDED_BY_PATH_FILTER: The path was filtered by path discovery filters.
        EXCLUDED_BY_FILE_TYPE_FILTER: The path was filtered by file-type filters.
        EXCLUDED_BY_DISCOVERY_FILTER: The path was filtered out before probing, but the exact
            discovery filter category was not identified.
        SELECTED_BY_ASSIGNMENT: An explicit rule selected the registered type.
        SELECTED_HIGHEST_SCORE: The selected file type had the highest score.
        SELECTED_BY_TIE_BREAK: Multiple candidates shared the top score and were
            ordered deterministically by tie-break rules.
        NO_CANDIDATES: No file type candidates matched the path.
        HARD_LINK_DUPLICATE: The path shares storage with another selected processing path.
        SELECTED_FILE_TYPE_HAS_NO_BOUND_PROCESSOR: The selected file type has no
            associated processor binding.
        SELECTED_FILE_TYPE_REQUIRES_OPT_IN: The selected file type requires
            explicit opt-in before it can be processed.
        SELECTED_FILE_TYPE_NEVER_PROCESSABLE: The selected file type is
            intentionally never processable.
    """

    EXCLUDED_BY_PATH_FILTER = "excluded_by_path_filter"
    EXCLUDED_BY_FILE_TYPE_FILTER = "excluded_by_file_type_filter"
    EXCLUDED_BY_DISCOVERY_FILTER = "excluded_by_discovery_filter"
    SELECTED_BY_ASSIGNMENT = "selected_by_assignment"
    SELECTED_HIGHEST_SCORE = "selected_highest_score"
    SELECTED_BY_TIE_BREAK = "selected_by_tie_break"
    NO_CANDIDATES = "no_candidates"
    HARD_LINK_DUPLICATE = "hard_link_duplicate"
    SELECTED_FILE_TYPE_HAS_NO_BOUND_PROCESSOR = "selected_file_type_has_no_bound_processor"
    SELECTED_FILE_TYPE_REQUIRES_OPT_IN = "selected_file_type_requires_opt_in"
    SELECTED_FILE_TYPE_NEVER_PROCESSABLE = "selected_file_type_never_processable"


@dataclass(frozen=True, kw_only=True, slots=True)
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


@dataclass(frozen=True, kw_only=True, slots=True)
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


@dataclass(frozen=True, kw_only=True, slots=True)
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


@dataclass(frozen=True, kw_only=True, slots=True)
class ResolutionProbeActivation:
    """Declared activation and dynamic authorization for the selected type."""

    declared: FileTypeActivation
    authorized: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class ResolutionProbeResult:
    """Probe result explaining file type and processor resolution for one path.

    Attributes:
        rule_matches: Ordered actual rule matches, with the winner last.
        path: Filesystem path that was probed.
        status: Machine-friendly probe status.
        reason: Machine-friendly reason for the probe outcome.
        candidates: Scored file type candidates in deterministic resolution order.
            Empty when the path was filtered before probing or when no candidates
            matched.
        selected_file_type: Selected file type identity, or ``None`` when
            unsupported or filtered.
        selected_processor: Selected processor identity, or ``None`` when
            unsupported, unbound, or filtered.
        activation: Declared activation and dynamic authorization for the
            selected file type, or ``None`` when no type was selected.
    """

    rule_matches: tuple[tuple[FileTypeRule, str], ...] = ()
    path: Path
    status: ResolutionProbeStatus
    reason: ResolutionProbeReason
    candidates: tuple[ResolutionProbeCandidate, ...]
    selected_file_type: ResolutionProbeSelection | None
    selected_processor: ResolutionProbeSelection | None
    activation: ResolutionProbeActivation | None = None

    @property
    def file_type_assigned(self) -> bool | None:
        """Return whether the selected type came from an explicit assignment."""
        if self.selected_file_type is None:
            return None
        return bool(
            self.rule_matches and self.selection_method == FileTypeSelectionMethod.ASSIGNMENT
        )

    @property
    def selection_method(self) -> FileTypeSelectionMethod:
        """Return the winning rule's selection method, defaulting to inference."""
        if self.rule_matches and self.rule_matches[-1][0].action == FileTypeRuleAction.ASSIGN:
            return FileTypeSelectionMethod.ASSIGNMENT
        return FileTypeSelectionMethod.INFERENCE
