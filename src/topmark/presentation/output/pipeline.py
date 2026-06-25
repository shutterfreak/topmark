# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/presentation/output/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline command output orchestration for human output formats.

This module coordinates format-specific pipeline renderers when a command needs
separate output streams. The concrete TEXT and Markdown renderers remain
responsible for formatting one stream at a time, while this facade decides which
rendered content belongs in the payload stream and which content belongs in the
human-report stream.

The split is intentionally independent from Click and Rich console objects. CLI
commands receive a value object and perform the actual writes themselves. This
keeps command modules small while leaving room for a later streaming
presentation-event model.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from topmark.core.formats import OutputFormat
from topmark.presentation.markdown.pipeline import render_pipeline_diffs_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_output_markdown
from topmark.presentation.shared.pipeline import PipelineCommandHumanOutput
from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
from topmark.presentation.text.pipeline import render_pipeline_diffs_text
from topmark.presentation.text.pipeline import render_pipeline_output_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.result import ProcessingResult


def _without_embedded_diffs(
    report: PipelineCommandHumanReport,
) -> PipelineCommandHumanReport:
    """Return a report copy with embedded diff-section rendering disabled.

    Args:
        report: Prepared human report.

    Returns:
        Report copy that renders only status, guidance, and summary output.
    """
    return replace(report, show_diffs=False)


def render_pipeline_command_human_output(
    *,
    report: PipelineCommandHumanReport,
    results: Sequence[ProcessingResult],
    fmt: OutputFormat,
) -> PipelineCommandHumanOutput:
    """Render human pipeline command output split by target stream.

    Args:
        report: Prepared human report for status, guidance, and summary output.
            When `report.show_diffs` is true, diffs are rendered as separate
            payload output instead of being embedded in the report output.
        results: Full durable processing results used for diff payload rendering.
            This intentionally ignores `report.view_results` so `--report` only
            affects per-file report visibility, not diff visibility.
        fmt: Selected human output format.

    Returns:
        Rendered output split into payload and human-report content. Commands
        decide which concrete streams receive these strings.

    Raises:
        RuntimeError: If an unsupported human output format is selected.
    """
    report_without_diffs: PipelineCommandHumanReport = _without_embedded_diffs(report)

    if fmt == OutputFormat.TEXT:
        stdout: str = (
            render_pipeline_diffs_text(
                results=results,
                styled=report.styled,
            )
            if report.show_diffs
            else ""
        )
        stderr: str = render_pipeline_output_text(report_without_diffs)
    elif fmt == OutputFormat.MARKDOWN:
        stdout = render_pipeline_diffs_markdown(results=results) if report.show_diffs else ""
        stderr = render_pipeline_output_markdown(report_without_diffs)
    else:
        msg: str = f"Unsupported human output format: {fmt.value}"
        raise RuntimeError(msg)

    return PipelineCommandHumanOutput(stdout=stdout, stderr=stderr)
