# topmark:header:start
#
#   project      : TopMark
#   file         : model.py
#   file_relpath : src/topmark/runtime/model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Execution-only runtime models.

This package holds values that describe invocation intent for a single
TopMark run. These values do not participate in layered config discovery,
per-path effective config resolution, or file-backed merge semantics.

The initial runtime split introduces `RunOptions` as the authoritative home
for execution-only concerns such as apply mode, stdin handling, output
routing, file-write strategy, and run timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Protocol

from topmark.utils.timestamp import get_utc_now

if TYPE_CHECKING:
    from datetime import datetime

    from topmark.config.types import FileWriteStrategy
    from topmark.config.types import OutputTarget
    from topmark.pipeline.kinds import PipelineKindLiteral


class _PipelineSelectionLike(Protocol):
    """Structural subset of pipeline selection data needed by `RunOptions`.

    The runtime model deliberately avoids importing
    [`PipelineSelection`][topmark.pipeline.pipelines.PipelineSelection] so that
    execution-only runtime state does not depend on the concrete pipeline
    catalogue or step modules.
    """

    @property
    def kind(self) -> PipelineKindLiteral:
        """Pipeline kind."""
        ...

    @property
    def apply(self) -> bool:
        """Whether the pipeline should write changes."""
        ...

    @property
    def diff(self) -> bool:
        """Whether the pipeline generates a diff."""
        ...


@dataclass(frozen=True, kw_only=True, slots=True)
class RunOptions:
    """Execution-only options for a single TopMark run.

    This value carries invocation intent that does not participate in layered
    config discovery or per-path effective config resolution.

    Attributes:
        pipeline_kind: the pipeline kind (`check`, `strip`, `probe`).
        apply_changes: Whether the run should write changes (`True`) or preview
            only (`False`).
        output_target: Where output should be emitted for this run.
        file_write_strategy: How file writes should be performed when
            `output_target` targets files.
        stdin_mode: Whether content is being provided on stdin for this run.
        stdin_filename: Synthetic filename associated with stdin content, used
            when header generation requires a file identity.
        prune_views: If True, release consumed volatile views between pipeline steps.
        keep_diff_view: Whether to preserve the diff view.
        started_at: Timestamp captured once for the whole run.
    """

    pipeline_kind: PipelineKindLiteral | None = None
    apply_changes: bool | None = None
    output_target: OutputTarget | None = None
    file_write_strategy: FileWriteStrategy | None = None
    stdin_mode: bool = False
    stdin_filename: str | None = None
    prune_views: bool = True
    keep_diff_view: bool = False

    started_at: datetime = field(default_factory=get_utc_now)

    @classmethod
    def from_pipeline_selection(
        cls,
        selection: _PipelineSelectionLike,
        *,
        output_target: OutputTarget | None = None,
        file_write_strategy: FileWriteStrategy | None = None,
        stdin_mode: bool = False,
        stdin_filename: str | None = None,
        prune_views: bool = True,
        started_at: datetime | None = None,
    ) -> RunOptions:
        """Build runtime options from a selected pipeline.

        This helper keeps duplicated invocation state synchronized between a
        selected pipeline and `RunOptions` without importing the concrete
        pipeline catalogue into the runtime model. Pipeline selection remains
        the short-lived executable choice, while `RunOptions` remains the
        durable runtime state copied onto processing contexts and reduced into
        processing results.

        The selected pipeline supplies the overlapping execution intent:
        `selection.kind` becomes `pipeline_kind`, `selection.apply` becomes
        `apply_changes`, and `selection.diff` becomes `keep_diff_view`. In other
        words, mutation mode and diff-view preservation are derived from the
        selected pipeline rather than repeated by the caller.

        Args:
            selection: Selected pipeline data exposing the pipeline kind,
                mutation flag, and diff-preservation flag.
            output_target: Where output should be emitted for this run.
            file_write_strategy: How file writes should be performed when
                `output_target` targets files.
            stdin_mode: Whether content is being provided on stdin for this run.
            stdin_filename: Synthetic filename associated with stdin content.
            prune_views: If True, release consumed volatile views between pipeline steps.
            started_at: Optional timestamp captured once for the whole run. When
                omitted, the normal `RunOptions` timestamp factory is used.

        Returns:
            Runtime options whose overlapping fields are derived from
            `selection`.
        """
        return cls(
            pipeline_kind=selection.kind,
            apply_changes=selection.apply,
            stdin_mode=stdin_mode,
            stdin_filename=stdin_filename,
            output_target=output_target,
            file_write_strategy=file_write_strategy,
            prune_views=prune_views,
            keep_diff_view=selection.diff,
            started_at=started_at or get_utc_now(),
        )
