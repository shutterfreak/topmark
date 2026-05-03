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

Some user-facing outcomes are discovered before a file can enter the normal
processing pipeline. This module builds `ProcessingContext` instances for those
outcomes so presentation, machine output, summaries, and exit-code selection can
treat them like ordinary pipeline results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.context.model import HaltState
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import FsStatus

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.runtime.model import RunOptions


def build_missing_file_contexts(
    *,
    paths: Sequence[Path],
    config: Config,
    run_options: RunOptions,
) -> list[ProcessingContext]:
    """Build synthetic contexts for explicit input paths that do not exist.

    Missing literal paths are detected by file-list resolution before the normal
    pipeline runs. Representing them as contexts keeps diagnostics visible in
    human and machine output and lets `exit_code_from_pipeline_results()` derive
    `ExitCode.FILE_NOT_FOUND` from the same result collection as other
    filesystem outcomes.

    Args:
        paths: Explicit literal paths that were requested but do not exist.
        config: Effective frozen configuration for the current command.
        run_options: Runtime options used to bootstrap synthetic contexts.

    Returns:
        Synthetic processing contexts with `FsStatus.NOT_FOUND` and a terminal
        filesystem hint.
    """
    result: list[ProcessingContext] = []
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
        result.append(ctx)

    return result
