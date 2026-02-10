# topmark:header:start
#
#   project      : TopMark
#   file         : resolver.py
#   file_relpath : src/topmark/pipeline/steps/resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolve file type and select header processor.

Determines `ctx.file_type` from name/content signals and attaches a registered
`HeaderProcessor` if available. Sets `ctx.status.resolve` accordingly.

Sets:
  - `ResolveStatus` → {RESOLVED, TYPE_RESOLVED_HEADERS_UNSUPPORTED,
                       TYPE_RESOLVED_NO_PROCESSOR_REGISTERED, UNSUPPORTED}
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.constants import VALUE_NOT_SET
from topmark.filetypes.base import ContentGate, FileType
from topmark.pipeline.hints import Axis, Cluster, KnownCode
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from topmark.config.logging import TopmarkLogger
    from topmark.config.model import Config
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)


Candidate = tuple[int, str, FileType]


def _candidate_order_key(candidate: Candidate) -> tuple[int, str]:
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
    score, name, _ = candidate
    return (-score, name)


@dataclass(frozen=True)
class MatchSignals:
    """Name-based match signals for a FileType (extension, filename/tail, pattern)."""

    ext: bool
    fname: bool
    pat: bool

    @property
    def any(self) -> bool:
        """Whether any name-based signal matched (extension, filename, or pattern)."""
        return self.ext or self.fname or self.pat


def _compute_signals(ft: FileType, base_name: str, path_str: str) -> MatchSignals:
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


def _should_probe_content(ft: FileType, sig: MatchSignals) -> bool:
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
        return sig.ext
    if gate is ContentGate.IF_FILENAME:
        return sig.fname
    if gate is ContentGate.IF_PATTERN:
        return sig.pat
    if gate is ContentGate.IF_ANY_NAME_RULE:
        return sig.any
    if gate is ContentGate.IF_NONE:
        no_rules: bool = not ((ft.extensions or []) or (ft.filenames or []) or (ft.patterns or []))
        return no_rules
    # ContentGate.ALWAYS
    return True


def _include_candidate(ft: FileType, sig: MatchSignals, content_hit: bool) -> bool:
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
    if gate is ContentGate.IF_EXTENSION and sig.ext:
        return content_hit or sig.fname or sig.pat
    if gate is ContentGate.IF_FILENAME and sig.fname:
        return content_hit
    if gate is ContentGate.IF_PATTERN and sig.pat:
        return content_hit
    if gate is ContentGate.IF_ANY_NAME_RULE and sig.any:
        return content_hit
    if gate is ContentGate.IF_NONE:
        return content_hit
    # ALWAYS: allow content to create a match even if name rules didn't
    return include or content_hit


def _score(
    ft: FileType, sig: MatchSignals, content_hit: bool, base_name: str, path_str: str
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
    if sig.fname:
        best: int = 0
        for fname in ft.filenames or []:
            if base_name == fname or path_str.endswith(fname):
                best = max(best, 100 + min(len(fname), 100))
        s = max(s, best)
    if content_hit:
        s = max(s, 90)
    if sig.pat:
        s = max(s, 70)
    if sig.ext:
        best_ext: int = 50
        for ext in ft.extensions or []:
            if base_name.endswith(ext):
                best_ext = max(best_ext, 50 + min(len(ext), 10))
        s = max(s, best_ext)
    if not getattr(ft, "skip_processing", False):
        s += 1
    return s


def get_candidates_for_file_path(path: Path) -> list[Candidate]:
    """Return candidate file types using name-based and optional content‑based matching.

    This helper centralizes the resolution logic used by `ResolverStep`.
    For each registered `FileType`, it computes name‑based match signals,
    determines whether content probing is allowed via the file type’s
    `ContentGate`, optionally calls the file type’s `content_matcher`, and
    evaluates inclusion rules and scoring.

    Args:
        path: Filesystem path of the file being resolved.

    Returns:
        A list of `(score, file_type_name, FileType)` tuples, unsorted. The caller is responsible
        for selecting the best candidate.
    """
    base_name: str = path.name
    path_str: str = path.as_posix()
    candidates: list[Candidate] = []

    # Validate against the effective file type registry:
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()

    # 1) Compute name signals -> 2) Gate content probe -> 3) Include? -> 4) Score
    for ft in ft_registry.values():
        sig: MatchSignals = _compute_signals(ft, base_name, path_str)
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

        if not _include_candidate(ft, sig, content_hit):
            continue

        candidates.append(
            (
                _score(ft, sig, content_hit, base_name, path_str),
                ft.name,
                ft,
            )
        )
    return candidates


def resolve_file_type_for_path(path: Path, *, cfg: Config) -> FileType | None:
    """Resolve the best `FileType` for a path, respecting configuration filters.

    This function wraps `get_candidates_for_file_path()` and additionally
    applies the user-provided configuration constraint `cfg.include_file_types` (whitelist)
    and `cfg.exclude_file_types` (blacklist), which restrict the set of allowed
    file type identifiers.

    If no candidates remain after filtering, `None` is returned.

    Args:
        path: Filesystem path of the file being resolved.
        cfg: Active immutable configuration snapshot. Only `cfg.include_file_types` and
            `cfg.exclude_file_types` are consulted here.

    Returns:
        The highest-scoring candidate, or None if none match.
    """
    candidates: list[Candidate] = get_candidates_for_file_path(path)

    # Filter by cfg.include_file_types if provided (whitelist)
    included: frozenset[str] = cfg.include_file_types
    if included:
        candidates = [c for c in candidates if c[2].name in included]

    # Filter by cfg.exclude_file_types if provided (blacklist)
    excluded: frozenset[str] = cfg.exclude_file_types
    if excluded:
        candidates = [c for c in candidates if c[2].name not in excluded]

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
    best: Candidate = min(candidates, key=_candidate_order_key)
    return best[2]


class ResolverStep(BaseStep):
    """Resolve file type and attach a header processor (no I/O).

    This step evaluates name rules (extensions/filenames/patterns) and, if allowed
    by the file type's content-gate, optional content probes to pick the best
    `FileType`. It also binds the matching `HeaderProcessor` (if registered).

    Axes written:
      - resolve

    Sets:
      - ResolveStatus: {PENDING, RESOLVED, TYPE_RESOLVED_HEADERS_UNSUPPORTED,
                        TYPE_RESOLVED_NO_PROCESSOR_REGISTERED, UNSUPPORTED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.RESOLVE,
            axes_written=(Axis.RESOLVE,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Return True (resolver is the first step and always runs).

        Args:
            ctx: The processing context for the current file.

        Returns:
            True if processing can proceed to the build step, False otherwise.
        """
        return True

    def run(self, ctx: ProcessingContext) -> None:
        """Resolve and assign the file type and header processor for the file.

        Updates these fields on the context when successful: `ctx.file_type`,
        `ctx.header_processor`, and `ctx.status.resolve`. On failure it appends a
        human-readable diagnostic and sets an appropriate resolve status.

        Args:
            ctx: Processing context representing the file being handled.

        Side effects:
            Sets `ctx.file_type`, `ctx.header_processor`, and `ctx.status.resolve`.
            Appends human-readable diagnostics when resolution fails or is partial.
        """
        ctx.status.resolve = ResolveStatus.PENDING

        logger.debug(
            "Resolve start: file='%s', fs status='%s', type=%s, processor=%s",
            ctx.path,
            ctx.status.fs.value,
            getattr(ctx.file_type, "name", VALUE_NOT_SET),
            (ctx.header_processor.__class__.__name__ if ctx.header_processor else VALUE_NOT_SET),
        )

        # Attempt to match the path against each registered FileType,
        # then pick the most specific match.
        candidates: list[Candidate] = []

        candidates = get_candidates_for_file_path(ctx.path)

        if candidates:
            # Best by (score DESC, name ASC) for deterministic choice
            candidates.sort(key=_candidate_order_key)
            file_type: FileType
            _, _, file_type = candidates[0]

            ctx.file_type = file_type
            logger.debug("File '%s' resolved to type: %s", ctx.path, file_type.name)

            if file_type.skip_processing:
                logger.info(
                    "Skipping header processing for '%s' "
                    "(file type '%s' marked skip_processing=True)",
                    ctx.path,
                    file_type.name,
                )
                ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
                reason: str = (
                    f"File type '{file_type.name}' recognized; "
                    "headers are not supported for this format."
                )
                ctx.info(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

            # Matched a FileType, but no header processor is registered for it
            hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()
            processor: HeaderProcessor | None = hp_registry.get(file_type.name)
            if processor is None:
                logger.info(
                    "No header processor registered for file type '%s' (file '%s')",
                    file_type.name,
                    ctx.path,
                )
                ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
                reason = f"No header processor registered for file type '{file_type.name}'."
                ctx.info(reason)
                ctx.request_halt(reason=reason, at_step=self)
                return

            # Success: attach the processor and mark the file as resolved
            ctx.header_processor = processor
            ctx.status.resolve = ResolveStatus.RESOLVED
            logger.debug(
                "Resolve success: file='%s' type='%s' processor=%s",
                ctx.path,
                file_type.name,
                processor.__class__.__name__,
            )
            return

        # No FileType matched
        logger.info("Unsupported file type for '%s' (no matcher)", ctx.path)
        ctx.status.resolve = ResolveStatus.UNSUPPORTED
        reason = "No file type associated with this file."
        ctx.info(reason)
        ctx.request_halt(reason=reason, at_step=self)
        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Advise about resolution outcome (non-binding).

        Args:
            ctx: The processing context.
        """
        st: ResolveStatus = ctx.status.resolve

        # May proceed to next step:
        if st == ResolveStatus.RESOLVED:
            # Implies file_type and header_processor are defined
            pass  # healthy, no hint
        # Stop processing:
        elif st == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED:
            ctx.hint(
                axis=Axis.RESOLVE,
                code=KnownCode.DISCOVERY_NO_PROCESSOR,
                cluster=Cluster.SKIPPED,
                message="no header processor registered",
                terminal=True,
            )
        elif st == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED:
            ctx.hint(
                axis=Axis.RESOLVE,
                code=KnownCode.DISCOVERY_UNSUPPORTED,
                cluster=Cluster.SKIPPED,
                message="headers not supported for this type",
                terminal=True,
            )
        elif st == ResolveStatus.UNSUPPORTED:
            ctx.hint(
                axis=Axis.RESOLVE,
                code=KnownCode.DISCOVERY_UNSUPPORTED,
                cluster=Cluster.SKIPPED,
                message="file type is not supported",
                terminal=True,
            )
        elif st == ResolveStatus.PENDING:
            # resolver did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
