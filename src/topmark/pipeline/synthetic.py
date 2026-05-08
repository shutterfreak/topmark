# topmark:header:start
#
#   project      : TopMark
#   file         : synthetic.py
#   file_relpath : src/topmark/pipeline/synthetic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Synthetic pipeline contexts for resolver-level outcomes.

Some user-facing outcomes are discovered before a file can enter normal pipeline
execution. This module builds `ProcessingContext` instances for those outcomes
so presentation, machine-readable output, summaries, and exit-code selection can treat
them like ordinary pipeline results.

These helpers are shared by CLI and public-API orchestration, but this module
remains internal pipeline infrastructure. Callers outside TopMark should use
`topmark.api` entry points instead of constructing synthetic contexts manually.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.context.model import HaltState
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import FsStatus
from topmark.resolution.discovery import FileSelectionReason
from topmark.resolution.discovery import FileSelectionStatus
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeResult
from topmark.resolution.probe import ResolutionProbeStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.resolution.discovery import FileSelectionProbeResult
    from topmark.runtime.model import RunOptions


def build_missing_file_contexts(
    *,
    paths: Sequence[Path],
    config: Config,
    run_options: RunOptions,
) -> list[ProcessingContext]:
    """Build synthetic filesystem contexts for missing explicit input paths.

    Missing literal paths are detected by file-list resolution before the normal
    pipeline runs. Representing them as contexts keeps diagnostics visible in
    human and machine-readable output and lets `exit_code_from_pipeline_results()` derive
    `ExitCode.FILE_NOT_FOUND` from the same result collection as other
    filesystem outcomes.

    Args:
        paths: Explicit literal input paths that were requested but do not exist.
        config: Effective frozen configuration for the current command.
        run_options: Runtime options used to bootstrap synthetic contexts.

    Returns:
        Synthetic processing contexts with `FsStatus.NOT_FOUND` and a terminal
        filesystem hint.
    """
    contexts: list[ProcessingContext] = []
    for path in paths:
        ctx: ProcessingContext = ProcessingContext.bootstrap(
            path=path,
            config=config,
            run_options=run_options,
        )

        ctx.status.fs = FsStatus.NOT_FOUND
        ctx.halt_state = HaltState(
            reason_code="file_not_found",
            step_name="file_resolution",
        )
        ctx.hint(
            axis=Axis.FS,
            code=KnownCode.FS_NOT_FOUND,
            message=f"No such file or directory: {path}",
            cluster=Cluster.ERROR,
            terminal=True,
        )
        contexts.append(ctx)

    return contexts


def map_selection_reason_to_probe_reason(
    reason: FileSelectionReason,
) -> ResolutionProbeReason:
    """Map a discovery selection reason to the corresponding probe reason.

    Args:
        reason: Selection reason emitted by file discovery for an explicit input.

    Returns:
        Probe-layer reason used by synthetic filtered `ResolutionProbeResult` values.
    """
    match reason:
        case FileSelectionReason.EXCLUDED_BY_PATH_FILTER:
            return ResolutionProbeReason.EXCLUDED_BY_PATH_FILTER
        case FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER:
            return ResolutionProbeReason.EXCLUDED_BY_FILE_TYPE_FILTER
        case FileSelectionReason.EXCLUDED_BY_DISCOVERY_FILTER:
            return ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER
        # These reasons only occur before file-type resolution can run. Treat
        # them as discovery-filtered probe outcomes rather than inventing more
        # granular public probe reasons.
        case FileSelectionReason.NOT_A_FILE:
            return ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER
        case FileSelectionReason.NOT_FOUND:
            return ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER
        # Selected inputs are skipped by `build_filtered_probe_contexts()`. This
        # fallback keeps the mapper total if it is reused directly.
        case FileSelectionReason.SELECTED:
            return ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER


def build_filtered_probe_contexts(
    *,
    selection_results: Sequence[FileSelectionProbeResult],
    config: Config,
    run_options: RunOptions,
) -> list[ProcessingContext]:
    """Build synthetic probe contexts for explicit inputs filtered before probing.

    The normal probe pipeline only runs for files selected by file-list
    resolution. Explicit input paths that are excluded before that point still
    need probe-shaped results so CLI, machine-readable output, summaries, and the public
    API can explain why they never reached file-type resolution.

    Args:
        selection_results: Discovery explanations for explicit input paths.
            Selected inputs are ignored because they are represented by real
            probe pipeline contexts.
        config: Effective frozen configuration for the current command.
        run_options: Runtime options used to bootstrap synthetic contexts.

    Returns:
        Synthetic processing contexts whose `resolution_probe` fields describe
        explicit inputs filtered before probing.
    """
    contexts: list[ProcessingContext] = []

    for selection in selection_results:
        # Selected inputs are represented by real probe pipeline contexts; only
        # paths that disappear during discovery need synthetic probe contexts.
        if selection.status == FileSelectionStatus.SELECTED:
            continue

        ctx: ProcessingContext = ProcessingContext.bootstrap(
            path=selection.path,
            config=config,
            run_options=run_options,
        )
        ctx.resolution_probe = ResolutionProbeResult(
            path=selection.path,
            status=ResolutionProbeStatus.FILTERED,
            reason=map_selection_reason_to_probe_reason(selection.reason),
            candidates=(),
            selected_file_type=None,
            selected_processor=None,
        )
        contexts.append(ctx)

    return contexts
