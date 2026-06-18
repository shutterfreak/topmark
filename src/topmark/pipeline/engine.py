# topmark:header:start
#
#   project      : TopMark
#   file         : engine.py
#   file_relpath : src/topmark/pipeline/engine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Execution helpers for running pipelines over a list of files (engine layer).

This module provides a small, CLI-free function to execute a pipeline for one or
more files. It exists so both the public API and the CLI can share the same
engine logic without introducing import cycles.

Design goals:
  - No CLI dependencies: Do not import Click, console helpers, or anything under
    ``topmark.cli.*`` from here. Presentation (printing, colors, exit) is a
    responsibility of the CLI layer.
  - Structured results: Return a `PipelineExecution` containing produced
    `ProcessingContext` objects plus an optional `ExitCode` summarizing any error
    encountered while iterating files.
  - Logging only: Error conditions are logged via the package logger. Callers
    decide how to surface errors (e.g., raise, print, or exit).

Typical usage:

    run = run_steps_for_files(
        file_list=files,
        pipeline=Pipeline.CHECK.steps,
        config=cfg,
        run_options=run_options,
    )
    if run.error_code is not None:
        # CLI would map this to a process exit; API callers may handle it differently.
        ...

This module is intentionally minimal to keep the dependency graph acyclic and
the execution path easy to test in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol

from topmark.config.policy import PolicyRegistry
from topmark.config.policy import make_policy_registry
from topmark.core.exit_codes import ExitCode
from topmark.core.logging import get_logger
from topmark.pipeline import runner
from topmark.pipeline.context.model import HaltState
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import WriteStatus
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeResult
from topmark.resolution.probe import ResolutionProbeStatus

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping
    from collections.abc import Sequence
    from os import stat_result
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.pipelines import PipelineSelection
    from topmark.runtime.model import RunOptions

logger: TopmarkLogger = get_logger(__name__)


class SupportsPipelineExitStatus(Protocol):
    """Minimum result surface required for pipeline exit-code selection."""

    @property
    def fs(self) -> FsStatus:
        """Filesystem status used by exit-code selection."""
        ...

    @property
    def content(self) -> ContentStatus:
        """Content status used by exit-code selection."""
        ...

    @property
    def write(self) -> WriteStatus:
        """Write status used by exit-code selection."""
        ...


class SupportsPipelineExitResult(Protocol):
    """Minimum context/result surface required for pipeline exit-code selection."""

    @property
    def status(self) -> SupportsPipelineExitStatus:
        """Per-axis status values used by exit-code selection."""
        ...


@dataclass(frozen=True, kw_only=True, slots=True)
class _FilesystemIdentity:
    """Stable filesystem-object identity used for hard-link detection."""

    device: int
    inode: int


def _filesystem_identity(path: Path) -> _FilesystemIdentity | None:
    """Return `(st_dev, st_ino)` identity for an existing path when available."""
    try:
        stat_info: stat_result = path.stat()
    except OSError:
        return None

    if stat_info.st_nlink < 2:
        return None

    return _FilesystemIdentity(device=stat_info.st_dev, inode=stat_info.st_ino)


def _hard_link_duplicate_paths(file_list: Sequence[Path]) -> set[Path]:
    """Return selected paths that share filesystem storage with another selected path."""
    paths_by_identity: dict[_FilesystemIdentity, list[Path]] = {}

    for path in file_list:
        identity: _FilesystemIdentity | None = _filesystem_identity(path)
        if identity is None:
            continue
        paths_by_identity.setdefault(identity, []).append(path)

    duplicates: set[Path] = set()
    for paths in paths_by_identity.values():
        unique_paths: set[Path] = set(paths)
        if len(unique_paths) > 1:
            duplicates.update(unique_paths)

    return duplicates


def _build_hard_link_duplicate_context(
    *,
    path: Path,
    run_options: RunOptions,
    config: FrozenConfig,
    policy_registry: PolicyRegistry | None,
) -> ProcessingContext:
    """Build a terminal context for a hard-linked processing target."""
    ctx: ProcessingContext = ProcessingContext.bootstrap(
        path=path,
        config=config,
        run_options=run_options,
        policy_registry_override=policy_registry,
    )
    ctx.status.fs = FsStatus.HARD_LINK_DUPLICATE
    ctx.halt_state = HaltState(
        reason_code=KnownCode.FS_HARD_LINK_DUPLICATE.value,
        step_name="HardLinkIdentityGuard",
    )
    ctx.resolution_probe = ResolutionProbeResult(
        path=path,
        status=ResolutionProbeStatus.UNSUPPORTED,
        reason=ResolutionProbeReason.HARD_LINK_DUPLICATE,
        candidates=(),
        selected_file_type=None,
        selected_processor=None,
    )
    ctx.hint(
        axis=Axis.FS,
        code=KnownCode.FS_HARD_LINK_DUPLICATE,
        message=(
            "Path shares storage with another selected processing path; "
            "hard-linked targets are blocked"
        ),
        cluster=Cluster.BLOCKED_POLICY,
        terminal=True,
        reason=FsStatus.HARD_LINK_DUPLICATE.value,
    )
    return ctx


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineExecution:
    """Materialized result of running pipeline steps over a selected file list.

    Attributes:
        contexts: Ordered per-file processing contexts produced by pipeline execution,
            one for each path in the input file list that did not raise a fatal
            engine-level error.
        exit_code: First non-success engine-level exit code encountered while
            iterating files, or `None` when no such error occurred.
    """

    contexts: list[ProcessingContext]
    exit_code: ExitCode | None


@dataclass(kw_only=True, slots=True)
class PipelineExecutionState:
    """Mutable state updated while iterating pipeline execution.

    Attributes:
        exit_code: First non-success engine-level exit code encountered while
            iterating files, or `None` when no such error occurred.
    """

    exit_code: ExitCode | None = None


def exit_code_from_pipeline_results(
    results: Sequence[SupportsPipelineExitResult],
) -> ExitCode | None:
    """Return the highest-priority non-success exit code implied by pipeline results.

    This helper summarizes per-file pipeline statuses into a process-level exit
    signal for CLI/API callers. It is intentionally presentation-free: it does
    not print, log, or inspect rendered hints. Callers remain responsible for
    rendering diagnostics and deciding exactly when to exit.

    Priority order:
      1. missing inputs (`FILE_NOT_FOUND`)
      2. permission failures (`PERMISSION_DENIED`)
      3. encoding failures (`ENCODING_ERROR`)
      4. write failures (`IO_ERROR`)
      5. generic read/I/O failures (`IO_ERROR`)

    Non-error skips such as binary/unsupported files, empty files, mixed line
    endings, and policy blocks are intentionally not mapped here. Those remain
    normal per-file pipeline outcomes unless a command layer gives them a
    command-specific non-zero meaning.

    Args:
        results: Pipeline contexts or durable processing results returned by
            `run_steps_for_files` or the batch reduction boundary.

    Returns:
        The highest-priority `ExitCode` implied by the results, or `None` when
        the result set does not imply a command-level error.
    """
    if any(r.status.fs == FsStatus.NOT_FOUND for r in results):
        return ExitCode.FILE_NOT_FOUND

    if any(
        r.status.fs
        in {
            FsStatus.NO_READ_PERMISSION,
            FsStatus.NO_WRITE_PERMISSION,
        }
        for r in results
    ):
        return ExitCode.PERMISSION_DENIED

    if any(r.status.fs == FsStatus.UNICODE_DECODE_ERROR for r in results):
        return ExitCode.ENCODING_ERROR

    if any(r.status.write == WriteStatus.FAILED for r in results):
        return ExitCode.IO_ERROR

    if any(
        r.status.fs == FsStatus.UNREADABLE or r.status.content == ContentStatus.UNREADABLE
        for r in results
    ):
        return ExitCode.IO_ERROR

    return None


def iter_steps_for_files(
    *,
    run_options: RunOptions,
    config: FrozenConfig,
    path_configs: Mapping[Path, FrozenConfig] | None = None,
    pipeline: PipelineSelection,
    file_list: list[Path],
    state: PipelineExecutionState | None = None,
) -> Iterator[ProcessingContext]:
    """Yield pipeline contexts for files in input order.

    This helper is the streaming-capable engine boundary. It preserves the
    existing per-file error handling semantics while allowing callers to reduce
    and release each yielded context before the next file is processed.

    Args:
        run_options: Invocation-wide runtime options shared by all files in the run.
        config: Default layered TopMark configuration for the run.
        path_configs: Optional per-path effective layered configs. When provided, a
            path-specific config is used for bootstrap; otherwise the shared `config`
            is used.
        pipeline: The pipeline steps to execute for the run.
        file_list: List of file Path instances to be processed in the run.
        state: Optional mutable execution state updated with the first
            non-success engine-level exit code encountered while iterating.

    Yields:
        Processing contexts in input-file order for files that were processed
        successfully by the engine layer. Files that raise handled engine-level
        filesystem, permission, encoding, or unexpected errors are logged and
        skipped while preserving the first corresponding exit code in `state`.

    Exit code mapping:
        FILE_NOT_FOUND
            Raised when a path is missing or is a directory where a file was expected
            (`FileNotFoundError`, `IsADirectoryError`).
        PERMISSION_DENIED
            Raised on insufficient permissions (`PermissionError`).
        ENCODING_ERROR
            Raised when the input cannot be decoded as text (`UnicodeDecodeError`).
        PIPELINE_ERROR
            Any other unexpected exception not covered by the above categories.

    Notes:
        - This helper **never prints**; it only logs. Callers are responsible for
          user-visible messaging and exiting the process if desired.
        - When multiple files are processed, only the *first* error code is preserved
          (a conventional behavior for batch tools). Subsequent files continue to run.
    """
    execution_state: PipelineExecutionState = (
        state if state is not None else PipelineExecutionState()
    )
    default_policy_registry: PolicyRegistry | None = (
        None if path_configs is not None else make_policy_registry(config)
    )
    hard_link_duplicate_paths: set[Path] = _hard_link_duplicate_paths(file_list)

    # Process each path independently; collect contexts and degrade gracefully
    # on non-fatal errors (recording the first encountered exit code).
    for path in file_list:
        try:
            effective_config: FrozenConfig = (
                path_configs[path] if path_configs is not None else config
            )
            policy_registry: PolicyRegistry | None = (
                make_policy_registry(effective_config)
                if path_configs is not None
                else default_policy_registry
            )
            if path in hard_link_duplicate_paths:
                yield _build_hard_link_duplicate_context(
                    path=path,
                    config=effective_config,
                    run_options=run_options,
                    policy_registry=policy_registry,
                )
                continue

            # When no precomputed registry is supplied, bootstrap() derives one from config.
            ctx_obj: ProcessingContext = ProcessingContext.bootstrap(
                path=path,
                config=effective_config,
                run_options=run_options,
                policy_registry_override=policy_registry,
            )
            yield runner.run(
                ctx_obj,
                pipeline.steps,
                prune_views=run_options.prune_views,
                keep_diff_view=run_options.keep_diff_view,
            )
        except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
            logger.error("Filesystem error while processing %s: %s", path, e)
            if isinstance(e, FileNotFoundError | IsADirectoryError):
                logger.error("%s: %s", e, path)
                execution_state.exit_code = execution_state.exit_code or ExitCode.FILE_NOT_FOUND
            else:
                logger.error("%s: %s", e, path)
                execution_state.exit_code = execution_state.exit_code or ExitCode.PERMISSION_DENIED
            continue
        except UnicodeDecodeError as e:
            logger.error("Encoding error while reading %s: %s", path, e)
            execution_state.exit_code = execution_state.exit_code or ExitCode.ENCODING_ERROR
            continue
        except Exception as e:  # pragma: no cover
            logger.exception("Unexpected error processing %s: %s", path, e)
            execution_state.exit_code = execution_state.exit_code or ExitCode.PIPELINE_ERROR
            continue


def run_steps_for_files(
    *,
    run_options: RunOptions,
    config: FrozenConfig,
    path_configs: Mapping[Path, FrozenConfig] | None = None,
    pipeline: PipelineSelection,
    file_list: list[Path],
) -> PipelineExecution:
    """Run a pipeline for each file and return structured engine results.

    Catches common filesystem/encoding errors so command bodies don't duplicate try/except.
    This batch helper materializes the streaming-capable `iter_steps_for_files()`
    boundary for existing callers that need all contexts at once.

    Args:
        run_options: Invocation-wide runtime options shared by all files in the run.
        config: Default layered TopMark configuration for the run.
        path_configs: Optional per-path effective layered configs. When provided, a
            path-specific config is used for bootstrap; otherwise the shared `config`
            is used.
        pipeline: The pipeline steps to execute for the run.
        file_list: List of file Path instances to be processed in the run.

    Returns:
        Structured engine result containing ordered per-file
        `ProcessingContext` objects and the first encountered non-success exit
        code, if any. The exit code is suitable for reporting or process exit
        in the CLI layer.

    Notes:
        - This helper **never prints**; it only logs. Callers are responsible for
          user-visible messaging and exiting the process if desired.
        - When multiple files are processed, only the *first* error code is preserved
          (a conventional behavior for batch tools). Subsequent files continue to run.
    """
    state: PipelineExecutionState = PipelineExecutionState()
    contexts: list[ProcessingContext] = list(
        iter_steps_for_files(
            run_options=run_options,
            config=config,
            path_configs=path_configs,
            pipeline=pipeline,
            file_list=file_list,
            state=state,
        ),
    )
    return PipelineExecution(contexts=contexts, exit_code=state.exit_code)
