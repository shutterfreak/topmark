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
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import MachineRunCompletedEvent
from topmark.pipeline.machine.streaming import MachineRunStartedEvent
from topmark.pipeline.reporting import filter_results_for_report
from topmark.presentation.markdown.pipeline import render_pipeline_diffs_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_output_markdown
from topmark.presentation.shared.pipeline import PipelineCommandHumanOutput
from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
from topmark.presentation.text.pipeline import render_pipeline_diffs_text
from topmark.presentation.text.pipeline import render_pipeline_output_text

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Sequence

    from topmark.pipeline.machine.streaming import MachineProcessingStreamEvent
    from topmark.pipeline.reporting import ReportFilterResult
    from topmark.pipeline.result import ProcessingResult
    from topmark.presentation.shared.pipeline import PipelineHumanPresentationOptions


def _collect_stream_results(
    events: Iterable[MachineProcessingStreamEvent],
    *,
    options: PipelineHumanPresentationOptions,
) -> tuple[ProcessingResult, ...]:
    """Collect durable processing results from an internal presentation stream.

    Args:
        events: Internal stream events carrying durable processing results.
        options: Human presentation options whose pipeline kind must match the stream.

    Returns:
        Durable processing results in stream order.

    Raises:
        ValueError: If the stream lifecycle, command identity, or per-file index
            ordering is malformed.
    """
    started: bool = False
    completed: bool = False
    expected_index: int = 0
    results: list[ProcessingResult] = []

    # These checks are intentionally defensive. The internal machine stream
    # adapter normally emits a single well-ordered stream for one command, but
    # the human facade validates the lifecycle boundary so corrupted or manually
    # assembled streams fail before presentation can silently drop or reorder
    # durable results.

    for event in events:
        match event:
            case MachineRunStartedEvent(command=options.pipeline_kind):
                if completed:
                    raise ValueError(
                        "Human presentation run-start event appeared after run-completed."
                    )
                if started:
                    raise ValueError(
                        "Human presentation stream contains more than one run-start event."
                    )
                started = True
            case MachineProcessingResultEvent(command=options.pipeline_kind):
                if not started:
                    raise ValueError(
                        "Human presentation file-result event appeared before run-start."
                    )
                if completed:
                    raise ValueError(
                        "Human presentation file-result event appeared after run-completed."
                    )
                if event.index != expected_index:
                    raise ValueError(
                        f"Expected human presentation file-result index {expected_index}, "
                        f"got {event.index}."
                    )
                expected_index += 1
                results.append(event.result)
            case MachineRunCompletedEvent(command=options.pipeline_kind):
                if not started:
                    raise ValueError(
                        "Human presentation run-completed event appeared before run-start."
                    )
                if completed:
                    raise ValueError(
                        "Human presentation stream contains more than one run-completed event."
                    )
                completed = True
            case _:
                raise ValueError(
                    "Human presentation stream contains an event for a different command."
                )

    if not started:
        raise ValueError("Human presentation stream is missing a run-start event.")
    if not completed:
        raise ValueError("Human presentation stream is missing a run-completed event.")

    return tuple(results)


def _report_for_stream_results(
    *,
    options: PipelineHumanPresentationOptions,
    results: Sequence[ProcessingResult],
    would_change: Callable[[ProcessingResult], bool],
) -> PipelineCommandHumanReport:
    """Return a human report whose view is derived from stream results.

    Args:
        options: Presentation configuration and report-scope policy.
        results: Durable processing results collected from the presentation stream.
        would_change: Command-specific actionable predicate for report filtering.

    Returns:
        Report with stream-derived file totals, view results, and hidden
        unsupported counts. Summary mode intentionally uses the full result set
        so grouped counts are not distorted by report-scope filtering.
    """
    filtered: ReportFilterResult[ProcessingResult] = filter_results_for_report(
        results,
        report_scope=options.report_scope,
        would_change=would_change,
    )
    human_results: Sequence[ProcessingResult] = (
        results if options.summary_mode else filtered.view_results
    )
    return PipelineCommandHumanReport(
        pipeline_kind=options.pipeline_kind,
        file_list_total=len(results),
        view_results=human_results,
        report_scope=options.report_scope,
        unsupported_count=filtered.unsupported_count_all,
        verbosity_level=options.verbosity_level,
        summary_mode=options.summary_mode,
        show_diffs=options.show_diffs,
        apply_changes=options.apply_changes,
        styled=options.styled,
    )


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


def render_pipeline_command_human_stream_output(
    *,
    options: PipelineHumanPresentationOptions,
    events: Iterable[MachineProcessingStreamEvent],
    fmt: OutputFormat,
    would_change: Callable[[ProcessingResult], bool],
) -> PipelineCommandHumanOutput:
    """Render human pipeline command output from an internal result stream.

    Args:
        options: Human presentation configuration. The stream-derived result set
            determines totals, filtering, and diff ordering.
        events: Internal durable-result stream in deterministic processing order.
        fmt: Selected human output format.
        would_change: Command-specific actionable predicate for report filtering.

    Returns:
        Rendered output split into payload and human-report content.
    """
    results: tuple[ProcessingResult, ...] = _collect_stream_results(
        events,
        options=options,
    )
    stream_report: PipelineCommandHumanReport = _report_for_stream_results(
        options=options,
        results=results,
        would_change=would_change,
    )
    return render_pipeline_command_human_output(
        report=stream_report,
        results=results,
        fmt=fmt,
    )
