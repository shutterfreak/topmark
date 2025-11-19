# topmark:header:start
#
#   project      : TopMark
#   file         : model.py
#   file_relpath : src/topmark/pipeline/context/model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Processing context model for the TopMark pipeline.

This module defines the core data structures used to represent the state of
a single file as it flows through the TopMark pipeline. The central type is
[`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext], which
carries configuration, status, diagnostics, and view data between steps.

Sections:
    ProcessingContext:
        High-level container that represents the per-file processing state
        and exposes convenience helpers for policy checks, feasibility
        decisions, and view access.

    FlowControl:
        Small helper dataclass that allows steps to request early,
        graceful termination of the pipeline for a given file.
"""

from __future__ import annotations

import logging
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
from topmark.pipeline.context.policy import allow_empty_by_policy
from topmark.pipeline.context.status import HeaderProcessingStatus
from topmark.pipeline.hints import Cluster, Hint, select_headline_hint
from topmark.pipeline.views import UpdatedView, Views

from ..status import (
    ComparisonStatus,
    FsStatus,
    HeaderStatus,
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
    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.pipeline.protocols import Step
    from topmark.rendering.colored_enum import Colorizer


logger: TopmarkLogger = get_logger(__name__)

__all__: list[str] = [
    "FlowControl",
    "ProcessingContext",
]


@dataclass
class FlowControl:
    """Execution flow control for the current file."""

    halt: bool = False
    reason: str = ""  # short code, e.g. "unsupported", "unchanged-summary"
    at_step: str = ""  # step name that requested the halt


@dataclass
class ProcessingContext:
    r"""Context for header processing in the TopMark pipeline.

    A ``ProcessingContext`` instance represents the complete, mutable state
    for a single file as it flows through the pipeline. It holds configuration,
    per-axis status, diagnostics, and view data, and it exposes helpers for
    policy- and feasibility-related decisions.

    Attributes:
        path (Path): The file path to process (absolute or relative to the
            working directory).
        config (Config): Effective configuration at the time of processing.
        steps (list[Step]): Ordered list of pipeline steps that have been
            executed for this context.
        file_type (FileType | None): Resolved file type for the file (for
            example, a Python or Markdown file type), if applicable.
        status (HeaderProcessingStatus): Aggregated status for each pipeline
            axis, kept as the single source of truth for per-axis outcomes.
        flow (FlowControl): Flow control flags indicating whether processing
            should halt and why.
        header_processor (HeaderProcessor | None): Header processor instance
            responsible for this file type, if any.
        leading_bom (bool): True if the original file began with a UTF-8 BOM
            (``"\\ufeff"``). The reader sets this flag and strips the BOM from
            the in-memory image; the writer re-attaches it to the final output.
        has_shebang (bool): True if the first logical line starts with ``"#!"
            `` (post-BOM normalization).
        newline_hist (dict[str, int]): Histogram of newline styles detected in
            the file image.
        dominant_newline (str | None): Dominant newline sequence detected in
            the file (for example, ``"\\n"`` or ``"\\r\\n"``), if any.
        dominance_ratio (float | None): Ratio of dominant newline occurrences
            versus total newline occurrences.
        mixed_newlines (bool | None): True if multiple newline styles were
            detected, False if a single style was found, or None if not
            evaluated yet.
        newline_style (str): Normalized newline style used when writing
            output; defaults to ``"\\n"``.
        ends_with_newline (bool | None): True if the file ends with a newline
            sequence, False if it does not, or None if unknown.
        pre_insert_capability (InsertCapability): Advisory from the sniffer
            about pre-insert checks (for example, spacers or empty body),
            defaults to ``InsertCapability.UNEVALUATED``.
        pre_insert_reason (str | None): Human-readable reason why insertion
            may be problematic.
        pre_insert_origin (str | None): Origin of the pre-insertion
            diagnostic (typically a step or subsystem name).
        diagnostics (list[Diagnostic]): Collected diagnostics (info, warning,
            and error) produced during processing.
        reason_hints (list[Hint]): Non-binding hints supplied by steps to
            explain decisions; used primarily for summarization.
        views (Views): Bundle that carries image/header/build/render/updated/
            diff views for this file. The runner may prune heavy views after
            processing.
    """

    path: Path  # The file path to process (absolute or relative to working directory)
    config: "Config"  # Active config at time of processing
    steps: list[Step] = field(default_factory=lambda: [])
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
        """Return the effective policy for this processing context.

        The effective policy combines the global configuration with any
        file-type-specific overrides for the current ``file_type``.

        Returns:
            Policy | None: The effective policy for this context, or ``None`` if
            policy resolution fails.
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

    @property
    def step_axes(self) -> dict[str, list[str]]:
        """Map each executed step to the axes it may write.

        The keys are step names (e.g. "SnifferStep"), and the values are
        lists of axis names (e.g. ["fs", "content"]). This is derived from
        the `axes_written` contract of each step instance in `self.steps`.

        Combined with `self.steps` (execution order) and `self.status.to_dict()`
        (per-axis final status), this provides a complete view of the
        step/axis/status relationship without duplicating status payloads.
        """
        result: dict[str, list[str]] = {}
        for step in self.steps:
            axes: list[str] = [axis.value for axis in step.axes_written]
            result[step.name] = axes
        return result

    def add_hint(self, hint: Hint) -> None:
        """Attach a structured hint to the processing context.

        Hints are non-binding diagnostics used to refine human-readable
        summaries without affecting the core outcome classification.

        Args:
            hint (Hint): The hint instance to attach.

        Returns:
            None: The hint collection is updated in place.
        """
        self.reason_hints.append(hint)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "added hint axis=%s code=%s message=%s", hint.axis, hint.code, hint.message
            )

    def stop_flow(self, reason: str, at_step: Step) -> None:
        """Request a graceful, terminal stop for the rest of the pipeline.

        Args:
            reason (str): Short machine-friendly reason code for halting the flow.
            at_step (Step): Step instance requesting the halt.

        Returns:
            None: The flow-control flags on this context are updated in place.
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
            list[str]: List of logical lines from the current image view. An
            empty list is returned if no image is available.
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

        The schema is intended for CLI/CI consumption and avoids color or
        formatting concerns. View details are delegated to
        ``self.views.as_dict()`` to keep this method small and consistent with
        the ``Views`` bundling.

        Returns:
            dict[str, object]: A JSON-serializable mapping describing the
            context, including path, file type, step statuses, views summary,
            diagnostics, and high-level outcome flags.
        """
        views_summary: dict[str, object] = self.views.as_dict()

        return {
            "path": str(self.path),
            "file_type": (self.file_type.name if self.file_type else None),
            "steps": [s.name for s in self.steps],
            "step_axes": self.step_axes,
            "status": self.status.to_dict(),
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

        Returns:
            str: Human-readable one-line summary, possibly followed by
            additional lines for verbose diagnostics depending on the
            configuration verbosity level.
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
        # head.cluster now carries the cluster value (e.g. "changed") but
        # enum_from_name(Cluster, cluster) looks up by enum name (e.g. "CHANGED").
        # Hence we use case insensitive lookup:
        cluster_elem: Cluster | None = enum_from_name(
            Cluster,
            cluster,
            case_insensitive=True,
        )
        color_fn: Colorizer = cluster_elem.color if cluster_elem else chalk.red.italic

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
        """Create a fresh context with no derived state.

        Args:
            path (Path): File system path for the file to process.
            config (Config): Effective configuration to attach to the context.

        Returns:
            ProcessingContext: Newly created context instance.
        """
        return cls(path=path, config=config)

    # --- Convenience helpers -------------------------------------------------
    def add_info(self, message: str) -> None:
        """Add an ``info`` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.

        Returns:
            None: The diagnostic is appended to the context in place.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.INFO, message))

    def add_warning(self, message: str) -> None:
        """Add a ``warning`` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.

        Returns:
            None: The diagnostic is appended to the context in place.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.WARNING, message))

    def add_error(self, message: str) -> None:
        """Add an ``error`` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.

        Returns:
            None: The diagnostic is appended to the context in place.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.ERROR, message))
