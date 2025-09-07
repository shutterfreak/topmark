# topmark:header:start
#
#   file         : __init__.py
#   file_relpath : src/topmark/api/__init__.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public TopMark API (stable surface).

This module exposes a **small, typed API** intended for integrations that want to
run TopMark programmatically without going through the CLI. The goal is to keep
this surface **stable** across minor versions; internal modules remain private.

Versioning policy
-----------------
- The **signatures and dataclass/TypedDict shapes** in this module follow semver.
- Adding optional parameters with defaults is allowed in minor releases.
- Removing/renaming anything here is a breaking change (major release).

Notes:
-----
- Functions here are **thin wrappers** around the internal pipeline, with the
  same file discovery and filtering as the CLI when `config=None`.
- The "config" parameter accepts a plain mapping and does not require importing
  internal TopMark config types; the mapping is normalized internally.
- Optional flags mirror the CLI: `add_only`, `update_only`, `skip_compliant`,
  and `skip_unsupported`.
- Writes are controlled by a tiny `WritePolicy` value object and a single
  `_write(...)` helper; only files whose `WriteStatus` matches the policy are
  written when `apply=True`.
- A FileType instance is **recognized** if it is in the FileTypeRegistry.
- A FileType instance is **supported** if it is recognized and is registered to
  a HeaderProcessor instance in the HeaderProcessorRegistry.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from topmark.cli.cmd_common import (
    filter_view_results,
    run_steps_for_files,
)
from topmark.cli.io import InputPlan
from topmark.cli_shared.utils import write_updates
from topmark.config import Config
from topmark.config.logging import get_logger, setup_logging
from topmark.constants import TOPMARK_VERSION
from topmark.pipeline.context import ComparisonStatus, FileStatus, ProcessingContext, WriteStatus
from topmark.registry import Registry

from .types import FileResult, FileTypeInfo, Outcome, ProcessorInfo, RunResult

if "TOPMARK_DEBUG" in os.environ:
    setup_logging(level=logging.DEBUG)

logger = get_logger(__name__)


__all__ = [
    "Outcome",
    "FileResult",
    "RunResult",
    "FileTypeInfo",
    "ProcessorInfo",
    "check",
    "strip",
    "version",
    "get_filetype_info",
    "get_processor_info",
    "Registry",
]


# ---------- helpers (private) ----------


def _to_config(value: Mapping[str, Any] | Config | None) -> Config:
    """Normalize a mapping or Config to a Config instance.

    If `value` is None, returns `Config.from_defaults()` (no project config merge).

    Args:
        value: Optional mapping or Config instance.

    Returns:
        A `Config` instance.
    """
    if value is None:
        # You may prefer Config.from_defaults() or a project loader if present
        return Config.from_defaults()
    if isinstance(value, Config):
        return value
    # Accept plain dict-like, normalize to internal Config
    return Config.from_toml_dict(dict(value))


def _map_outcome(r: ProcessingContext, *, apply: bool) -> Outcome:
    """Translate a `ProcessingContext` status into a public `Outcome`.

    Notes:
        - Non-resolved *skipped* statuses (e.g., unsupported or known-no-headers)
          are treated as `UNCHANGED` to avoid surfacing them as errors in the API.
        - When `apply=False`, changed files are reported as `WOULD_CHANGE`.
        - When `apply=True`, changed files are reported as `CHANGED`.
    """
    if r.status.file is not FileStatus.RESOLVED:
        # Treat unsupported/matched-but-unhandled types as non-errors for API consumers.
        unsupported = {
            getattr(FileStatus, "SKIPPED_UNSUPPORTED", None),
            getattr(FileStatus, "SKIPPED_KNOWN_NO_HEADERS", None),
        }
        if r.status.file in unsupported:
            return Outcome.UNCHANGED
        return Outcome.ERROR
    if r.status.comparison is ComparisonStatus.UNCHANGED:
        return Outcome.UNCHANGED
    # At this point the file either would change or did change.
    if apply:
        # In apply mode, run_steps_for_files computes updates; caller may write them.
        return Outcome.CHANGED
    # Dry-run: would change
    return Outcome.WOULD_CHANGE


def _to_file_result(r: ProcessingContext, *, apply: bool) -> FileResult:
    """Convert a ProcessingContext into a FileResult."""
    # Prefer a unified diff when available; otherwise None (human views may omit diffs).
    diff = r.header_diff or None
    message = getattr(r, "summary", None)
    return FileResult(
        path=Path(str(r.path)), outcome=_map_outcome(r, apply=apply), diff=diff, message=message
    )


def _summarize(files: Sequence[FileResult]) -> Mapping[str, int]:
    """Count occurrences of each Outcome in the given files."""
    counts: dict[str, int] = {}
    for fr in files:
        counts[fr.outcome.value] = counts.get(fr.outcome.value, 0) + 1
    return counts


def _run_pipeline(
    *,
    pipeline_name: str,
    paths: Iterable[Path | str],
    base_config: Mapping[str, Any] | Config | None,
    file_types: Sequence[str] | None,
) -> tuple[Config, list[Path], list[ProcessingContext], object | None]:
    """Resolve config + files, register processors, and run the pipeline.

    - Uses the same planner/resolver as the CLI (via `build_config_and_file_list`)
    when `base_config is None`; otherwise honors the supplied mapping without
    merging project config, then resolves files via `resolve_file_list`.
    - Ensures all header processors are registered before running the pipeline.

    Returns:
    (cfg, file_list, results, encountered_error_code)
    """
    logger.info("Building config and file list for paths: %s", paths)
    cfg, file_list = _build_cfg_and_files_via_cli_helpers(
        paths, base_config=base_config, file_types=file_types
    )
    if not file_list:
        return cfg, file_list, [], None

    logger.info("Processing %d files with TopMark %s", len(file_list), TOPMARK_VERSION)

    # Ensure all processors are registered before running the pipeline (idempotent)
    Registry.ensure_processors_registered()

    results, encountered_error_code = run_steps_for_files(
        file_list, pipeline_name=pipeline_name, config=cfg
    )
    return cfg, file_list, results, encountered_error_code


def _apply_view_filter(
    results: list[ProcessingContext],
    *,
    skip_compliant: bool,
    skip_unsupported: bool,
) -> tuple[list[ProcessingContext], int]:
    """Apply CLI-equivalent view filtering and return (filtered_results, skipped_count).

    `skipped_count` equals `len(results) - len(filtered_results)` and reflects only
    view-level filtering (not internal SKIPPED statuses).
    """
    view_results = filter_view_results(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )
    skipped = len(results) - len(view_results)
    return view_results, skipped


def _collect_diagnostics(results: list[ProcessingContext]) -> dict[str, list[str]]:
    """Collect per-file diagnostics as a mapping `{path: [messages...]}`.

    Only files that produced diagnostics are included in the result.

    Args:
        results: List of ProcessingContext results.

    Returns:
        A mapping from file path (string) to a list of diagnostic messages.
    """
    diags: dict[str, list[str]] = {}
    for r in results:
        if r.diagnostics:
            diags[str(r.path)] = r.diagnostics
    return diags


# ---------- public API ----------


def _build_cfg_and_files_via_cli_helpers(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, Any] | Config | None,
    file_types: Sequence[str] | None,
) -> tuple[Config, list[Path]]:
    """Use the same config+file discovery as the CLI.

    If `base_config` is provided, we normalize it to Config and resolve the file
    list directly with `resolve_file_list(cfg)` to avoid merging project config
    implicitly. Otherwise we perform project-config discovery & merge without Click
    and then resolve files.
    """
    from topmark.file_resolver import resolve_file_list

    cfg: Config = _to_config(base_config)

    logger.debug("Normalizing input paths: %s", paths)

    plan = InputPlan(
        stdin_mode=False,
        temp_path=None,
        paths=[str(Path(p)) for p in paths],
        include_patterns=[],
        exclude_patterns=[],
        files_from=[],
        include_from=[],
        exclude_from=[],
    )

    logger.debug("Input plan: %s", plan)

    # If the caller supplied a mapping/Config, honor it directly to avoid
    # inadvertently merging local project config. We still reuse the planner’s
    # normalization of paths.
    if base_config is not None:
        cfg.files = list(plan.paths)
        logger.debug("Found %d input paths", len(cfg.files))
        if file_types:
            cfg.file_types = set(file_types)
        file_list = resolve_file_list(cfg)
        logger.debug("Files found: %s", len(file_list))
        return cfg, file_list

    # Otherwise, perform project-config discovery & merge like the CLI,
    # but without relying on Click. We construct the ArgsNamespace-equivalent
    # mapping that `Config.load_merged()` expects.
    args_mapping = {
        "log_level": logging.WARNING,
        "files": list(plan.paths),
        "files_from": list(plan.files_from),
        "stdin": False,
        "include_patterns": list(plan.include_patterns),
        "include_from": list(plan.include_from),
        "exclude_patterns": list(plan.exclude_patterns),
        "exclude_from": list(plan.exclude_from),
        "no_config": False,
        "config_files": [],
        "file_types": list(file_types) if file_types else [],
        "relative_to": None,
        "align_fields": False,
        "header_format": None,
    }

    cfg_built = Config.load_merged(args_mapping)  # uses project discovery/merge

    from topmark.file_resolver import resolve_file_list as _resolve_file_list

    file_list = _resolve_file_list(cfg_built)
    return cfg_built, file_list


def check(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    config: Mapping[str, Any] | None = None,
    file_types: Sequence[str] | None = None,
    add_only: bool = False,
    update_only: bool = False,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
) -> RunResult:
    """Validate or apply TopMark headers for the given paths.

    Args:
        paths: Files and/or directories to process. Globs are allowed by the
            caller; TopMark will recurse and filter internally.
        apply: If True, write changes in-place; otherwise perform a dry run.
        config: Optional plain mapping merged/normalized into a `Config`. If
            None, the same discovery/merging as the CLI is used.
        file_types: Optional whitelist of TopMark file type identifiers to narrow
            discovery.
        add_only: Only add missing headers; do not update existing ones.
        update_only: Only update non-compliant headers; do not add new ones.
        skip_compliant: Exclude already-compliant files from the returned view.
        skip_unsupported: Exclude unsupported files from the returned view.

    Returns:
        RunResult: Filtered per-file outcomes, counts, diagnostics, and write stats.

    Raises:
        ValueError: If `add_only` and `update_only` are both True.

    Notes:
        The `skip_compliant` and `skip_unsupported` flags affect only the
        **returned view** (which files appear and how counts are summarized).
        They do not change which files are *eligible* to be written when
        `apply=True`.
    """
    if add_only and update_only:
        raise ValueError("Options add_only and update_only are mutually exclusive.")

    # Always use 'apply' pipeline to compute updated content even in dry-run
    _, file_list, results, encountered_error_code = _run_pipeline(
        pipeline_name="apply",
        paths=paths,
        base_config=config,
        file_types=file_types,
    )
    if not file_list:
        return RunResult(files=(), summary={}, had_errors=False)

    view_results, skipped = _apply_view_filter(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )

    files = tuple(_to_file_result(r, apply=apply) for r in view_results)
    summary = _summarize(files)
    had_errors = any(_map_outcome(r, apply=apply) is Outcome.ERROR for r in results) or (
        encountered_error_code is not None
    )
    diagnostics = _collect_diagnostics(view_results)

    written = failed = 0
    if apply:

        def _should_write_check(r: ProcessingContext) -> bool:
            """Determine whether to write this file in check mode."""
            if add_only and r.status.write is not WriteStatus.INSERTED:
                return False
            if update_only and r.status.write is not WriteStatus.REPLACED:
                return False
            return r.status.file is FileStatus.RESOLVED and r.status.write in (
                WriteStatus.INSERTED,
                WriteStatus.REPLACED,
            )

        # Perform writes and count successes/failures
        written, failed = write_updates(results, should_write=_should_write_check)

    return RunResult(
        files=files,
        summary=summary,
        had_errors=had_errors,
        skipped=skipped,
        written=written,
        failed=failed,
        diagnostics=diagnostics,
    )


def strip(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    config: Mapping[str, Any] | None = None,
    file_types: Sequence[str] | None = None,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
) -> RunResult:
    """Remove TopMark headers from files (dry-run or apply).

    Args:
        paths: Files and/or directories to process. Globs are allowed by the caller.
        apply: If True, write changes in-place; otherwise perform a dry run.
        config: Optional plain mapping merged/normalized into a `Config`. If
            None, the same discovery/merging as the CLI is used.
        file_types: Optional whitelist of TopMark file type identifiers to narrow
            discovery.
        skip_compliant: Exclude already-compliant files from the returned view.
        skip_unsupported: Exclude unsupported files from the returned view.

    Returns:
        RunResult: Filtered per-file outcomes, counts, diagnostics, skipped count,
        and write stats.

    Notes:
        The `skip_*` flags affect only the **returned view** and do not modify
        pipeline write decisions.
    """
    # The 'strip' pipeline computes removal-ready updates even in dry-run
    _, file_list, results, encountered_error_code = _run_pipeline(
        pipeline_name="strip",
        paths=paths,
        base_config=config,
        file_types=file_types,
    )
    if not file_list:
        return RunResult(files=(), summary={}, had_errors=False)

    view_results, skipped = _apply_view_filter(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )

    files = tuple(_to_file_result(r, apply=apply) for r in view_results)
    summary = _summarize(files)
    had_errors = any(_map_outcome(r, apply=apply) is Outcome.ERROR for r in results) or (
        encountered_error_code is not None
    )
    diagnostics = _collect_diagnostics(view_results)

    written = failed = 0
    if apply:

        def _should_write_strip(r: ProcessingContext) -> bool:
            """Determine whether to write this file in strip mode."""
            logger.debug("Deciding whether to write file %s: status=%s", r.path, r.status)
            return r.status.file is FileStatus.RESOLVED and r.status.write is WriteStatus.REMOVED

        # Perform writes and count successes/failures
        written, failed = write_updates(results, should_write=_should_write_strip)

    return RunResult(
        files=files,
        summary=summary,
        had_errors=had_errors,
        skipped=skipped,
        written=written,
        failed=failed,
        diagnostics=diagnostics,
    )


def get_filetype_info(long: bool = False) -> list[FileTypeInfo]:
    """Return metadata about registered file types.

    Args:
        long: If True, include extended metadata such as patterns and policy.

    Returns:
        A list of `FileTypeInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `FileTypeRegistry` from
        `topmark.registry`. This function returns metadata (not the objects).
    """
    proc_reg = Registry.processors()

    items: list[FileTypeInfo] = []
    for name, ft in Registry.filetypes().items():
        processor = proc_reg.get(name, None) if proc_reg else None
        supported = bool(processor)
        processor_name = processor.__class__.__name__ if processor else None
        info: FileTypeInfo = {
            "name": name,
            "description": getattr(ft, "description", ""),
        }
        if long:
            info.update(
                {
                    "supported": supported,
                    "processor_name": processor_name,
                    "extensions": tuple(getattr(ft, "extensions", ()) or ()),
                    "filenames": tuple(getattr(ft, "filenames", ()) or ()),
                    "patterns": tuple(getattr(ft, "patterns", ()) or ()),
                    "skip_processing": bool(getattr(ft, "skip_processing", False)),
                    "content_matcher": bool(getattr(ft, "has_content_matcher", False)),
                    "header_policy": str(getattr(ft, "header_policy_name", "")),
                }
            )
        items.append(info)
    return items


def get_processor_info(long: bool = False) -> list[ProcessorInfo]:
    """Return metadata about registered header processors.

    Args:
        long: If True, include extended details for line/block delimiters.

    Returns:
        A list of `ProcessorInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `HeaderProcessorRegistry` from
        `topmark.registry`. This function returns metadata (not the objects).
    """
    # Ensure all processors are registered before listing (idempotent)
    Registry.ensure_processors_registered()

    items: list[ProcessorInfo] = []
    for name, proc in Registry.processors().items():
        info: ProcessorInfo = {
            "name": name,
            "description": getattr(proc, "description", ""),
        }
        if long:
            info.update(
                {
                    "line_prefix": getattr(proc, "line_prefix", "") or "",
                    "line_suffix": getattr(proc, "line_suffix", "") or "",
                    "block_prefix": getattr(proc, "block_prefix", "") or "",
                    "block_suffix": getattr(proc, "block_suffix", "") or "",
                }
            )
        items.append(info)
    return items


def version() -> str:
    """Return the current TopMark version string."""
    return TOPMARK_VERSION
