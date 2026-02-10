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

    HaltState:
        Small helper dataclass that records why and where processing
        was halted for a given file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from topmark.config.logging import get_logger
from topmark.config.policy import make_policy_registry
from topmark.diagnostic.model import (
    DiagnosticLog,
)
from topmark.filetypes.base import InsertCapability
from topmark.pipeline.context.policy import (
    can_change,
    check_permitted_by_policy,
    effective_would_add_or_update,
    effective_would_strip,
    would_add_or_update,
    would_change,
    would_strip,
)
from topmark.pipeline.context.status import ProcessingStatus
from topmark.pipeline.hints import (
    Axis,
    Cluster,
    HintLog,
    KnownCode,
    make_hint,
)
from topmark.pipeline.views import (
    UpdatedView,
    Views,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from topmark.config import Config
    from topmark.config.logging import TopmarkLogger
    from topmark.config.policy import Policy, PolicyRegistry
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.pipeline.protocols import Step


logger: TopmarkLogger = get_logger(__name__)

__all__: list[str] = [
    "HaltState",
    "ProcessingContext",
]


@dataclass(frozen=True)
class HaltState:
    """Information about a terminal halt for a single file.

    Instances of this dataclass describe why and where the pipeline
    decided to stop processing a file. A non-empty ``step_name`` implies
    that a step requested an early, graceful halt.

    Attributes:
        reason_code (str): Short machine-friendly reason code explaining
            why processing was halted (for example, ``"unsupported"`` or
            ``"unchanged-summary"``). Intended for internal use and
            machine output.
        step_name (str): Name of the pipeline step that requested the
            halt. An empty string indicates that no explicit halt has
            been recorded.
    """

    reason_code: str = ""  # short code, e.g. "unsupported", "unchanged-summary"
    step_name: str = ""  # step name that requested the halt


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
        policy_registry (PolicyRegistry): The policy registry (global
            + file type specific overrides).
        steps (list[Step]): Ordered list of pipeline steps that have been
            executed for this context.
        file_type (FileType | None): Resolved file type for the file (for
            example, a Python or Markdown file type), if applicable.
        status (ProcessingStatus): Aggregated status for each pipeline
            axis, kept as the single source of truth for per-axis outcomes.
        halt_state (HaltState | None): Information about an early, terminal
            halt for this file. ``None`` means processing has not been
            halted.
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
        diagnostics (DiagnosticLog): Collected diagnostics (info, warning,
            and error) produced during processing.
        diagnostic_hints (HintLog): Non-binding hints supplied by steps to
            explain decisions; used primarily for summarization.
        views (Views): Bundle that carries image/header/build/render/updated/
            diff views for this file. The runner may prune heavy views after
            processing.
    """

    path: Path  # The file path to process (absolute or relative to working directory)
    config: Config  # Active config at time of processing
    policy_registry: PolicyRegistry
    steps: list[Step] = field(default_factory=lambda: [])
    file_type: FileType | None = None  # Resolved file type (e.g., PythonFileType)
    status: ProcessingStatus = field(default_factory=ProcessingStatus)
    halt_state: HaltState | None = None

    header_processor: HeaderProcessor | None = (
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
    diagnostics: DiagnosticLog = field(default_factory=DiagnosticLog)

    # Pre-outcome hints (non-binding)
    diagnostic_hints: HintLog = field(default_factory=HintLog)

    # View-based properties
    views: Views = field(default_factory=Views)

    def get_effective_policy(self) -> Policy:
        """Return the effective policy for this processing context.

        The effective policy is derived from the global configuration and any
        file-type-specific overrides via the shared PolicyRegistry. This method
        does not perform any merging at runtime; all policies are resolved at
        Config.freeze() time.

        Returns:
            The effective policy for this context.
        """
        name: str | None = self.file_type.name if self.file_type is not None else None
        return self.policy_registry.for_type(name)

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

    def request_halt(self, reason: str, at_step: Step) -> None:
        """Request a graceful, terminal stop for the rest of the pipeline.

        This method records a ``HaltState`` on the context so that subsequent
        steps and the runner can avoid further processing for this file.

        The context's ``halt_state`` field is updated in place.

        Args:
            reason: Short machine-friendly reason code for halting the
                pipeline (for example, ``"unsupported"``).
            at_step: Step instance requesting the halt.
        """
        logger.info("🛑 Processing halted in %s: %s", at_step.name, reason)
        self.halt_state = HaltState(reason_code=reason, step_name=at_step.name)

    @property
    def is_halted(self) -> bool:
        """Return True if a step has requested an early halt for this file.

        Returns:
            ``True`` when ``halt_state`` is not ``None``, meaning that
            the pipeline should not execute any further steps for this file.
        """
        return self.halt_state is not None

    # TODO: decide to keep or always refer to FileImageViewiter_lines() instead.
    def iter_image_lines(self) -> Iterable[str]:
        """Iterate the current file image without materializing.

        This accessor hides the underlying representation (list-backed, mmap-backed,
        or generator-based) and returns an iterator over logical lines with original
        newline sequences preserved.

        Returns:
            An iterator over the file's lines. If no image is present,
            an empty iterator is returned.
        """
        if self.views.image is not None:
            return self.views.image.iter_lines()
        return iter(())  # empty

    def image_line_count(self) -> int:
        """Return the number of logical lines without materializing.

        Returns:
            Total number of lines in the current image, or ``0`` if no image is present.
        """
        if self.views.image is not None:
            return self.views.image.line_count()
        return 0

    def iter_updated_lines(self) -> Iterable[str]:
        """Iterate the updated file image lines, if present.

        Returns:
            Iterator over updated lines. If no updated image is available (no planner/strip output),
            returns an empty iterator.
        """
        uv: UpdatedView | None = self.views.updated
        if not uv or uv.lines is None:
            return iter(())
        seq_or_it: Sequence[str] | Iterable[str] = uv.lines
        # If it's already a concrete sequence, avoid copying:
        if isinstance(seq_or_it, (list, tuple)):
            return iter(seq_or_it)
        # Fallback: it's an arbitrary iterable (possibly a generator)
        return iter(seq_or_it)

    def materialize_image_lines(self) -> list[str]:
        """Return the original file image as a materialized list of lines.

        Returns:
            List of logical lines from the current image view. An empty list is returned if no image
            is available.
        """
        return list(self.iter_image_lines())

    def materialize_updated_lines(self) -> list[str]:
        """Return the updated file image as a materialized list of lines.

        Returns:
            List of updated lines if present, otherwise an empty list.
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
            A JSON-serializable mapping describing the context, including path, file type,
            step statuses, views summary, diagnostics, and high-level outcome flags.
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
            "diagnostic_counts": self.diagnostics.to_dict(),
            "pre_insert_check": {
                "capability": self.pre_insert_capability.name,
                "reason": self.pre_insert_reason,
                "origin": self.pre_insert_origin,
            },
            "outcome": {
                "would_change": would_change(self),
                "can_change": can_change(self),
                "permitted_by_policy": check_permitted_by_policy(self),
                "check": {
                    "would_add_or_update": would_add_or_update(self),
                    "effective_would_add_or_update": effective_would_add_or_update(self),
                },
                "strip": {
                    "would_strip": would_strip(self),
                    "effective_would_strip": effective_would_strip(self),
                },
            },
        }

    def info(self, message: str) -> None:
        """Record an informational diagnostic for this context."""
        self.diagnostics.add_info(message)

    def warn(self, message: str) -> None:
        """Record a warning diagnostic for this context."""
        self.diagnostics.add_warning(message)

    def error(self, message: str) -> None:
        """Record an error diagnostic for this context."""
        self.diagnostics.add_error(message)

    def hint(
        self,
        *,
        axis: Axis,
        code: KnownCode | str,
        message: str,
        detail: str | None = None,
        cluster: Cluster | str | None = None,
        terminal: bool = False,
        reason: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Create and attach a normalized `Hint` to this context.

        This is a convenience façade around `make_hint` and `HintLog.add`,
        allowing pipeline steps to emit structured, non-binding diagnostics
        without depending on the underlying `HintLog` representation.

        The new hint is appended to this context's hint log.

        Args:
            axis: Axis emitting the hint.
            code: Stable machine key for the condition.
            message: Human-readable short summary line.
            detail: Optional extended diagnostic text rendered at higher verbosity
                (e.g., multi-line config snippets or rationale).
            cluster: Optional grouping key; defaults to ``code``.
            terminal: Whether this condition is terminal.
            reason: Optional detail string.
            meta: Optional extensibility bag.

        Example:
            ```python
            ctx.hint(axis=Axis.PLAN, code=KnownCode.PLAN_INSERT, message="would insert header")
            ```
        """
        self.diagnostic_hints.add(
            make_hint(
                axis=axis,
                code=code,
                message=message,
                detail=detail,
                cluster=cluster,
                terminal=terminal,
                reason=reason,
                meta=meta,
            )
        )

    @classmethod
    def bootstrap(
        cls,
        *,
        path: Path,
        config: Config,
        policy_registry_override: PolicyRegistry | None = None,
    ) -> ProcessingContext:
        """Create a fresh context with no derived state.

        Args:
            path: File system path for the file to process.
            config: Effective configuration to attach to the context.
            policy_registry_override: Optional policy registry override providing precomputed
                effective policies per file type for this run. If not set, then the policy
                registry

        Returns:
            Newly created context instance.
        """
        if policy_registry_override is None:
            reg: PolicyRegistry = make_policy_registry(config)
        else:
            reg = policy_registry_override
        return cls(path=path, config=config, policy_registry=reg)
