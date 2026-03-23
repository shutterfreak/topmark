# topmark:header:start
#
#   project      : TopMark
#   file         : filetypes.py
#   file_relpath : src/topmark/resolution/filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Path-based file type and processor resolution helpers.

This module contains the shared scoring-based resolution engine used to map a
concrete filesystem path onto the most specific matching
[`FileType`][topmark.filetypes.model.FileType], and optionally onto the bound
[`HeaderProcessor`][topmark.processors.base.HeaderProcessor] registered for that
resolved file type.

Unlike identifier-based lookup in [`topmark.registry.filetypes`][topmark.registry.filetypes],
these helpers operate on real paths and evaluate extension, filename, pattern,
and optional content-based signals.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.core.logging import get_logger
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import FileType
from topmark.processors.base import HeaderProcessor
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Collection
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.core.logging import TopmarkLogger
    from topmark.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)


@dataclass(frozen=True, slots=True, init=True)
class FileTypeCandidate:
    """Describe a FileType candidate.

    Attributes:
        score: file type candidate matching score
        namespace: Candidate file type namespace
        local_key: Candiate file type local key
        file_type: Candidate FileType instance
    """

    score: int
    namespace: str
    local_key: str
    file_type: FileType


@dataclass(frozen=True, slots=True)
class MatchSignals:
    """Name-based match signals for a FileType (extension, filename/tail, pattern)."""

    extension: bool
    filename: bool
    pattern: bool

    @property
    def any(self) -> bool:
        """Whether any name-based signal matched (extension, filename, or pattern)."""
        return self.extension or self.filename or self.pattern


@dataclass(frozen=True, slots=True)
class ResolvedBinding:
    """Resolved file type and associated header processor for a path.

    Attributes:
        file_type: Resolved `FileType`, or ``None`` when no candidate matched.
        processor: Bound `HeaderProcessor` for the resolved file type, or
            ``None`` when the file type is unsupported or unresolved.
    """

    file_type: FileType | None
    processor: HeaderProcessor | None


def candidate_order_key(  # TODO: make namespace-aware (TOPMARK_NAMESPACE loest priority)
    candidate: FileTypeCandidate,
) -> tuple[int, str]:
    """Return the ordering key for a file type resolution candidate.

    Candidates are ordered by:
      1) score (descending)
      2) file type name (ascending)

    This key is intended to be used with `min()`:
        min(candidates, key=_candidate_order_key)
    so that the best candidate is selected deterministically without
    sorting the entire list.

    Args:
        candidate: A `(score, name, FileType)` tuple.

    Returns:
        The composite ordering key.
    """
    return (-candidate.score, candidate.local_key)


def _compute_match_signals(
    ft: FileType,
    base_name: str,
    path_str: str,
) -> MatchSignals:
    """Compute name-based match signals for a file type.

    Args:
        ft: File type whose rules are evaluated.
        base_name: Basename of the path (e.g., "settings.json").
        path_str: POSIX path string (used for tail matches like ".vscode/settings.json").

    Returns:
        Booleans indicating extension, filename/tail, and pattern matches.
    """
    exts: list[str] = ft.extensions or []
    fnames: list[str] = ft.filenames or []
    pats: list[str] = ft.patterns or []
    # Consider multi-dot extensions (e.g., ".d.ts") by checking the basename.
    ext_match: bool = any(base_name.endswith(ext) for ext in exts)
    fname_match = False
    if fnames:
        for fname in fnames:
            # Normalize declared tail to POSIX to match path_str (which is POSIX)
            tail: str = fname.replace("\\", "/")
            if "/" in tail:
                if path_str.endswith(tail):
                    fname_match = True
                    break
            elif base_name == tail:
                fname_match = True
                break
    pat_match: bool = any(re.fullmatch(p, base_name) is not None for p in pats)
    return MatchSignals(ext_match, fname_match, pat_match)


def _should_probe_content(
    ft: FileType,
    sig: MatchSignals,
) -> bool:
    """Decide whether the content matcher may be evaluated for this file type.

    The decision is based on the file type's `ContentGate` and the
    name-based match signals. This avoids probing content for clearly unrelated
    files (e.g., Markdown accidentally containing `//`).

    Args:
        ft: File type whose gate is evaluated.
        sig: Name-based match signals for the current path.

    Returns:
        True if calling `content_matcher` is allowed.
    """
    gate: ContentGate = ft.content_gate or ContentGate.NEVER
    if gate is ContentGate.NEVER:
        return False
    if gate is ContentGate.IF_EXTENSION:
        return sig.extension
    if gate is ContentGate.IF_FILENAME:
        return sig.filename
    if gate is ContentGate.IF_PATTERN:
        return sig.pattern
    if gate is ContentGate.IF_ANY_NAME_RULE:
        return sig.any
    if gate is ContentGate.IF_NONE:
        no_rules: bool = not ((ft.extensions or []) or (ft.filenames or []) or (ft.patterns or []))
        return no_rules
    # ContentGate.ALWAYS
    return True


def _should_include_candidate(
    ft: FileType,
    sig: MatchSignals,
    content_hit: bool,
) -> bool:
    """Determine if a candidate should be included after gating content.

    Applies gate-aware inclusion rules. For overlay types (e.g., JSONC over JSON)
    this requires a positive content hit when only the gated name signal matched.

    Args:
        ft: File type considered as candidate.
        sig: Name-based match signals for the current path.
        content_hit: Result of calling the content matcher (if probed).

    Returns:
        True if the candidate should be considered.
    """
    cm: Callable[[Path], bool] | None = ft.content_matcher or None
    include: bool = sig.any
    if not callable(cm):
        return include

    # Gate-aware inclusion
    gate: ContentGate = ft.content_gate or ContentGate.NEVER
    if gate is ContentGate.NEVER:
        return include
    if gate is ContentGate.IF_EXTENSION and sig.extension:
        return content_hit or sig.filename or sig.pattern
    if gate is ContentGate.IF_FILENAME and sig.filename:
        return content_hit
    if gate is ContentGate.IF_PATTERN and sig.pattern:
        return content_hit
    if gate is ContentGate.IF_ANY_NAME_RULE and sig.any:
        return content_hit
    if gate is ContentGate.IF_NONE:
        return content_hit
    # ALWAYS: allow content to create a match even if name rules didn't
    return include or content_hit


def _score_file_type_candidate(
    ft: FileType,
    sig: MatchSignals,
    content_hit: bool,
    base_name: str,
    path_str: str,
) -> int:
    """Score a candidate for tie-breaking.

    Precedence: explicit filename/tail > content-based (upgrade over ext)
    > pattern > extension. Headerable types get +1 on ties.

    Args:
        ft: File type under evaluation.
        sig: Name-based match signals for the current path.
        content_hit: Whether content-based refinement matched.
        base_name: Basename of the path.
        path_str: POSIX path string of the path.

    Returns:
        A score where higher is better.
    """
    s: int = 0
    if sig.filename:
        best: int = 0
        for fname in ft.filenames or []:
            if base_name == fname or path_str.endswith(fname):
                best = max(best, 100 + min(len(fname), 100))
        s = max(s, best)
    if content_hit:
        s = max(s, 90)
    if sig.pattern:
        s = max(s, 70)
    if sig.extension:
        best_ext: int = 50
        for ext in ft.extensions or []:
            if base_name.endswith(ext):
                best_ext = max(best_ext, 50 + min(len(ext), 10))
        s = max(s, best_ext)
    if not getattr(ft, "skip_processing", False):
        s += 1
    return s


def get_file_type_candidates_for_path(
    path: Path,
    *,
    include_file_types: Collection[str] | None = None,
    exclude_file_types: Collection[str] | None = None,
) -> list[FileTypeCandidate]:
    """Return candidate file types using name-based and optional content‑based matching.

    This helper centralizes the resolution logic used by `ResolverStep`.
    For each registered `FileType`, it computes name‑based match signals,
    determines whether content probing is allowed via the file type’s
    `ContentGate`, optionally calls the file type’s `content_matcher`, and
    evaluates inclusion rules and scoring.

    Args:
        path: Filesystem path of the file being resolved.
        include_file_types: Optional set of file type identifiers to include (whitelist).
            Empty collection means no whitelist filter
        exclude_file_types: Optional set of file type identifiers to exclude (blacklist).
            Empty collection means no blacklist filter

    Returns:
        A list of `(score, file_type_name, FileType)` tuples, unsorted. The caller is responsible
        for selecting the best candidate.
    """
    base_name: str = path.name
    path_str: str = path.as_posix()
    candidates: list[FileTypeCandidate] = []

    # Validate against the effective file type registry:
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()

    # 1) Compute name signals -> 2) Gate content probe -> 3) Include? -> 4) Score

    # Normalizeation: empty collections are treated the same as None.
    effective_include: Collection[str] | None = include_file_types or None
    effective_exclude: Collection[str] | None = exclude_file_types or None

    for ft in ft_registry.values():
        if effective_include is not None and ft.local_key not in effective_include:
            continue
        if effective_exclude is not None and ft.local_key in effective_exclude:
            continue

        sig: MatchSignals = _compute_match_signals(ft, base_name, path_str)
        should_probe: bool = _should_probe_content(ft, sig)

        cm: Callable[[Path], bool] | None = ft.content_matcher or None
        content_hit = False
        if should_probe and callable(cm):
            try:
                content_hit = bool(cm(path))
            except (
                OSError,
                UnicodeError,
                ValueError,
                TypeError,
                RuntimeError,
                AssertionError,
            ) as e:
                # Content matchers are user/extensible; keep resolver resilient.
                logger.debug("content matcher failed (%s); treating as no-hit", type(e).__name__)
                content_hit = False

        if not _should_include_candidate(ft, sig, content_hit):
            continue

        candidates.append(
            FileTypeCandidate(
                score=_score_file_type_candidate(ft, sig, content_hit, base_name, path_str),
                namespace=ft.namespace,
                local_key=ft.local_key,
                file_type=ft,
            )
        )
    return candidates


def _select_best_file_type_candidate(
    candidates: list[FileTypeCandidate],
) -> FileTypeCandidate | None:
    """Select the best file type candidate deterministically.

    Candidates are ranked by
    [`candidate_order_key`][topmark.resolution.filetypes.candidate_order_key],
    which prefers higher score and then lower file type name.

    Args:
        candidates: Candidate tuples in `(score, file_type_name, FileType)` form.

    Returns:
        The best candidate, or ``None`` if `candidates` is empty.
    """
    if not candidates:
        return None

    # Deterministic best candidate selection.
    #
    # We want the highest score to win, with a stable tie-break on file type name
    # (ascending) to ensure deterministic behavior across runs.
    #
    # Using `min()` with a composite key avoids sorting the full list:
    #   key = (-score, name)
    # so the "best" candidate becomes the smallest by this ordering.
    return min(candidates, key=candidate_order_key)


def resolve_file_type_for_path(
    path: Path,
    *,
    include_file_types: Collection[str] | None = None,
    exclude_file_types: Collection[str] | None = None,
) -> FileType | None:
    """Resolve the best matching `FileType` for `path`.

    Args:
        path: Filesystem path of the file being resolved.
        include_file_types: Optional set of file type identifiers to include (whitelist).
            Empty collection means no whitelist filter
        exclude_file_types: Optional set of file type identifiers to exclude (blacklist).
            Empty collection means no blacklist filter

    Returns:
        The highest-scoring matching `FileType`, or ``None`` if no candidates
        remain after filtering.
    """
    candidates: list[FileTypeCandidate] = get_file_type_candidates_for_path(
        path,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
    )

    if not candidates:
        return None

    best: FileTypeCandidate | None = _select_best_file_type_candidate(candidates)
    return None if best is None else best.file_type


def resolve_binding_for_path(
    path: Path,
    *,
    include_file_types: Collection[str] | None = None,
    exclude_file_types: Collection[str] | None = None,
) -> ResolvedBinding:
    """Resolve the effective file type/processor binding for `path`.

    Args:
        path: Filesystem path of the file being resolved.
        include_file_types: Optional set of file type identifiers to include (whitelist).
            Empty collection means no whitelist filter
        exclude_file_types: Optional set of file type identifiers to exclude (blacklist).
            Empty collection means no blacklist filter

    Returns:
        [`ResolvedBinding`][topmark.resolution.filetypes.ResolvedBinding]
        containing the resolved file type and associated processor.
    """
    file_type: FileType | None = resolve_file_type_for_path(
        path,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
    )
    if file_type is None:
        logger.warning("File '%s' cannot be resolved to a registered file type", path)
        return ResolvedBinding(None, None)

    from topmark.registry.registry import Registry

    processor: HeaderProcessor | None = Registry.resolve_processor(file_type.qualified_key)
    if processor is None:
        logger.warning(
            "File '%s' is resolved to file type '%s' but has no registered header processor",
            path,
            file_type.local_key,
        )
    return ResolvedBinding(file_type, processor)
