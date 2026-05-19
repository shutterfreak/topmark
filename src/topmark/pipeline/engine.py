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

from topmark.config.policy import PolicyRegistry
from topmark.config.policy import make_policy_registry
from topmark.core.exit_codes import ExitCode
from topmark.core.logging import get_logger
from topmark.pipeline import runner
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import WriteStatus

if TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.protocols import Step
    from topmark.runtime.model import RunOptions

logger: TopmarkLogger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineExecution:
    """Result of running pipeline steps over a selected file list.

    Attributes:
        results: Ordered per-file processing contexts produced by the pipeline,
            one for each path in the input file list that did not raise a fatal
            engine-level error.
        exit_code: First non-success engine-level exit code encountered while
            iterating files, or `None` when no such error occurred.
    """

    results: list[ProcessingContext]
    exit_code: ExitCode | None


def exit_code_from_pipeline_results(
    results: Sequence[ProcessingContext],
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
        results: Pipeline contexts returned by `run_steps_for_files`.

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


def run_steps_for_files(
    *,
    run_options: RunOptions,
    config: FrozenConfig,
    path_configs: Mapping[Path, FrozenConfig] | None = None,
    pipeline: Sequence[Step[ProcessingContext]],
    file_list: list[Path],
) -> PipelineExecution:
    """Run a pipeline for each file and return structured engine results.

    Catches common filesystem/encoding errors so command bodies don't duplicate try/except.

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
    results: list[ProcessingContext] = []
    encountered_exit_code: ExitCode | None = None
    default_policy_registry: PolicyRegistry | None = (
        None if path_configs is not None else make_policy_registry(config)
    )

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
            # When no precomputed registry is supplied, bootstrap() derives one from config.
            ctx_obj: ProcessingContext = ProcessingContext.bootstrap(
                path=path,
                config=effective_config,
                run_options=run_options,
                policy_registry_override=policy_registry,
            )
            ctx_obj = runner.run(ctx_obj, pipeline, prune=run_options.prune_views)
            results.append(ctx_obj)
        except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
            logger.error("Filesystem error while processing %s: %s", path, e)
            if isinstance(e, FileNotFoundError | IsADirectoryError):
                logger.error("%s: %s", e, path)
                encountered_exit_code = encountered_exit_code or ExitCode.FILE_NOT_FOUND
            else:
                logger.error("%s: %s", e, path)
                encountered_exit_code = encountered_exit_code or ExitCode.PERMISSION_DENIED
            continue
        except UnicodeDecodeError as e:
            logger.error("Encoding error while reading %s: %s", path, e)
            encountered_exit_code = encountered_exit_code or ExitCode.ENCODING_ERROR
            continue
        except Exception as e:  # pragma: no cover
            logger.exception("Unexpected error processing %s: %s", path, e)
            encountered_exit_code = encountered_exit_code or ExitCode.PIPELINE_ERROR
            continue

    return PipelineExecution(results=results, exit_code=encountered_exit_code)
