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
  - Structured results: Return a list of `ProcessingContext` objects, plus an
    optional `ExitCode` summarizing any error encountered while iterating files.
  - Logging only: Error conditions are logged via the package logger. Callers
    decide how to surface errors (e.g., raise, print, or exit).

Typical usage:

    results, err = run_steps_for_files(
        file_list=files, pipeline=Pipeline.CHECK.steps, config=cfg, prune=True
    )
    if err is not None:
        # CLI would map this to a process exit; API callers may handle it differently.
        ...

This module is intentionally minimal to keep the dependency graph acyclic and
the execution path easy to test in isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.config.policy import PolicyRegistry, make_policy_registry
from topmark.core.exit_codes import ExitCode
from topmark.pipeline import runner
from topmark.pipeline.context.model import ProcessingContext

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config import Config
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.protocols import Step

logger: TopmarkLogger = get_logger(__name__)


def run_steps_for_files(
    *,
    file_list: list[Path],
    pipeline: Sequence[Step],
    config: Config,
    prune: bool = True,
) -> tuple[list[ProcessingContext], ExitCode | None]:
    """Run a pipeline for each file and return (results, encountered_error_code).

    Catches common filesystem/encoding errors so command bodies don’t duplicate try/except.

    Args:
        file_list: List of file Path instances to be processed in the run.
        pipeline: The pipeline steps to execute for the run.
        config: The TopMark configuration for the run.
        prune: If `True`, trim heavy views after the run (keeps summaries). Default: `True`.

    Returns:
        tuple[list[ProcessingContext], ExitCode | None]: A pair ``(results, error_code)`` where:
            - ``results`` is the ordered list of per-file `ProcessingContext` objects produced
              by the pipeline, one for each path in ``file_list`` that did not raise a fatal error.
            - ``error_code`` is ``None`` if no error occurred; otherwise the first encountered
              non-success exit code, suitable for reporting or process exit in the CLI layer.

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
    encountered_error_code: ExitCode | None = None
    policy_registry: PolicyRegistry = make_policy_registry(config)

    # Process each path independently; collect contexts and degrade gracefully
    # on non-fatal errors (recording the first encountered exit code).
    for path in file_list:
        try:
            ctx_obj: ProcessingContext = ProcessingContext.bootstrap(
                path=path,
                config=config,
                policy_registry_override=policy_registry,
            )
            ctx_obj = runner.run(ctx_obj, pipeline, prune=prune)
            results.append(ctx_obj)
        except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
            logger.error("Filesystem error while processing %s: %s", path, e)
            if isinstance(e, (FileNotFoundError, IsADirectoryError)):
                logger.error("%s: %s", e, path)
                encountered_error_code = encountered_error_code or ExitCode.FILE_NOT_FOUND
            else:
                logger.error("%s: %s", e, path)
                encountered_error_code = encountered_error_code or ExitCode.PERMISSION_DENIED
            continue
        except UnicodeDecodeError as e:
            logger.error("Encoding error while reading %s: %s", path, e)
            encountered_error_code = encountered_error_code or ExitCode.ENCODING_ERROR
            continue
        except Exception as e:  # pragma: no cover
            logger.exception("Unexpected error processing %s: %s", path, e)
            encountered_error_code = encountered_error_code or ExitCode.PIPELINE_ERROR
            continue

    return results, encountered_error_code
