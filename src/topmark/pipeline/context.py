# topmark:header:start
#
#   project      : TopMark
#   file         : context.py
#   file_relpath : src/topmark/pipeline/context.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Context for header processing in the Topmark pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Sequence

from yachalk import chalk

from topmark.config.logging import get_logger
from topmark.config.policy import effective_policy
from topmark.core.diagnostics import (
    Diagnostic,
    DiagnosticLevel,
    DiagnosticStats,
    compute_diagnostic_stats,
)
from topmark.core.enum_mixins import enum_from_name
from topmark.filetypes.base import InsertCapability
from topmark.pipeline.hints import Cluster, Hint, select_headline_hint
from topmark.pipeline.views import UpdatedView, Views

from .status import (
    ComparisonStatus,
    ContentStatus,
    FsStatus,
    GenerationStatus,
    HeaderStatus,
    PatchStatus,
    PlanStatus,
    RenderStatus,
    ResolveStatus,
    StripStatus,
    WriteStatus,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from topmark.config import Config
    from topmark.config.logging import TopmarkLogger
    from topmark.config.policy import Policy
    from topmark.filetypes.base import FileType
    from topmark.pipeline.contracts import Step
    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.rendering.colored_enum import Colorizer


logger: TopmarkLogger = get_logger(__name__)

__all__: list[str] = [
    "allow_empty_by_policy",
    "allow_empty_header_by_policy",
    "ReasonHint",
    "FlowControl",
    "HeaderProcessingStatus",
    "ProcessingContext",
]


def allow_empty_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the file is empty and the effective policy allows header insertions.

    This checks the resolved per-type effective policy (global overlaid by per-type).
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    return ctx.status.fs == FsStatus.EMPTY and eff.allow_header_in_empty_files is True


def allow_empty_header_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the effective policy allows empty header insertions.

    This checks the resolved per-type effective policy (global overlaid by per-type).
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.
    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    return eff.render_empty_header_when_no_fields


def allow_content_reflow_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the effective policy allows content reflow.

    This checks the resolved per-type effective policy (global overlaid by per-type).
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.
    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    return eff.allow_reflow


def allows_mixed_line_endings_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if policy allows proceeding despite soft FS violations.

    This helper is used by early pipeline steps (e.g., ReaderStep) to continue
    when Sniffer detected *soft* file-system issues that a project might choose
    to tolerate. Hard errors (e.g., not found, unreadable, binary) must remain
    terminal and are not bypassed here.

    Soft violations considered:
      - FsStatus.BOM_BEFORE_SHEBANG
      - FsStatus.MIXED_LINE_ENDINGS

    Policy fields:
      - If the effective `Policy` defines `ignore_mixed_line_endings` and it is True,
        we allow proceeding on `MIXED_LINE_ENDINGS`.

    Notes:
      - This function is forward-compatible: it uses `getattr(...)` so it returns
        False for unknown fields on older Policy versions (safe default).
      - We *always* allow when `FsStatus` is already OK/EMPTY; for EMPTY, your
        existing `allow_empty_by_policy()` governs header insertion later.

    Args:
        ctx (ProcessingContext): Processing context containing fs status and config.

    Returns:
        bool: True if we may proceed despite a soft FS violation.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    if ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_mixed_line_endings", False))

    # All other FS states should not be skipped by policy here.
    return False


def allows_bom_before_shebang_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if policy allows proceeding despite soft FS violations.

    This helper is used by early pipeline steps (e.g., ReaderStep) to continue
    when Sniffer detected *soft* file-system issues that a project might choose
    to tolerate. Hard errors (e.g., not found, unreadable, binary) must remain
    terminal and are not bypassed here.

    Soft violations considered:
      - FsStatus.BOM_BEFORE_SHEBANG

    Policy fields:
      - If the effective `Policy` defines `ignore_bom_before_shebang` and it is True,
        we allow proceeding on `BOM_BEFORE_SHEBANG`.

    Notes:
      - This function is forward-compatible: it uses `getattr(...)` so it returns
        False for unknown fields on older Policy versions (safe default).
      - We *always* allow when `FsStatus` is already OK/EMPTY; for EMPTY, your
        existing `allow_empty_by_policy()` governs header insertion later.

    Args:
        ctx (ProcessingContext): Processing context containing fs status and config.

    Returns:
        bool: True if we may proceed despite a soft FS violation.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    if ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_bom_before_shebang", False))

    # All other FS states should not be skipped by policy here.
    return False


def policy_allows_fs_skip(ctx: "ProcessingContext") -> bool:
    """Return True if policy allows proceeding despite soft FS violations.

    This helper is used by early pipeline steps (e.g., ReaderStep) to continue
    when Sniffer detected *soft* file-system issues that a project might choose
    to tolerate. Hard errors (e.g., not found, unreadable, binary) must remain
    terminal and are not bypassed here.

    Soft violations considered:
      - FsStatus.BOM_BEFORE_SHEBANG
      - FsStatus.MIXED_LINE_ENDINGS

    Policy fields:
      - If the effective `Policy` defines `ignore_bom_before_shebang` and it is True,
        we allow proceeding on `BOM_BEFORE_SHEBANG`.
      - If the effective `Policy` defines `ignore_mixed_line_endings` and it is True,
        we allow proceeding on `MIXED_LINE_ENDINGS`.

    Notes:
      - This function is forward-compatible: it uses `getattr(...)` so it returns
        False for unknown fields on older Policy versions (safe default).
      - We *always* allow when `FsStatus` is already OK/EMPTY; for EMPTY, your
        existing `allow_empty_by_policy()` governs header insertion later.

    Args:
        ctx (ProcessingContext): Processing context containing fs status and config.

    Returns:
        bool: True if we may proceed despite a soft FS violation.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    if ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_bom_before_shebang", False))

    if ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_mixed_line_endings", False))

    # All other FS states should not be skipped by policy here.
    return False


# --- Step gatekeeping ------------------------------------------------------


@dataclass
class ReasonHint:
    """Lightweight advisory hint attached by steps.

    Hints are non‑binding breadcrumbs to help explain *why* a step reached
    a given state. They should never change classification/outcome directly.

    Attributes:
        axis (str): Logical axis the hint refers to (e.g., "fs", "content").
        code (str): Short, machine‑friendly reason code (e.g., "no-read").
        message (str): Human‑readable message explaining the reason succinctly.
    """

    axis: str
    code: str
    message: str


@dataclass
class FlowControl:
    """Execution flow control for the current file."""

    halt: bool = False
    reason: str = ""  # short code, e.g. "unsupported", "unchanged-summary"
    at_step: str = ""  # step name that requested the halt


@dataclass
class HeaderProcessingStatus:
    """Tracks the status of each processing phase for a single file.

    Fields correspond to each pipeline phase: file, header, generation, comparison, write.
    """

    # File type resolution status:
    resolve: ResolveStatus = ResolveStatus.PENDING

    # File system status (existence, permissions, binary):
    fs: FsStatus = FsStatus.PENDING

    # File content status (BOM, shebang, mixed newlines, readability):
    content: ContentStatus = ContentStatus.PENDING

    # Header-level axes: detect existing header
    header: HeaderStatus = HeaderStatus.PENDING  # Status of header detection/parsing

    # A. Check -- insert / update headers
    # A.1 Generate updated header list and updated header value dict
    generation: GenerationStatus = GenerationStatus.PENDING  # Status of header dict generation

    # A.2 Render the updated header according to the file type and header processor
    render: RenderStatus = RenderStatus.PENDING  # Status of header rendering

    # B. Strip -- remove existing header
    strip: StripStatus = StripStatus.PENDING  # Status of header stripping lifecycle

    # Compare existing and updated file image
    comparison: ComparisonStatus = ComparisonStatus.PENDING  # Status of header comparison

    # Plan updates to the file
    plan: PlanStatus = PlanStatus.PENDING  # Status of file update (prior to writing)

    # Generate a patch for updated files
    patch: PatchStatus = PatchStatus.PENDING  # Status of patch generation

    # Write changes
    write: WriteStatus = WriteStatus.PENDING  # Status of writing the header

    def reset(self) -> None:
        """Set all status fields to PENDING."""
        self.resolve = ResolveStatus.PENDING
        self.fs = FsStatus.PENDING
        self.content = ContentStatus.PENDING
        self.header = HeaderStatus.PENDING
        self.generation = GenerationStatus.PENDING
        self.render = RenderStatus.PENDING
        self.strip = StripStatus.PENDING
        self.comparison = ComparisonStatus.PENDING
        self.plan = PlanStatus.PENDING
        self.patch = PatchStatus.PENDING
        self.write = WriteStatus.PENDING


@dataclass
class ProcessingContext:
    """Context for header processing in the pipeline.

    This class holds all necessary information for processing a file's header,
    including the file path, configuration, detected header state, and derived
    header fields. It is used to pass data between different stages of the
    header processing pipeline.

    Attributes:
        path (Path): The file path to process.
        config (Config): The configuration for processing.
        steps (dict[str, int]): Keep track of the pipeline steps executed.
        file_type (FileType | None): The resolved file type, if applicable.
        status (HeaderProcessingStatus): Processing status for each pipeline phase.
        flow (FlowControl): If `True`, stop processing (reached a terminal state).
        header_processor (HeaderProcessor | None): The header processor instance for this file.
        leading_bom (bool): True when the original file began with a UTF-8 BOM
            ("\ufeff"). The reader sets this and strips the BOM from memory; the
            updater re-attaches it to the final output.
        has_shebang (bool): True if the first line starts with '#!' (post-BOM normalization).
        newline_hist (dict[str, int]): Histogram of newline styles found in the file.
        dominant_newline (str | None): Dominant newline style detected in the file.
        dominance_ratio (float | None): Dominance ratio of the dominant newline style.
        mixed_newlines (bool | None): True if mixed newline styles were found in the file.
        newline_style (str): The newline style in the file (``LF``, ``CR``, ``CRLF``).
        ends_with_newline (bool | None): True if the file ends with a newline.
        pre_insert_capability (InsertCapability): Advisory from the sniffer about
            pre-insert checks (e.g. spacers, empty body), defaults to UNEVALUATED.
        pre_insert_reason (str | None): Reason why insertion may be problematic.
        pre_insert_origin (str | None): Origin of the pre-insertion diagnostic.
        diagnostics (list[Diagnostic]): Warnings or errors encountered during processing.
        reason_hints (list[Hint]): Pre-outcome hints (non-binding).
        views (Views): Bundle that carries image/header/build/render/updated/diff
            views for this file. The runner may prune these after processing.
    """

    path: Path  # The file path to process (absolute or relative to working directory)
    config: "Config"  # Active config at time of processing
    steps: dict[str, int] = field(default_factory=lambda: {})  # Track the pipeline steps
    file_type: "FileType | None" = None  # Resolved file type (e.g., PythonFileType)
    status: HeaderProcessingStatus = field(default_factory=HeaderProcessingStatus)
    flow: FlowControl = field(default_factory=FlowControl)

    header_processor: "HeaderProcessor | None" = (
        None  # HeaderProcessor instance for this file type, if applicable
    )

    leading_bom: bool = False  # True if original file began with a UTF-8 BOM
    has_shebang: bool = False  # True if the first line starts with '#!' (post-BOM normalization)

    newline_hist: dict[str, int] = field(default_factory=lambda: {})
    dominant_newline: str | None = None
    dominance_ratio: float | None = None
    mixed_newlines: bool | None = None

    newline_style: str = "\n"  # Newline style (default = "\n")
    ends_with_newline: bool | None = None  # True if file ends with a newline sequence

    # Advisory from sniffer about pre-insert checks (e.g. spacers, empty body)
    pre_insert_capability: InsertCapability = InsertCapability.UNEVALUATED
    pre_insert_reason: str | None = None
    pre_insert_origin: str | None = None

    # Processing diagnostics: warnings/errors collected during processing
    diagnostics: list[Diagnostic] = field(default_factory=list[Diagnostic])

    # Pre-outcome hints (non-binding)
    reason_hints: list[Hint] = field(default_factory=list[Hint])

    # View-based properties
    views: Views = field(default_factory=Views)

    # Cache per instance
    _eff_policy: Policy | None = None  # cached

    def get_effective_policy(self) -> Policy | None:
        """Get the effective policy for the given processing context.

        Combines the effective processing context at Config level
        with overrides for the given FileType instance.
        """
        if self._eff_policy is not None:
            return self._eff_policy
        try:
            eff: Policy = effective_policy(
                self.config, self.file_type.name if self.file_type else None
            )
        except Exception:
            return None
        # Cache per-context so policy_by_type lookups aren’t repeated.
        self._eff_policy = eff
        return eff

    @property
    def would_change(self) -> bool | None:
        """Return whether a change *would* occur (tri-state).

        Returns:
            bool | None: ``True`` if a change is intended (e.g., comparison is
                CHANGED, a header is missing, or the strip step prepared/attempted
                a removal), ``False`` if definitively no change (e.g., UNCHANGED or
                strip NOT_NEEDED), and ``None`` when indeterminate because the
                comparison was skipped/pending and the strip step did not run.
        """
        # Strip intent takes precedence: READY means we intend to remove, and
        # FAILED still represents an intent (feasibility is handled by can_change).
        if self.status.strip in {StripStatus.READY, StripStatus.FAILED}:
            return True
        # Default pipeline intents
        if self.status.header == HeaderStatus.MISSING:
            return True
        if self.status.comparison == ComparisonStatus.CHANGED:
            return True
        if (
            self.status.comparison == ComparisonStatus.UNCHANGED
            or self.status.strip == StripStatus.NOT_NEEDED
        ):
            return False
        # Anything else (PENDING, SKIPPED, CANNOT_COMPARE with no strip decision)
        return None

    @property
    def can_change(self) -> bool:
        """Return whether a change *can* be applied safely.

        This reflects operational feasibility (filesystem/resolve status) and
        structural safety, with a policy-based allowance for inserting into empty files.
        """
        # baseline feasibility + structural safety
        feasible: bool = (
            self.status.resolve == ResolveStatus.RESOLVED
            # if strip preparation failed, we can’t change via strip:
            and self.status.strip != StripStatus.FAILED
            # malformed headers block safe mutation in the default pipeline:
            and self.status.header
            not in {
                HeaderStatus.MALFORMED,
                HeaderStatus.MALFORMED_ALL_FIELDS,
                HeaderStatus.MALFORMED_SOME_FIELDS,
            }
        )

        if not feasible:
            return False

        # Filesystem feasibility:
        # - OK files: allowed
        # - EMPTY files: allowed if per-type policy permits insertion into empty files
        if self.status.fs == FsStatus.OK:
            return True
        if self.status.fs == FsStatus.EMPTY and allow_empty_by_policy(self):
            return True

        return False

    @property
    def check_permitted_by_policy(self) -> bool | None:
        """Whether policy allows the intended type of change (tri-state).

        Returns:
            bool | None:
                - True  : policy allows the intended change (insert/replace)
                - False : policy forbids it (e.g., add_only forbids replace)
                - None  : indeterminate (no clear intent yet)
        """
        pol: Policy | None = self.get_effective_policy()
        pol_check_add_only: bool = pol.add_only if pol else False
        pol_check_update_only: bool = pol.update_only if pol else False

        if self.status.strip != StripStatus.PENDING:
            # StripperStep did run
            return None

        if self.status.header == HeaderStatus.PENDING:
            # ScannerStep did not run
            return None

        # Insert path (missing header)
        if pol_check_add_only:
            if (
                self.status.header
                in {
                    HeaderStatus.DETECTED,
                    HeaderStatus.EMPTY,
                    # HeaderStatus.MALFORMED_ALL_FIELDS,
                    # HeaderStatus.MALFORMED_SOME_FIELDS,
                }
                # and self.status.comparison == ComparisonStatus.CHANGED
            ):
                logger.debug(
                    "permitted_by_policy: header: %s, comparison: %s "
                    "-- pol_check_add_only: %s, will return False",
                    self.status.header,
                    self.status.comparison,
                    pol_check_add_only,
                )
                return False  # forbidden when add-only
            else:
                logger.debug(
                    "permitted_by_policy: header: %s, comparison: %s "
                    "-- pol_check_add_only: %s, will return True",
                    self.status.header,
                    self.status.comparison,
                    pol_check_add_only,
                )
                return True

        # Replace path (existing but different)
        if pol_check_update_only:
            if (
                self.status.header == HeaderStatus.MISSING
                # and self.status.comparison == ComparisonStatus.CHANGED
            ):
                logger.debug(
                    "permitted_by_policy: header: %s, comparison: %s "
                    "-- pol_check_update_only: %s, will return False",
                    self.status.header,
                    self.status.comparison,
                    pol_check_update_only,
                )
                return False  # forbidden when update-only
            else:
                logger.debug(
                    "permitted_by_policy: header: %s, comparison: %s "
                    "-- pol_check_update_only: %s, will return True",
                    self.status.header,
                    self.status.comparison,
                    pol_check_update_only,
                )
                return True

        # No clear intent yet → unknown
        if self.status.header not in {
            HeaderStatus.MISSING,
            HeaderStatus.DETECTED,
        } and self.status.comparison not in {
            ComparisonStatus.CHANGED,
            ComparisonStatus.UNCHANGED,
        }:
            logger.debug(
                "permitted_by_policy: header: %s, comparison: %s -- will return None",
                self.status.header,
                self.status.comparison,
            )
            return None

        logger.debug(
            "permitted_by_policy: header: %s, comparison: %s -- PROCEED",
            self.status.header,
            self.status.comparison,
        )

        # Unchanged or no-op
        return True

    @property
    def would_add_or_update(self) -> bool:
        """Intent for check/apply: True if we'd insert or replace a header."""
        return (
            self.status.header == HeaderStatus.MISSING
            or self.status.comparison == ComparisonStatus.CHANGED
        )

    @property
    def effective_would_add_or_update(self) -> bool:
        """True iff add/update is intended, feasible, and allowed by policy."""
        return (
            self.would_add_or_update
            and self.can_change is True
            and (self.check_permitted_by_policy is not False)
        )

    @property
    def would_strip(self) -> bool:
        """Intent for strip: True if a removal would occur."""
        return self.status.strip == StripStatus.READY

    @property
    def effective_would_strip(self) -> bool:
        """True iff a strip is intended and feasible."""
        # Policy doesn’t block strip; feasibility is in can_change
        return self.would_strip and self.can_change is True

    def add_hint(self, hint: Hint) -> None:
        """TODO Google-style docstring with type annotations."""
        logger.info(
            "Adding hint: axis: %s, code: %s, message: %s", hint.axis, hint.code, hint.message
        )
        self.reason_hints.append(hint)
        for h in self.reason_hints:
            logger.info("hint -- axis: %s, code: %s, message: %s", h.axis, h.code, h.message)

    def stop_flow(self, reason: str, at_step: Step) -> None:
        """Request a graceful, terminal stop for the rest of the pipeline.

        Args:
            reason (str): Reason for halting the flow.
            at_step (Step): the step requesting the halt.
        """
        logger.info("Flow halted in %s: %s", at_step.name, reason)
        self.flow = FlowControl(halt=True, reason=reason, at_step=at_step.name)

    # TODO: decide to keep or always refer to FileImageViewiter_lines() instead.
    def iter_image_lines(self) -> Iterable[str]:
        """Iterate the current file image without materializing.

        This accessor hides the underlying representation (list-backed, mmap-backed,
        or generator-based) and returns an iterator over logical lines with original
        newline sequences preserved.

        Returns:
            Iterable[str]: An iterator over the file's lines. If no image is present,
            an empty iterator is returned.
        """
        if self.views.image is not None:
            return self.views.image.iter_lines()
        return iter(())  # empty

    def image_line_count(self) -> int:
        """Return the number of logical lines without materializing.

        Returns:
            int: Total number of lines in the current image, or ``0`` if no image
            is present.
        """
        if self.views.image is not None:
            return self.views.image.line_count()
        return 0

    def iter_updated_lines(self) -> Iterable[str]:
        """Iterate the updated file image lines, if present.

        Returns:
            Iterable[str]: Iterator over updated lines. If no updated image is
            available (no planner/strip output), returns an empty iterator.
        """
        uv: UpdatedView | None = self.views.updated
        if not uv or uv.lines is None:
            return iter(())
        seq_or_it: Sequence[str] | Iterable[str] = uv.lines
        # If it's already a concrete sequence, avoid copying:
        if isinstance(seq_or_it, list) or isinstance(seq_or_it, tuple):
            return iter(seq_or_it)
        # Fallback: it's an arbitrary iterable (possibly a generator)
        return iter(seq_or_it)

    def materialize_image_lines(self) -> list[str]:
        """Return the original file image as a materialized list of lines.

        Returns:
            list[str]: List of logical lines from the current image view.
        """
        return list(self.iter_image_lines())

    def materialize_updated_lines(self) -> list[str]:
        """Return the updated file image as a materialized list of lines.

        Returns:
            list[str]: List of updated lines if present, otherwise an empty list.
        """
        uv: UpdatedView | None = self.views.updated
        if not uv or uv.lines is None:
            return []
        seq_or_it: Sequence[str] | Iterable[str] = uv.lines
        return seq_or_it if isinstance(seq_or_it, list) else list(seq_or_it)

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable representation of this processing result.

        The schema is stable for CLI/CI consumption and avoids color/formatting.
        View details are provided by ``self.views.as_dict()`` to keep this method
        small and consistent with the Views bundling.
        """
        views_summary: dict[str, object] = self.views.as_dict()

        return {
            "path": str(self.path),
            "file_type": (self.file_type.name if self.file_type else None),
            "status": {
                "resolve": self.status.resolve.name,
                "fs": self.status.fs.name,
                "content": self.status.content.name,
                "header": self.status.header.name,
                "generation": self.status.generation.name,
                "render": self.status.render.name,
                "comparison": self.status.comparison.name,
                "strip": self.status.strip.name,
                "plan": self.status.plan.name,
                "patch": self.status.patch.name,
                "write": self.status.write.name,
            },
            "views": views_summary,
            "diagnostics": [
                {"level": d.level.value, "message": d.message} for d in self.diagnostics
            ],
            "diagnostic_counts": {
                "info": sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.INFO),
                "warning": sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.WARNING),
                "error": sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.ERROR),
            },
            "pre_insert_check": {
                "capability": self.pre_insert_capability.name,
                "reason": self.pre_insert_reason,
                "origin": self.pre_insert_origin,
            },
            "outcome": {
                "would_change": self.would_change,
                "can_change": self.can_change,
                "permitted_by_policy": self.check_permitted_by_policy,
                "check": {
                    "would_add_or_update": self.would_add_or_update,
                    "effective_would_add_or_update": self.effective_would_add_or_update,
                },
                "strip": {
                    "would_strip": self.would_strip,
                    "effective_would_strip": self.effective_would_strip,
                },
            },
        }

    def format_summary(self) -> str:
        """Return a concise, human‑readable one‑liner for this file.

        The summary is aligned with TopMark's pipeline phases and mirrors what
        comparable tools (e.g., *ruff*, *black*, *prettier*) surface: a clear
        primary outcome plus a few terse hints.

        Rendering rules:
          1. Primary bucket comes from the view-layer classification helper
             `map_bucket()` in `topmark.api.view`. This ensures stable wording
             across commands and pipelines.
          2. If a write outcome is known (e.g., PREVIEWED/WRITTEN/INSERTED/REMOVED),
             append it as a trailing hint.
          3. If there is a diff but no write outcome (e.g., check/summary with
             `--diff`), append a "diff" hint.
          4. If diagnostics exist, append the diagnostic count as a hint.

        Verbose per‑line diagnostics are emitted only when Config.verbosity_level >= 1
        (treats None as 0).

        Examples (colors omitted here):
            path/to/file.py: python – would insert header - previewed
            path/to/file.py: python – up-to-date
            path/to/file.py: python – would strip header - diff - 2 issues
        """
        # Local import to avoid import cycles at module import time

        verbosity_level: int = self.config.verbosity_level or 0

        parts: list[str] = [f"{self.path}:"]

        # File type (dim), or <unknown> if resolution failed
        if self.file_type is not None:
            parts.append(chalk.dim(self.file_type.name))
        else:
            parts.append(chalk.dim("<unknown>"))

        head: Hint | None = None
        if not self.reason_hints:
            key: str = "no_hint"
            label: str = "No diagnostic hints"
        else:
            head = select_headline_hint(self.reason_hints)
            if head is None:
                key = "no_hint"
                label = "No diagnostic hints"
            else:
                key = head.code
                label = f"{head.axis.value.title()}: {head.message}"

        # Color choice can still be simple or based on cluster:
        cluster: str | None = head.cluster if head else None
        cluster_elem: Cluster | None = enum_from_name(Cluster, cluster)
        color_fn: Colorizer = cluster_elem.color if cluster_elem else chalk.red.dim.italic

        parts.append("-")
        parts.append(color_fn(f"{key}: {label}"))

        # Secondary hints: write status > diff marker > diagnostics

        if self.status.write != WriteStatus.PENDING:
            parts.append("-")
            parts.append(self.status.write.color(self.status.write.value))
        elif self.views.diff and self.views.diff.text:
            parts.append("-")
            parts.append(chalk.yellow("diff"))

        diag_show_hint: str = ""
        if self.diagnostics:
            stats: DiagnosticStats = compute_diagnostic_stats(self.diagnostics)
            n_info: int = stats.n_info
            n_warn: int = stats.n_warning
            n_err: int = stats.n_error
            parts.append("-")
            # Compose a compact triage summary like "1 error, 2 warnings"
            triage: list[str] = []
            if verbosity_level <= 0:
                diag_show_hint = chalk.dim.italic(" (use '-v' to view)")
            if n_err:
                triage.append(chalk.red_bright(f"{n_err} error" + ("s" if n_err != 1 else "")))
            if n_warn:
                triage.append(chalk.yellow(f"{n_warn} warning" + ("s" if n_warn != 1 else "")))
            if n_info and not (n_err or n_warn):
                # Only show infos when there are no higher severities
                triage.append(chalk.blue(f"{n_info} info" + ("s" if n_info != 1 else "")))
            parts.append(", ".join(triage) if triage else chalk.blue("info"))

        result: str = " ".join(parts) + diag_show_hint

        # Optional verbose diagnostic listing (gated by verbosity level)
        if self.diagnostics and verbosity_level > 0:
            details: list[str] = []
            for d in self.diagnostics:
                prefix: str = {
                    DiagnosticLevel.ERROR: chalk.red_bright("error"),
                    DiagnosticLevel.WARNING: chalk.yellow("warning"),
                    DiagnosticLevel.INFO: chalk.blue("info"),
                }[d.level]
                details.append(f"  [{prefix}] {d.message}")
            result += "\n" + "\n".join(details)

        return result

    @property
    def summary(self) -> str:
        """Return a formatted summary string of the processing status for this file."""
        return self.format_summary()

    @classmethod
    def bootstrap(cls, *, path: Path, config: Config) -> ProcessingContext:
        """Create a fresh context with no derived state."""
        return cls(path=path, config=config)

    # --- Convenience helpers -------------------------------------------------
    def add_info(self, message: str) -> None:
        """Add an `info` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.INFO, message))
        logger.info(message)

    def add_warning(self, message: str) -> None:
        """Add an `warning` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.WARNING, message))
        logger.warning(message)

    def add_error(self, message: str) -> None:
        """Add an `error` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.ERROR, message))
        logger.error(message)
