# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline.py
#   file_relpath : src/topmark/api/commands/pipeline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Programmatic pipeline entry points (public API).

This module exposes `probe()`, `check()`, and `strip()` as typed functions mirroring
the CLI commands (`topmark probe`, `topmark check`, `topmark strip`) without Click.

Call styles:
- Discovery mode: pass `config=None` to discover and merge config layers.
- Seeded mode: pass a plain mapping via `config=` to skip discovery and use that seed.

Notes:
- These functions choose the concrete pipeline, build execution-only run options,
  and delegate runtime setup/execution to [`topmark.api.runtime`][topmark.api.runtime] helpers.
- Runtime helpers reduce mutable execution contexts to durable processing results
  before this module assembles public DTOs in the view layer.
- `check()` and `strip()` apply public report-scope filtering in the common run
  finalizer. `probe()` uses the probe-specific finalizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Final
from typing import Literal

from topmark.api.runtime import run_pipeline_results
from topmark.api.runtime import run_probe_pipeline_results
from topmark.api.types import FileResultEvent
from topmark.api.types import ProbeFileResultEvent
from topmark.api.types import RunCompletedEvent
from topmark.api.types import RunStartedEvent
from topmark.api.view import finalize_probe_result
from topmark.api.view import finalize_run_result
from topmark.core.errors import InvalidReportScopeError
from topmark.pipeline.pipelines import PipelineSelection
from topmark.pipeline.pipelines import select_pipeline
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.reporting import would_add_or_update_result
from topmark.pipeline.reporting import would_strip_result
from topmark.pipeline.status import PlanStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Mapping
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.api.runtime import ApiPipelineResultRun
    from topmark.api.types import ContentStreamEvent
    from topmark.api.types import ProbeRunResult
    from topmark.api.types import ProbeStreamEvent
    from topmark.api.types import PublicPolicy
    from topmark.api.types import PublicReportScopeLiteral
    from topmark.api.types import RunResult
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.result import ProcessingResult

__all__ = (
    "check",
    "probe",
    "stream_check",
    "stream_probe",
    "stream_strip",
    "strip",
)

_CHECK_UPDATE_STATUSES: Final[frozenset[PlanStatus]] = frozenset(
    {
        PlanStatus.INSERTED,
        PlanStatus.REPLACED,
        PlanStatus.REMOVED,
    }
)

_STRIP_UPDATE_STATUSES: Final[frozenset[PlanStatus]] = frozenset(
    {
        PlanStatus.REMOVED,
    }
)


@dataclass(frozen=True, slots=True)
class _ContentPipelineRun:
    """Internal result of a content-processing pipeline execution.

    This value groups the finalized public run result together with the ordered
    selected file list used to construct streaming run-start events.

    Attributes:
        result: Finalized public batch API result.
        selected_paths: Ordered real file paths selected for pipeline execution.
    """

    result: RunResult
    selected_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class _ProbePipelineRun:
    """Internal result of a probe pipeline execution.

    This value groups the finalized public probe result together with the ordered
    selected file list used to construct streaming run-start events.

    Attributes:
        result: Finalized public probe API result.
        selected_paths: Ordered real file paths selected for probe execution.
    """

    result: ProbeRunResult
    selected_paths: tuple[Path, ...]


def _resolve_public_report_scope(
    value: PublicReportScopeLiteral,
) -> ReportScope:
    """Return the internal report-scope enum for a public API token.

    Args:
        value: Public report-scope literal supplied by an API caller.

    Returns:
        Internal report-scope enum used by the API view layer.

    Raises:
        InvalidReportScopeError: If `value` is not one of the public report-scope tokens.
    """
    try:
        return ReportScope(value)
    except ValueError as exc:
        raise InvalidReportScopeError(
            message=f"Invalid value for report: {value!r}",
            report_value=value,
        ) from exc


def _iter_content_events(
    *,
    command: Literal["check", "strip"],
    run: _ContentPipelineRun,
) -> Iterator[ContentStreamEvent]:
    """Yield public content stream events for a finalized run result.

    Args:
        command: Public command that produced the stream.
        run: Finalized content pipeline run for the same invocation.

    Yields:
        Public streaming events in deterministic run order.
    """
    yield RunStartedEvent(
        kind="run_started",
        command=command,
        selected_count=len(run.selected_paths),
        paths=tuple(run.selected_paths),
    )
    for index, file_result in enumerate(run.result.files):
        yield FileResultEvent(
            kind="file_result",
            command=command,
            index=index,
            result=file_result,
        )
    yield RunCompletedEvent(
        kind="run_completed",
        command=command,
        summary=run.result.summary,
        had_errors=run.result.had_errors,
        skipped=run.result.skipped,
        written=run.result.written,
        failed=run.result.failed,
        diagnostic_totals=run.result.diagnostic_totals,
        diagnostic_totals_all=run.result.diagnostic_totals_all,
    )


def _iter_probe_events(
    *,
    run: _ProbePipelineRun,
) -> Iterator[ProbeStreamEvent]:
    """Yield public probe stream events for a finalized probe result.

    Args:
        run: Finalized probe pipeline run for the same invocation.

    Yields:
        Public probe streaming events in deterministic run order.
    """
    yield RunStartedEvent(
        kind="run_started",
        command="probe",
        selected_count=len(run.selected_paths),
        paths=tuple(run.selected_paths),
    )
    for index, file_result in enumerate(run.result.files):
        yield ProbeFileResultEvent(
            kind="file_result",
            command="probe",
            index=index,
            result=file_result,
        )
    yield RunCompletedEvent(
        kind="run_completed",
        command="probe",
        summary=run.result.summary,
        had_errors=run.result.had_errors,
        diagnostic_totals=run.result.diagnostic_totals,
    )


def _run_probe_pipeline(
    paths: Iterable[Path | str],
    *,
    config: Mapping[str, object] | None,
    policy: PublicPolicy | None,
    policy_by_type: Mapping[str, PublicPolicy] | None,
    include_file_types: Sequence[str] | None,
    exclude_file_types: Sequence[str] | None,
    prune_views: bool,
) -> _ProbePipelineRun:
    """Run the probe pipeline and assemble the public result DTO.

    Args:
        paths: Files and/or directories to probe.
        config: Optional plain mapping or immutable configuration object used as
            the runtime configuration seed.
        policy: Optional global policy overrides in the public API shape.
        policy_by_type: Optional per-type policy overrides in the public API shape.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        prune_views: If True, release consumed volatile views between pipeline steps.

    Returns:
        Finalized public probe result and the ordered selected real file paths.
    """
    # Probe has a single read-only diagnostic pipeline. Runtime helpers also
    # attach synthetic durable results for missing literals and explicit inputs
    # filtered before real probe execution.
    pipeline: PipelineSelection = select_pipeline(
        "probe",
        apply=False,
        diff=False,
    )

    run_options: RunOptions = RunOptions.from_pipeline_selection(
        selection=pipeline,
        prune_views=prune_views,
    )

    api_run: ApiPipelineResultRun = run_probe_pipeline_results(
        pipeline=pipeline,
        paths=paths,
        run_options=run_options,
        base_config=config,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        policy=policy,
        policy_by_type=policy_by_type,
    )

    return _ProbePipelineRun(
        result=finalize_probe_result(
            results=api_run.results,
            file_list=api_run.file_list,
            encountered_exit_code=api_run.exit_code,
        ),
        selected_paths=tuple(api_run.file_list),
    )


def _run_content_pipeline(
    paths: Iterable[Path | str],
    *,
    pipeline_kind: PipelineKindLiteral,
    apply: bool,
    diff: bool,
    config: Mapping[str, object] | None,
    policy: PublicPolicy | None,
    policy_by_type: Mapping[str, PublicPolicy] | None,
    include_file_types: Sequence[str] | None,
    exclude_file_types: Sequence[str] | None,
    report: PublicReportScopeLiteral,
    would_change: Callable[[ProcessingResult], bool],
    prune_views: bool,
    update_statuses: frozenset[PlanStatus],
) -> _ContentPipelineRun:
    """Run a content-processing pipeline and assemble the public result DTO.

    Args:
        paths: Files and/or directories to process.
        pipeline_kind: Selected public pipeline family, either `check` or `strip`.
        apply: If `True`, write changes in-place; otherwise perform a dry run.
        diff: If `True`, include unified diffs for changes where applicable.
        config: Optional plain mapping or immutable configuration object used as
            the runtime configuration seed.
        policy: Optional global policy overrides in the public API shape.
        policy_by_type: Optional per-type policy overrides in the public API shape.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        report: Reporting scope for the returned API view.
        would_change: Command-specific predicate describing whether a result is
            actionable for the selected pipeline intent. `check()` passes an
            add/update predicate; `strip()` passes a strip predicate. Pass
            [`would_change_result`][topmark.pipeline.reporting.would_change_result]
            for command-neutral reporting.
        prune_views: If True, release consumed volatile views between pipeline steps.
        update_statuses: Plan statuses counted as write/update candidates by the
            public result finalizer.

    Returns:
        Filtered per-file outcomes, counts, diagnostics, write stats, and the
        ordered selected real file paths.
    """
    # Choose the concrete content-processing pipeline variant.
    pipeline: PipelineSelection = select_pipeline(
        pipeline_kind,
        apply=apply,
        diff=diff,
    )

    # Run the pipeline; runtime helpers handle config discovery, policy overlays,
    # file-list resolution, per-path config, and pipeline execution.

    run_options: RunOptions = RunOptions.from_pipeline_selection(
        pipeline,
        prune_views=prune_views,
    )

    api_run: ApiPipelineResultRun = run_pipeline_results(
        pipeline=pipeline,
        paths=paths,
        run_options=run_options,
        base_config=config,  # None preserves discovery; mapping/Config is honored.
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        policy=policy,
        policy_by_type=policy_by_type,
    )

    report_scope: ReportScope = _resolve_public_report_scope(report)

    return _ContentPipelineRun(
        result=finalize_run_result(
            results=api_run.results,
            file_list=api_run.file_list,
            apply=apply,
            report_scope=report_scope,
            would_change=would_change,
            update_statuses=update_statuses,
            encountered_exit_code=api_run.exit_code,
        ),
        selected_paths=tuple(api_run.file_list),
    )


def check(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    diff: bool = False,
    config: Mapping[str, object] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    report: PublicReportScopeLiteral = "actionable",
    prune_views: bool = False,
) -> RunResult:
    """Validate or apply TopMark headers for the given paths.

    This is the programmatic equivalent of the CLI `topmark check`. It preserves
    the same discovery behavior when `config` is `None` and accepts optional
    policy overlays that are applied after discovery, before the pipeline runs.

    Args:
        paths: Files and/or directories to process. Globs are allowed by the caller;
            TopMark will recurse and filter internally.
        apply: If `True`, write changes in-place; otherwise perform a dry run.
        diff: If `True`, include unified diffs for changes where applicable.
        config: Optional plain mapping or immutable
            [`FrozenConfig`][topmark.config.model.FrozenConfig] to seed configuration.
            When `None`, project discovery and layered merge are performed.
        policy: Optional global policy overrides in the public API shape. These
            are merged after discovery using standard policy resolution.
        policy_by_type: Optional per-type policy overrides in the public API shape,
            merged after discovery.
        include_file_types: Optional whitelist of file type identifiers to restrict discovery.
        exclude_file_types: Optional blacklist of file type identifiers to exclude from discovery.
        report: Reporting scope for the returned API view (`actionable`,
            `noncompliant`, or `all`).
        prune_views: If True, release consumed volatile views between pipeline steps.

    Returns:
        Filtered per-file outcomes, counts, diagnostics, and write stats.

    Notes:
        Reporting/view filtering is handled by the public view layer. It does not
        change which files are eligible to be written when `apply=True`.
    """
    result: _ContentPipelineRun = _run_content_pipeline(
        paths,
        pipeline_kind="check",
        apply=apply,
        diff=diff,
        config=config,
        policy=policy,
        policy_by_type=policy_by_type,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        report=report,
        would_change=would_add_or_update_result,
        prune_views=prune_views,
        update_statuses=_CHECK_UPDATE_STATUSES,
    )
    return result.result


def stream_check(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    diff: bool = False,
    config: Mapping[str, object] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    report: PublicReportScopeLiteral = "actionable",
    prune_views: bool = False,
) -> Iterator[ContentStreamEvent]:
    """Stream public events for a `check()` invocation.

    The emitted file-result events use the same public `FileResult` DTOs and
    report-scope filtering semantics as `check()`. Ordering is deterministic:
    one run-start event, zero or more file-result events, then one run-completed
    event.
    """
    result: _ContentPipelineRun = _run_content_pipeline(
        paths,
        pipeline_kind="check",
        apply=apply,
        diff=diff,
        config=config,
        policy=policy,
        policy_by_type=policy_by_type,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        report=report,
        would_change=would_add_or_update_result,
        prune_views=prune_views,
        update_statuses=_CHECK_UPDATE_STATUSES,
    )
    yield from _iter_content_events(
        command="check",
        run=result,
    )


def strip(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    diff: bool = False,
    config: Mapping[str, object] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    report: PublicReportScopeLiteral = "actionable",
    prune_views: bool = False,
) -> RunResult:
    """Remove TopMark headers from files (dry-run or apply).

    This is the programmatic equivalent of the CLI `topmark strip`. When `config`
    is `None`, the function performs the same project discovery as the CLI and
    then applies optional policy overlays before running the pipeline.

    Args:
        paths: Files and/or directories to process. Globs are allowed.
        apply: If `True`, write changes in-place; otherwise perform a dry run.
        diff: If `True`, include unified diffs for changes where applicable.
        config: Optional plain mapping or immutable
            [`FrozenConfig`][topmark.config.model.FrozenConfig] to seed configuration.
            When `None`, project discovery and layered merge are performed.
        policy: Optional global policy overrides in the public API shape. Strip
            flows are currently policy-agnostic, but this is accepted for forward
            compatibility.
        policy_by_type: Optional per-type policy overrides in the public API shape.
        include_file_types: Optional whitelist of file type identifiers to restrict discovery.
        exclude_file_types: Optional blacklist of file type identifiers to exclude from discovery.
        report: Reporting scope for the returned API view (`actionable`,
            `noncompliant`, or `all`).
        prune_views: If True, release consumed volatile views between pipeline steps.

    Returns:
        Filtered per-file outcomes, counts, diagnostics, and write stats.

    Notes:
        Reporting/view filtering is handled by the public view layer and does not
        modify pipeline write decisions.
    """
    result: _ContentPipelineRun = _run_content_pipeline(
        paths,
        pipeline_kind="strip",
        apply=apply,
        diff=diff,
        config=config,
        policy=policy,
        policy_by_type=policy_by_type,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        report=report,
        would_change=would_strip_result,
        prune_views=prune_views,
        update_statuses=_STRIP_UPDATE_STATUSES,
    )
    return result.result


def stream_strip(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    diff: bool = False,
    config: Mapping[str, object] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    report: PublicReportScopeLiteral = "actionable",
    prune_views: bool = False,
) -> Iterator[ContentStreamEvent]:
    """Stream public events for a `strip()` invocation.

    The emitted file-result events use the same public `FileResult` DTOs and
    report-scope filtering semantics as `strip()`. Ordering is deterministic:
    one run-start event, zero or more file-result events, then one run-completed
    event.
    """
    result: _ContentPipelineRun = _run_content_pipeline(
        paths,
        pipeline_kind="strip",
        apply=apply,
        diff=diff,
        config=config,
        policy=policy,
        policy_by_type=policy_by_type,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        report=report,
        would_change=would_strip_result,
        prune_views=prune_views,
        update_statuses=_STRIP_UPDATE_STATUSES,
    )
    yield from _iter_content_events(
        command="strip",
        run=result,
    )


def probe(
    paths: Iterable[Path | str],
    *,
    config: Mapping[str, object] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    prune_views: bool = False,
) -> ProbeRunResult:
    """Explain how paths resolve to TopMark file types and processors.

    This is the programmatic equivalent of the CLI `topmark probe`. It runs the
    read-only probe pipeline and returns a stable public view of file-type
    resolution, selected processors, and normalized candidate information.

    The returned objects intentionally do not expose internal resolution enums,
    pipeline contexts, or registry implementation details. Use string fields and
    `ProbeCandidateInfo` values for programmatic decisions.

    Args:
        paths: Files and/or directories to probe. Globs are allowed by the caller;
            TopMark will recurse and filter internally.
        config: Optional plain mapping or immutable
            [`FrozenConfig`][topmark.config.model.FrozenConfig] to seed configuration.
            When `None`, project discovery and layered merge are performed.
        policy: Optional global policy overrides. For probe, this is primarily
            useful for resolver-affecting options such as `allow_content_probe`.
        policy_by_type: Optional per-type policy overrides merged after discovery.
        include_file_types: Optional whitelist of file type identifiers to restrict discovery.
        exclude_file_types: Optional blacklist of file type identifiers to exclude from discovery.
        prune_views: If True, release consumed volatile views between pipeline steps.
            Probe results are built from resolution data, not presentation views.

    Returns:
        Stable probe results, summary counts, diagnostics, and any fatal
        pipeline-level exit code.

    Notes:
        `probe()` is always read-only. It has no `apply` or `diff` mode because it
        explains resolution rather than planning or applying header mutations.
    """
    result: _ProbePipelineRun = _run_probe_pipeline(
        paths,
        config=config,
        policy=policy,
        policy_by_type=policy_by_type,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        prune_views=prune_views,
    )
    return result.result


# NOTE: keep `stream_probe()` near `probe()` in generated docs even though it
# delegates through the same runtime and finalizer.
def stream_probe(
    paths: Iterable[Path | str],
    *,
    config: Mapping[str, object] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    prune_views: bool = False,
) -> Iterator[ProbeStreamEvent]:
    """Stream public events for a `probe()` invocation.

    Probe joined the initial public streaming entry-point PR because the probe
    event DTO was already part of the public compatibility contract. The emitted
    file-result events use the same public `ProbeFileResult` DTOs and ordering
    semantics as `probe()`.
    """
    result: _ProbePipelineRun = _run_probe_pipeline(
        paths,
        config=config,
        policy=policy,
        policy_by_type=policy_by_type,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        prune_views=prune_views,
    )
    yield from _iter_probe_events(run=result)
