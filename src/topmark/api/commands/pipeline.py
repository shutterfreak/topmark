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

This module exposes `check()` and `strip()` as typed functions mirroring the CLI commands
(`topmark check`, `topmark strip`) without Click.

Call styles:
- Discovery mode: pass `config=None` to discover and merge config layers.
- Seeded mode: pass a plain mapping via `config=` to skip discovery and use that seed.

Notes:
- These functions orchestrate selection of a pipeline variant and delegate execution to
  `topmark.api.runtime.run_pipeline`.
- View flags (`skip_compliant`, `skip_unsupported`) affect only what is returned, not what
  is eligible to be written when `apply=True`.
- Machine output is returned as a `RunResult` and contains no colorized/human rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.api.runtime import run_pipeline
from topmark.api.runtime import select_pipeline
from topmark.api.view import finalize_run_result
from topmark.pipeline.status import PlanStatus

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.api.protocols import PublicPolicy
    from topmark.api.types import RunResult
    from topmark.config.model import Config
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step

__all__ = (
    "check",
    "strip",
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
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    prune: bool = False,
) -> RunResult:
    """Validate or apply TopMark headers for the given paths.

    This is the programmatic equivalent of the CLI `topmark check`. It preserves
    the same discovery behavior when `config` is `None` and accepts optional
    policy overlays that are applied after discovery, before the pipeline runs.

    Args:
        paths: Files and/or directories to process. Globs are allowed by the caller; TopMark will
            recurse and filter internally.
        apply: If `True`, write changes in-place; otherwise perform a dry run.
        diff: If `True`, include unified diffs for changes where applicable.
        config: Optional plain mapping or frozen `Config` to seed configuration. When `None`,
            project discovery and layered merge are performed (defaults → project config
            → overrides).
        policy: Optional global policy overrides (public shape). These are merged after discovery
            using the standard policy resolution.
        policy_by_type: Optional per-type policy overrides (public shape) merged after discovery.
        include_file_types: Optional whitelist of file type identifiers to restrict discovery.
        exclude_file_types: Optional blacklist of file type identifiers to exclude from discovery.
        skip_compliant: Exclude already-compliant files from the returned view.
        skip_unsupported: Exclude unsupported files from the returned view.
        prune: If `True`, trim heavy views after the run (keeps summaries).

    Returns:
        Filtered per-file outcomes, counts, diagnostics, and write stats.

    Notes:
        The `skip_compliant` and `skip_unsupported` flags affect only the **returned view** (which
        files appear and how counts are summarized). They do not change which files are *eligible*
        to be written when `apply=True`.
    """
    # Choose the concrete pipeline variant
    pipeline: Sequence[Step[ProcessingContext]] = select_pipeline("check", apply=apply, diff=diff)

    # Run the pipeline; `_run_pipeline` handles discovery and applies policy overlays
    _cfg: Config
    file_list: list[Path]
    results: list[ProcessingContext]
    encountered_error_code: ExitCode | None
    _cfg, file_list, results, encountered_error_code = run_pipeline(
        pipeline=pipeline,
        paths=paths,
        base_config=config,  # `None` preserves discovery; mapping/Config is honored
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        apply_changes=apply,
        policy=policy,
        policy_by_type=policy_by_type,
        prune=prune,
    )

    # Use common post-run assembly with the write-status set for "check"
    update_statuses: set[PlanStatus] = {
        PlanStatus.INSERTED,
        PlanStatus.REPLACED,
        PlanStatus.REMOVED,
    }
    return finalize_run_result(
        results=results,
        file_list=file_list,
        apply=apply,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
        update_statuses=update_statuses,
        encountered_error_code=encountered_error_code,
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
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    prune: bool = False,
) -> RunResult:
    """Remove TopMark headers from files (dry-run or apply).

    This is the programmatic equivalent of the CLI `topmark strip`. When `config`
    is `None`, the function performs the same project discovery as the CLI and then
    applies optional policy overlays before running the pipeline.

    Args:
        paths: Files and/or directories to process. Globs are allowed.
        apply: If `True`, write changes in-place; otherwise perform a dry run.
        diff: If `True`, include unified diffs for changes where applicable.
        config: Optional plain mapping or frozen `Config` to seed configuration. When `None`,
            project discovery and layered merge are performed (defaults → project config
            → overrides).
        policy: Optional global policy overrides (public shape). Currently strip flows are
            policy-agnostic, but this is accepted for forward compatibility.
        policy_by_type: Optional per-type policy overrides (public shape).
        include_file_types: Optional whitelist of file type identifiers to restrict discovery.
        exclude_file_types: Optional blacklist of file type identifiers to exclude from discovery.
        skip_compliant: Exclude already-compliant files from the returned view.
        skip_unsupported: Exclude unsupported files from the returned view.
        prune: If `True`, trim heavy views after the run (keeps summaries).

    Returns:
        Filtered per-file outcomes, counts, diagnostics, and write stats.

    Notes:
        The `skip_*` flags affect only the **returned view** and do not modify
        pipeline write decisions.
    """
    # Choose the concrete pipeline variant
    pipeline: Sequence[Step[ProcessingContext]] = select_pipeline("strip", apply=apply, diff=diff)

    # Run the pipeline; `_run_pipeline` handles discovery and applies policy overlays
    _cfg: Config
    file_list: list[Path] = []
    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None = None
    _cfg, file_list, results, encountered_error_code = run_pipeline(
        pipeline=pipeline,
        paths=paths,
        base_config=config,  # `None` preserves discovery; mapping/Config is honored
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        apply_changes=apply,
        policy=policy,
        policy_by_type=policy_by_type,
        prune=prune,
    )

    # Use common post-run assembly with the write-status set for "strip"
    update_statuses: set[PlanStatus] = {
        PlanStatus.REMOVED,
    }
    return finalize_run_result(
        results=results,
        file_list=file_list,
        apply=apply,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
        update_statuses=update_statuses,
        encountered_error_code=encountered_error_code,
    )
