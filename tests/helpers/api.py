# topmark:header:start
#
#   project      : TopMark
#   file         : api.py
#   file_relpath : tests/helpers/api.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for API-layer tests.

This module contains pure test utilities used by `tests/api/*` and related
high-level integration-style tests that exercise TopMark through its public
Python API.

The helpers here intentionally cover two distinct API-entry styles:
    - fully materialized `Config` objects and engine-level execution helpers
    - TOML-shaped config mappings passed directly to `api.check()` / `api.strip()`

These helpers are kept outside `conftest.py` so their logic remains explicit,
importable, and reusable without relying on pytest fixture discovery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api
from topmark.api.runtime import select_pipeline
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft
from topmark.pipeline.engine import run_steps_for_files
from topmark.resolution.files import resolve_file_list
from topmark.runtime.model import RunOptions
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.api.types import PipelineKindLiteral
    from topmark.api.types import PublicPolicy
    from topmark.api.types import PublicReportScopeLiteral
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.toml.types import TomlValue

# --- Config-related helpers ---


def config_mapping(**overrides: TomlValue) -> dict[str, TomlValue]:
    """Build a minimal TOML-shaped mapping for API calls that accept `config=`.

    This helper is intentionally narrow: it exercises the public API branch
    where callers pass a plain mapping instead of a fully constructed
    [`Config`][topmark.config.model.Config]. The returned object mirrors the
    layered TOML/config fragment shape expected by
    [`mutable_config_from_mapping()`][topmark.config.io.deserializers.mutable_config_from_mapping].

    Notes:
        * Only a tiny base is provided (`files.include_file_types = ["python"]`)
          so tests stay explicit about what is enabled.
        * Merging of `overrides` is shallow at the top level for convenience.
        * No layered discovery, source-level TOML validation, path
          normalization, or `PatternSource` coercion happens here. Tests that
          need those behaviors should use helpers from `tests.helpers.config`
          or the TOML-layer helpers instead.

    Args:
        **overrides: Top-level layered-config fragment overrides such as
            `files={...}` or `policy={...}`.

    Returns:
        A plain layered-config mapping suitable for
        `api.check(..., config=...)` or `api.strip(..., config=...)`.
    """
    base: dict[str, TomlValue] = {
        Toml.SECTION_FILES: {
            # When provided, discovery should consider only these types
            Toml.KEY_INCLUDE_FILE_TYPES: ["python"],
        },
    }
    for k, v in overrides.items():
        existing: TomlValue | None = base.get(k)

        # We use 'existing' as a local variable so Pyright can safely narrow
        # the type to dict[str, TomlValue] after the isinstance check.
        if isinstance(v, dict) and isinstance(existing, dict):
            existing.update(v)  # shallow merge for convenience in tests
        else:
            base[k] = v
    return base


# --- Pipeline helpers


def by_path_outcome(run_result: api.RunResult) -> dict[Path, str]:
    """Return a mapping of each file path to its outcome string.

    This is a small assertion helper for tests that only care about the final
    per-path outcome classification and not the full `RunResult` object.
    """
    return {fr.path: fr.outcome.value for fr in run_result.files}


def api_check_dir(
    root: Path,
    *,
    apply: bool = False,
    policy: PublicPolicy | None = None,
    report: PublicReportScopeLiteral = "all",
    include_file_types: Iterable[str] | None = None,
    exclude_file_types: Iterable[str] | None = None,
    prune: bool = False,
) -> api.RunResult:
    """Run [`topmark.api.check`][topmark.api.check] against `root / 'src'` with common defaults.

    By default, does not exclude any file types (no blacklist).

    Args:
        root: Repository-like temporary root whose `src/` subtree should be processed.
        apply: Whether to run in apply mode.
        policy: Optional public policy overlay.
        report: Report-scope selection for the returned API view.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        prune: Whether to prune heavy views in the returned `RunResult`.

    Returns:
        Result of `api.check(...)` over `root / "src"`.
    """
    paths: list[Path] = [root / "src"]
    return api.check(
        paths,
        apply=apply,
        config=None,  # let API load topmark.toml from repo root
        include_file_types=list(include_file_types) if include_file_types else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types else None,
        policy=policy,
        report=report,
        prune_views=prune,
    )


def api_strip_dir(
    root: Path,
    *,
    apply: bool = False,
    policy: PublicPolicy | None = None,
    report: PublicReportScopeLiteral = "all",
    include_file_types: Iterable[str] | None = None,
    exclude_file_types: Iterable[str] | None = None,
    prune: bool = False,
) -> api.RunResult:
    """Run [`topmark.api.strip`][topmark.api.strip] against `root / 'src'` with common defaults.

    By default, does not exclude any file types (no blacklist).

    Args:
        root: Repository-like temporary root whose `src/` subtree should be processed.
        apply: Whether to run in apply mode.
        policy: Optional public policy overlay.
        report: Report-scope selection for the returned API view.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        prune: Whether to prune heavy views in the returned `RunResult`.

    Returns:
        Result of `api.strip(...)` over `root / "src"`.
    """
    paths: list[Path] = [root / "src"]
    return api.strip(
        paths,
        apply=apply,
        config=None,
        include_file_types=list(include_file_types) if include_file_types else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types else None,
        policy=policy,
        report=report,
        prune_views=prune,
    )


def run_cli_like(
    anchor: Path,
    kind: PipelineKindLiteral,
    apply: bool = False,
    diff: bool = False,
    prune_views: bool = False,
    include_file_types: tuple[str, ...] = (),
    exclude_file_types: tuple[str, ...] = (),
) -> tuple[MutableConfig, list[Path], list[ProcessingContext]]:
    """Execute the selected pipeline using the same config-loading path as the CLI.

    This helper resolves TOML sources through the authoritative bridge used by
    CLI-like flows, freezes the resulting config, resolves the file list, and
    then runs the selected pipeline with explicit runtime options.

    It is useful for tests that want engine-level results while still honoring
    layered config discovery and resolution semantics.
    """
    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=(anchor,),
    )
    draft.files = [str(anchor)]  # seed positional inputs
    if include_file_types:
        draft.include_file_types = set(include_file_types)
    if exclude_file_types:
        draft.exclude_file_types = set(exclude_file_types)

    cfg: Config = draft.freeze()
    files: list[Path] = resolve_file_list(cfg)
    run_options: RunOptions = RunOptions(
        apply_changes=apply,
        prune_views=prune_views,
    )

    results: list[ProcessingContext]
    _exit_code: ExitCode | None
    pipeline: Sequence[Step[ProcessingContext]] = select_pipeline(kind, apply=apply, diff=diff)
    results, _exit_code = run_steps_for_files(
        run_options=run_options,
        config=cfg,
        path_configs=None,
        pipeline=pipeline,
        file_list=files,
    )
    return draft, files, results
