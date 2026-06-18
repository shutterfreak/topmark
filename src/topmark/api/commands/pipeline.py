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

from typing import TYPE_CHECKING
from typing import Final

from topmark.api.runtime import run_pipeline_results
from topmark.api.runtime import run_probe_pipeline_results
from topmark.api.view import finalize_probe_result
from topmark.api.view import finalize_run_result
from topmark.core.errors import InvalidReportScopeError
from topmark.pipeline.pipelines import PipelineSelection
from topmark.pipeline.pipelines import select_pipeline
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import PlanStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.api.runtime import ApiPipelineResultRun
    from topmark.api.types import ProbeRunResult
    from topmark.api.types import PublicPolicy
    from topmark.api.types import PublicReportScopeLiteral
    from topmark.api.types import RunResult
    from topmark.pipeline.kinds import PipelineKindLiteral

__all__ = (
    "check",
    "probe",
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
    prune_views: bool,
    update_statuses: frozenset[PlanStatus],
) -> RunResult:
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
        prune_views: If True, release consumed volatile views between pipeline steps.
        update_statuses: Plan statuses counted as write/update candidates by the
            public result finalizer.

    Returns:
        Filtered per-file outcomes, counts, diagnostics, and write stats.
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

    return finalize_run_result(
        results=api_run.results,
        file_list=api_run.file_list,
        apply=apply,
        report_scope=report_scope,
        update_statuses=update_statuses,
        encountered_exit_code=api_run.exit_code,
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
    report: PublicReportScopeLiteral = "all",
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
    return _run_content_pipeline(
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
        prune_views=prune_views,
        update_statuses=_CHECK_UPDATE_STATUSES,
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
    report: PublicReportScopeLiteral = "all",
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
    return _run_content_pipeline(
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
        prune_views=prune_views,
        update_statuses=_STRIP_UPDATE_STATUSES,
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

    # Probe has a dedicated public result shape; do not route it through the
    # check/strip finalizer.
    return finalize_probe_result(
        results=api_run.results,
        file_list=api_run.file_list,
        encountered_exit_code=api_run.exit_code,
    )
