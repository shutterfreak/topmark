# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/presentation/shared/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared pipeline presentation models and utilities (Click-free).

This module defines the presentation payload shared by human-facing pipeline
renderers for `topmark check` and `topmark strip`.

Scope:
    - Provide immutable report models consumed by TEXT and Markdown renderers.
    - Centralize small display helpers that must remain consistent across human
      formats.
    - Avoid Click, console, and I/O dependencies; callers are responsible for
      building reports, rendering strings, and printing output.

TEXT renderers may use `verbosity_level` and `styled` for console-oriented
progressive disclosure. Markdown renderers treat Markdown as document-oriented
output and ignore TEXT-only verbosity and styling controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.pipeline.status import FsStatus

if TYPE_CHECKING:
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.reporting import ReportScope


@dataclass(frozen=True, kw_only=True, slots=True)
class ProbeCommandHumanReport:
    """Prepared payload for human-facing pipeline probe command renderers.

    The report is shared by human-facing renderers for `topmark probe`. It
    contains only presentation-ready data and policy flags; it does not perform
    rendering, Click interaction, or console output.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        pipeline_kind: Pipeline kind used to select command-specific guidance.
        file_list_total: Total number of candidate files before view filtering.
        view_results: Processing contexts selected for the current human-output view.
    """

    verbosity_level: int
    styled: bool
    pipeline_kind: PipelineKindLiteral
    file_list_total: int
    view_results: list[ProcessingContext]


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineCommandHumanReport:
    """Prepared payload for human-facing pipeline command renderers.

    The report is shared by TEXT and Markdown renderers for `topmark check` and
    `topmark strip`. It contains only presentation-ready data and policy flags;
    it does not perform rendering, Click interaction, or console output.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        pipeline_kind: Pipeline kind used to select command-specific guidance.
        file_list_total: Total number of user-requested results before view filtering,
            including selected pipeline files and synthetic resolver-level outcomes.
        view_results: Processing contexts selected for the current human-output view.
        report_scope: Active report scope for the current view.
        unsupported_count: Number of unsupported files omitted from actionable listings.
        summary_mode: Whether to render grouped outcome counts instead of per-file sections.
        show_diffs: Whether to include unified diffs.
        apply_changes: Whether the command runs in apply mode.
    """

    verbosity_level: int
    styled: bool
    pipeline_kind: PipelineKindLiteral
    file_list_total: int
    view_results: list[ProcessingContext]
    report_scope: ReportScope
    unsupported_count: int
    summary_mode: bool
    show_diffs: bool
    apply_changes: bool


def get_file_type_label(ctx: ProcessingContext) -> str | None:
    """Return the human-facing file-type label for a pipeline result.

    Resolved files use their local file-type key. Unresolved files usually render
    as ``<unknown>`` so users can see that type resolution did not complete.
    Synthetic missing-file contexts are the exception: they are created by file
    resolution before type resolution can run, so they omit the file-type segment
    entirely.

    This keeps missing-file output concise:

    ```text
    fubar: error: not_found
    ```

    while still preserving useful context if a file was resolved before a later
    filesystem failure.

    Args:
        ctx: Processing context to inspect.

    Returns:
        File-type label for human output, or `None` when the file-type segment
        should be omitted.
    """
    if ctx.file_type is not None:
        return ctx.file_type.local_key
    if ctx.status.fs == FsStatus.NOT_FOUND:
        return None
    return "<unknown>"
