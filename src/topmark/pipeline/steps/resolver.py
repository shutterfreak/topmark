# topmark:header:start
#
#   project      : TopMark
#   file         : resolver.py
#   file_relpath : src/topmark/pipeline/steps/resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File type and header processor resolver step for the TopMark pipeline.

This step determines the `FileType` for the current path and attaches the
corresponding `HeaderProcessor` instance from the registry. It updates
`ctx.status.resolve` accordingly and records diagnostics for unsupported files or
missing processors. It performs no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.constants import VALUE_NOT_SET
from topmark.filetypes.base import ContentGate, FileType
from topmark.filetypes.instances import get_file_type_registry
from topmark.filetypes.registry import get_header_processor_registry
from topmark.pipeline.context import ProcessingContext, ResolveStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)


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
        ft (FileType): File type whose rules are evaluated.
        base_name (str): Basename of the path (e.g., "settings.json").
        path_str (str): POSIX path string (used for tail matches like ".vscode/settings.json").

    Returns:
        MatchSignals: Booleans indicating extension, filename/tail, and pattern matches.
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
        ft (FileType): File type whose gate is evaluated.
        sig (MatchSignals): Name-based match signals for the current path.

    Returns:
        bool: True if calling `content_matcher` is allowed.
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
        ft (FileType): File type considered as candidate.
        sig (MatchSignals): Name-based match signals for the current path.
        content_hit (bool): Result of calling the content matcher (if probed).

    Returns:
        bool: True if the candidate should be considered.
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

    Precedence (desc): explicit filename/tail > content-based (upgrade over ext)
    > pattern > extension. Headerable types get +1 on ties.

    Args:
        ft (FileType): File type under evaluation.
        sig (MatchSignals): Name-based match signals for the current path.
        content_hit (bool): Whether content-based refinement matched.
        base_name (str): Basename of the path.
        path_str (str): POSIX path string of the path.

    Returns:
        int: A score where higher is better.
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


def resolve(ctx: ProcessingContext) -> ProcessingContext:
    """Resolve and assign the file type and header processor for the file.

    Updates these fields on the context when successful: `ctx.file_type`,
    `ctx.header_processor`, and `ctx.status.resolve`. On failure it appends a
    human-readable diagnostic and sets an appropriate resolve status.

    Args:
        ctx (ProcessingContext): Processing context representing the file being handled.

    Returns:
        ProcessingContext: The same context, updated in place.
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
    candidates: list[tuple[int, str, FileType]] = []

    base_name: str = ctx.path.name
    path_str: str = ctx.path.as_posix()

    # 1) Compute name signals -> 2) Gate content probe -> 3) Include? -> 4) Score
    for ft in get_file_type_registry().values():
        sig: MatchSignals = _compute_signals(ft, base_name, path_str)
        should_probe: bool = _should_probe_content(ft, sig)

        cm: Callable[[Path], bool] | None = ft.content_matcher or None
        content_hit = False
        if should_probe and callable(cm):
            try:
                content_hit = bool(cm(ctx.path))
            except Exception:
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

    if candidates:
        # Best by (score DESC, name ASC) for deterministic choice
        candidates.sort(key=lambda x: (-x[0], x[1]))
        file_type: FileType
        _, _, file_type = candidates[0]

        ctx.file_type = file_type
        logger.debug("File '%s' resolved to type: %s", ctx.path, file_type.name)

        if file_type.skip_processing:
            ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
            ctx.add_warning(
                f"File type '{file_type.name}' recognized; "
                "headers are not supported for this format. Skipping."
            )
            logger.info(
                "Skipping header processing for '%s' (file type '%s' marked skip_processing=True)",
                ctx.path,
                file_type.name,
            )
            return ctx

        # Matched a FileType, but no header processor is registered for it
        processor: HeaderProcessor | None = get_header_processor_registry().get(file_type.name)
        if processor is None:
            ctx.status.resolve = ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
            ctx.add_warning(f"No header processor registered for file type '{file_type.name}'.")
            logger.info(
                "No header processor registered for file type '%s' (file '%s')",
                file_type.name,
                ctx.path,
            )
            return ctx

        # Success: attach the processor and mark the file as resolved
        ctx.header_processor = processor
        ctx.status.resolve = ResolveStatus.RESOLVED
        logger.debug(
            "Resolve success: file='%s' type='%s' processor=%s",
            ctx.path,
            file_type.name,
            processor.__class__.__name__,
        )
        return ctx

    # No FileType matched: mark as unsupported and record a diagnostic
    ctx.status.resolve = ResolveStatus.UNSUPPORTED
    ctx.add_warning("No file type associated with this file.")
    logger.info("Unsupported file type for '%s' (no matcher)", ctx.path)
    return ctx
