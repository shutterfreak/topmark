# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/api/__init__.py
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
- Optional view flags mirror the CLI: `skip_compliant`, `skip_unsupported`.
- Add/update intent is controlled via **policy overlays** (`PublicPolicy`, `PublicPolicyByType`)
  that are applied after discovery.
- Writes are performed exclusively by the pipeline writer step; the API only reports
  statuses determined by the pipeline (no duplicate write logic).
- A FileType instance is **recognized** if it is in the FileTypeRegistry.
- A FileType instance is **supported** if it is recognized and is registered to
  a HeaderProcessor instance in the HeaderProcessorRegistry.
- The API returns per-file diagnostics and aggregate counts; levels are "info", "warning", "error".

Configuration contract
----------------------
- Public functions accept either a plain **mapping** (mirroring the TOML shape) or a frozen
  [`topmark.config.Config`][]. We normalize/merge internally and run the pipeline against an
  **immutable snapshot**.
- The internal [`topmark.config.MutableConfig`][] builder is **not part of the public API**.
  It exists to perform discovery/merging and then ``freeze()`` to a `Config` just before
  execution. This keeps runtime deterministic and avoids accidental mutation.
- To "update config" programmatically, pass a mapping to the function call:

```python
from topmark import api

run = api.check(
    ["src"],
    config={
        "fields": {"project": "TopMark", "license": "MIT"},
        "header": {"fields": ["file", "project", "license"]},
        "formatting": {"align_fields": True},
        "files": {"file_types": ["python"], "exclude_patterns": [".venv"]},
    },
)
```
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from topmark.api.runtime import run_pipeline, select_pipeline
from topmark.api.view import finalize_run_result
from topmark.config.logging import get_logger
from topmark.constants import TOPMARK_VERSION
from topmark.pipeline.status import PlanStatus
from topmark.registry import Registry

from .public_types import PublicDiagnostic, PublicPolicy
from .types import FileResult, FileTypeInfo, Outcome, ProcessorInfo, RunResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from topmark.cli_shared.exit_codes import ExitCode
    from topmark.config import Config
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.contracts import Step

logger: TopmarkLogger = get_logger(__name__)


__all__: list[str] = [
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
    "PublicDiagnostic",
]


def check(
    paths: Iterable[Path | str],
    *,
    apply: bool = False,
    diff: bool = False,
    config: Mapping[str, Any] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    file_types: Sequence[str] | None = None,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    prune: bool = False,
) -> RunResult:
    """Validate or apply TopMark headers for the given paths.

    This is the programmatic equivalent of the CLI `topmark check`. It preserves
    the same discovery behavior when `config` is `None` and accepts optional
    policy overlays that are applied after discovery, before the pipeline runs.

    Args:
        paths (Iterable[Path | str]): Files and/or directories to process. Globs are
            allowed by the caller; TopMark will recurse and filter internally.
        apply (bool): If `True`, write changes in-place; otherwise perform a dry run.
        diff (bool): If `True`, include unified diffs for changes where applicable.
        config (Mapping[str, Any] | None): Optional plain mapping or frozen `Config`
            to seed configuration. When `None`, project discovery and layered merge
            are performed (defaults → project config → overrides).
        policy (PublicPolicy | None): Optional global policy overrides (public shape).
            These are merged after discovery using the standard policy resolution.
        policy_by_type (Mapping[str, PublicPolicy] | None): Optional per-type policy
            overrides (public shape) merged after discovery.
        file_types (Sequence[str] | None): Optional whitelist of TopMark file type
            identifiers to narrow discovery.
        skip_compliant (bool): Exclude already-compliant files from the returned view.
        skip_unsupported (bool): Exclude unsupported files from the returned view.
        prune (bool): If `True`, trim heavy views after the run (keeps summaries).

    Returns:
        RunResult: Filtered per-file outcomes, counts, diagnostics, and write stats.

    Notes:
        The `skip_compliant` and `skip_unsupported` flags affect only the
        **returned view** (which files appear and how counts are summarized).
        They do not change which files are *eligible* to be written when
        `apply=True`.
    """
    # Choose the concrete pipeline variant
    pipeline: Sequence[Step] = select_pipeline("check", apply=apply, diff=diff)

    # Run the pipeline; `_run_pipeline` handles discovery and applies policy overlays
    _cfg: Config
    file_list: list[Path]
    results: list[ProcessingContext]
    encountered_error_code: ExitCode | None
    _cfg, file_list, results, encountered_error_code = run_pipeline(
        pipeline=pipeline,
        paths=paths,
        base_config=config,  # `None` preserves discovery; mapping/Config is honored
        file_types=file_types,
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
    config: Mapping[str, Any] | None = None,
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
    file_types: Sequence[str] | None = None,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    prune: bool = False,
) -> RunResult:
    """Remove TopMark headers from files (dry-run or apply).

    This is the programmatic equivalent of the CLI `topmark strip`. When `config`
    is `None`, the function performs the same project discovery as the CLI and then
    applies optional policy overlays before running the pipeline.

    Args:
        paths (Iterable[Path | str]): Files and/or directories to process. Globs are allowed.
        apply (bool): If `True`, write changes in-place; otherwise perform a dry run.
        diff (bool): If `True`, include unified diffs for changes where applicable.
        config (Mapping[str, Any] | None): Optional plain mapping or frozen `Config`
            to seed configuration. When `None`, project discovery and layered merge
            are performed (defaults → project config → overrides).
        policy (PublicPolicy | None): Optional global policy overrides (public shape).
            Currently strip flows are policy-agnostic, but this is accepted for forward
            compatibility.
        policy_by_type (Mapping[str, PublicPolicy] | None): Optional per-type policy
            overrides (public shape).
        file_types (Sequence[str] | None): Optional whitelist of TopMark file type identifiers.
        skip_compliant (bool): Exclude already-compliant files from the returned view.
        skip_unsupported (bool): Exclude unsupported files from the returned view.
        prune (bool): If `True`, trim heavy views after the run (keeps summaries).

    Returns:
        RunResult: Filtered per-file outcomes, counts, diagnostics, and write stats.

    Notes:
        The `skip_*` flags affect only the **returned view** and do not modify
        pipeline write decisions.
    """
    # Choose the concrete pipeline variant
    pipeline: Sequence[Step] = select_pipeline("strip", apply=apply, diff=diff)

    # Run the pipeline; `_run_pipeline` handles discovery and applies policy overlays
    _cfg: Config
    file_list: list[Path] = []
    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None = None
    _cfg, file_list, results, encountered_error_code = run_pipeline(
        pipeline=pipeline,
        paths=paths,
        base_config=config,  # `None` preserves discovery; mapping/Config is honored
        file_types=file_types,
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


def get_filetype_info(long: bool = False) -> list[FileTypeInfo]:
    """Return metadata about registered file types.

    Args:
        long (bool): If `True`, include extended metadata such as patterns and policy.

    Returns:
        list[FileTypeInfo]: A list of `FileTypeInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `FileTypeRegistry` from
        [`topmark.registry`][]. This function returns metadata (not the objects).
    """
    proc_reg: Mapping[str, object] = Registry.processors()

    items: list[FileTypeInfo] = []
    for name, ft in Registry.filetypes().items():
        processor = proc_reg.get(name, None) if proc_reg else None
        supported = bool(processor)
        processor_name: str | None = processor.__class__.__name__ if processor else None
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
        long (bool): If True, include extended details for line/block delimiters.

    Returns:
        list[ProcessorInfo]: A list of `ProcessorInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `HeaderProcessorRegistry` from
        [`topmark.registry`][]. This function returns metadata (not the objects).
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
