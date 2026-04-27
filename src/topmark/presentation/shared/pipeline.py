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

if TYPE_CHECKING:
    from topmark.api.types import PipelineKindLiteral
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.reporting import ReportScope


@dataclass(frozen=True, slots=True, kw_only=True)
class ProbeCommandHumanReport:
    """Prepared payload for human-facing pipeline probe command renderers.

    The report is shared by human-facing renderers for `topmark probe`. It
    contains only presentation-ready data and policy flags; it does not perform
    rendering, Click interaction, or console output.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        cmd: Command name, usually `probe`.
        file_list_total: Total number of candidate files before view filtering.
        view_results: Processing contexts selected for the current human-output view.
    """

    verbosity_level: int
    styled: bool
    cmd: str
    file_list_total: int
    view_results: list[ProcessingContext]


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineCommandHumanReport:
    """Prepared payload for human-facing pipeline command renderers.

    The report is shared by TEXT and Markdown renderers for `topmark check` and
    `topmark strip`. It contains only presentation-ready data and policy flags;
    it does not perform rendering, Click interaction, or console output.

    Attributes:
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.
        cmd: Command name, such as `check` or `strip`.
        pipeline_kind: Pipeline kind used to select command-specific guidance.
        file_list_total: Total number of candidate files before view filtering.
        view_results: Processing contexts selected for the current human-output view.
        report_scope: Active report scope for the current view.
        unsupported_count: Number of unsupported files omitted from actionable listings.
        summary_mode: Whether to render grouped outcome counts instead of per-file sections.
        show_diffs: Whether to include unified diffs.
        apply_changes: Whether the command runs in apply mode.
    """

    verbosity_level: int
    styled: bool
    cmd: str
    pipeline_kind: PipelineKindLiteral
    file_list_total: int
    view_results: list[ProcessingContext]
    report_scope: ReportScope
    unsupported_count: int
    summary_mode: bool
    show_diffs: bool
    apply_changes: bool


def get_display_path(
    r: ProcessingContext,
) -> str:
    """Return the user-facing path to display for a processing result.

    TopMark may process *content-on-STDIN* by writing it to a temporary file.
    In that mode, `ProcessingContext.path` points at the temporary file on disk,
    but users expect messages to refer to the logical filename supplied via
    `--stdin-filename`.

    This helper centralizes that policy so all human-facing renderers (TEXT and
    Markdown) display the same path labels.

    Args:
        r: Processing context to render.

    Returns:
        The logical filename in STDIN content mode, otherwise the actual file path.
    """
    if r.run_options.stdin_mode and bool(r.run_options.stdin_filename):
        return r.run_options.stdin_filename
    return str(r.path)
