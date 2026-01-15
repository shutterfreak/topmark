# topmark:header:start
#
#   project      : TopMark
#   file         : runtime.py
#   file_relpath : src/topmark/api/runtime.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Runtime helpers for the public API.

This module contains **typed**, non-underscored helpers that orchestrate
configuration discovery/normalization and pipeline execution. Keeping these
helpers outside `topmark.api.__init__` maintains a clean public surface while
remaining importable under strict typing.

The functions here are considered **internal API** for the package; they are
not re-exported from `topmark.api` and may change in minor versions. Public
consumers should call `topmark.api.check()` / `topmark.api.strip()` instead.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from topmark.config import Config, MutableConfig
from topmark.config.logging import get_logger
from topmark.config.policy import MutablePolicy
from topmark.constants import TOPMARK_VERSION
from topmark.file_resolver import resolve_file_list
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.pipelines import Pipeline
from topmark.registry import Registry

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from topmark.config.logging import TopmarkLogger
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step

    from .public_types import PublicPolicy

logger: TopmarkLogger = get_logger(__name__)

__all__: list[str] = [
    "ensure_mutable_config",
    "build_cfg_and_files_via_cli_helpers",
    "select_pipeline",
    "run_pipeline",
]


def ensure_mutable_config(
    config: Mapping[str, Any] | MutableConfig | Config | None,
) -> MutableConfig:
    """Return a **MutableConfig** from a mapping or a frozen `Config`.

    This adapter normalizes public inputs (``Mapping[str, Any]`` or frozen ``Config``)
    to a **mutable** builder for merging and final ``freeze()`` before pipeline execution.

    Args:
        config (Mapping[str, Any] | MutableConfig | Config | None): Optional (TOML) mapping,
            draft, or frozen config instance.

    Returns:
        MutableConfig: A mutable draft configuration.

    Note:
        Public API functions accept **mappings** or **frozen** configs. Passing a
        `MutableConfig` is not part of the public contract; this helper accepts it
        internally for convenience during discovery tests.
    """
    if config is None:
        logger.debug("No config provided - returning MutableConfig.from_defaults()")
        return MutableConfig.from_defaults()
    if isinstance(config, MutableConfig):
        logger.debug("Supplied config is MutableConfig - returning as is")
        return config
    if isinstance(config, Config):
        # Thaw a frozen Config into a mutable draft
        logger.debug("Supplied config is Config - returning MutableConfig")
        return MutableConfig(
            timestamp=config.timestamp,
            verbosity_level=config.verbosity_level,
            apply_changes=config.apply_changes,
            policy=config.policy.thaw(),
            policy_by_type={k: v.thaw() for k, v in config.policy_by_type.items()},
            config_files=list(config.config_files),
            header_fields=list(config.header_fields),
            field_values=dict(config.field_values),
            align_fields=config.align_fields,
            header_format=config.header_format,
            relative_to_raw=config.relative_to_raw,
            relative_to=config.relative_to,
            stdin_mode=config.stdin_mode,
            files=list(config.files),
            include_patterns=list(config.include_patterns),
            include_from=list(config.include_from),
            exclude_patterns=list(config.exclude_patterns),
            exclude_from=list(config.exclude_from),
            files_from=list(config.files_from),
            file_types=set(config.file_types),
        )
    # Accept plain dict-like, normalize to internal MutableConfig via TOML-like dict
    logger.debug("Supplied config is TOML Mapping - returning MutableConfig.from_toml_dict(config)")
    return MutableConfig.from_toml_dict(dict(config))


def build_cfg_and_files_via_cli_helpers(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, Any] | Config | None,
    file_types: Sequence[str] | None,
) -> tuple[Config, list[Path]]:
    """Build a frozen `Config` and resolve files using the same rules as the CLI.

    Two modes are supported:

    * Seeded mode (`base_config` provided):
        - Normalize `paths` from the current working directory (CLI parity).
        - Start from defaults, merge the provided `base_config` (mapping or frozen `Config`)
          using the same merge semantics as the CLI, and **do not** discover project configs.
        - Resolve the file list with `resolve_file_list(cfg)`.

    * Discovery mode (`base_config` is `None`):
        - Perform layered discovery via `MutableConfig.load_merged`, starting from the
          first `paths` element (its parent if it is a file) or CWD when `paths` is empty.
        - Discovery order: defaults → user → project (root→current; per-dir: pyproject then topmark)
          → extra config files (none here) → CLI-like overrides.
        - Evaluate globs declared in discovered configs relative to each config file's directory.

    Args:
        paths (Iterable[Path | str]): Files and/or directories to process. Items are
            normalized to strings early for stability and logging. Empty input falls
            back to CWD as the discovery anchor in discovery mode.
        base_config (Mapping[str, Any] | Config | None): Optional mapping or frozen
            `Config` to seed from. When provided, discovery is skipped and only the
            provided configuration is honored.
        file_types (Sequence[str] | None): Optional whitelist of file type identifiers
            to seed the draft for parity with CLI behavior.

    Returns:
        tuple[Config, list[Path]]: A 2-tuple `(cfg, files)` where `cfg` is the frozen
        configuration used to resolve files and `files` is the resolved/filtered list.

    Notes:
        * In both modes, input `paths` are normalized to strings, assigned to the draft's
          `files`, then the final `cfg` is frozen prior to calling `resolve_file_list`.
        * This helper deliberately avoids side effects beyond logging. All config
          discovery and merge logic is delegated to `MutableConfig`.
    """
    # Start from a mutable draft; we only build the frozen Config right before use
    draft: MutableConfig = ensure_mutable_config(base_config)

    logger.debug("Normalizing input paths: %s", paths)

    # Normalize input paths to strings from CWD for stability and logging parity with CLI.
    paths_str: list[str] = [str(Path(p)) for p in paths]

    # If the caller supplied a mapping/Config, discovery is intentionally skipped.
    # Only the provided config is honored, and project config is NOT merged.
    if base_config is not None:
        # Start from defaults so that header fields/values are present unless overridden
        draft_defaults: MutableConfig = MutableConfig.from_defaults()
        draft = draft_defaults.merge_with(draft)

        # Assign normalized paths to draft.files for consistency
        draft.files = list(paths_str)
        logger.debug("Found %d input paths", len(draft.files))
        if file_types:
            draft.file_types = set(file_types)
        # Freeze the config before resolving files,
        # as resolve_file_list expects an immutable Config.
        cfg: Config = draft.freeze()
        file_list: list[Path] = resolve_file_list(cfg)
        logger.debug("Files found: %s", len(file_list))
        return cfg, file_list

    # Otherwise, perform project-config discovery & merge using the authoritative loader.
    # If input paths are empty, anchor discovery at CWD.
    # If the first path is a file, use its parent.
    anchor_inputs: list[Path] = [Path(p) for p in paths_str] or [Path.cwd()]
    draft = MutableConfig.load_merged(
        input_paths=tuple(anchor_inputs),
        extra_config_files=(),  # none here; API parity with "no --config"
    )

    # Assign normalized paths to draft.files for CLI-like override semantics.
    draft.files = list(paths_str)
    if file_types:
        draft.file_types = set(file_types)
    # Freeze the config before resolving files, as resolve_file_list expects an immutable Config.
    cfg = draft.freeze()
    file_list = resolve_file_list(cfg)
    logger.debug("Files found: %s", len(file_list))
    return cfg, file_list


def select_pipeline(kind: Literal["check", "strip"], *, apply: bool, diff: bool) -> Sequence[Step]:
    """Return the concrete pipeline steps for the requested kind and intent.

    Args:
        kind (Literal["check","strip"]): The pipeline family to use.
        apply (bool): If `True`, choose an *_APPLY* variant.
        diff (bool): If `True`, choose a *PATCH* variant (includes unified diffs).

    Returns:
        Sequence[Step]: The ordered list of steps to execute.
    """
    # NOTE: Print existing header: new command!
    # NOTE: if we decide to add '--print-header' (not with '--appy'): Pipeline.CHECK_RENDER
    if kind == "check":
        return (
            Pipeline.CHECK_APPLY_PATCH.steps
            if apply and diff
            else Pipeline.CHECK_APPLY.steps
            if apply
            else Pipeline.CHECK_PATCH.steps
            if diff
            else Pipeline.CHECK.steps
        )
    # kind == "strip"
    return (
        Pipeline.STRIP_APPLY_PATCH.steps
        if apply and diff
        else Pipeline.STRIP_APPLY.steps
        if apply
        else Pipeline.STRIP_PATCH.steps
        if diff
        else Pipeline.STRIP.steps
    )


def run_pipeline(
    *,
    pipeline: Sequence[Step],
    paths: Iterable[Path | str],
    base_config: Mapping[str, Any] | Config | None,
    file_types: Sequence[str] | None,
    apply_changes: bool,
    prune: bool = False,
    # public-policy overlays (None = no override)
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
) -> tuple[Config, list[Path], list[ProcessingContext], ExitCode | None]:
    """Resolve config & files, apply policy overlays, register processors, run steps.

    Behavior:
        * If `base_config is None`, perform full project discovery (same rules as the CLI),
          then apply **public policy overlays** (if provided) to the discovered draft,
          freeze it to `Config`, and set `apply_changes` for this run.
        * If `base_config` is a mapping or frozen `Config`, normalize it to a draft,
          then apply **public policy overlays** and freeze.
        * Uses the same file list resolver as the CLI to honor include/exclude rules.
        * Ensures processors are registered before running the steps.

    Args:
        pipeline (Sequence[Step]): The pipeline (steps) to apply.
        paths (Iterable[Path | str]): Files and/or directories to process.
        base_config (Mapping[str, Any] | Config | None): `None` for discovery; a mapping
            or `Config` to seed the run directly.
        file_types (Sequence[str] | None): Optional whitelist of file type identifiers.
        apply_changes (bool): When `True`, run in apply mode; otherwise dry run.
        prune (bool): If `True`, trim heavy views after the run (keeps summaries).
        policy (PublicPolicy | None): Optional global policy overlays (public shape)
            applied **after** discovery and before freezing.
        policy_by_type (Mapping[str, PublicPolicy] | None): Optional per-type policy
            overlays (public shape) applied **after** discovery and before freezing.

    Returns:
        tuple[Config, list[Path], list[ProcessingContext], ExitCode | None]: A tuple:
            * `Config`: The final (frozen) config used for the run.
            * `list[Path]`: Resolved/filtered file list.
            * `list[ProcessingContext]`: Pipeline results.
            * `ExitCode | None`: An exit code indicating a fatal condition (if any).
    """
    logger.info("Building config and file list for paths: %s", paths)

    # 1) Build config + resolve files using the same helpers as the CLI.
    #    This performs discovery when base_config is None; otherwise it honors mapping/Config.
    cfg: Config
    file_list: list[Path]
    cfg, file_list = build_cfg_and_files_via_cli_helpers(
        paths, base_config=base_config, file_types=file_types
    )
    logger.debug("cfg for run (1 - after build_cfg_and_files_via_cli_helpers): %s", cfg)

    # 2) Apply public policy overlays AFTER discovery, then materialize apply intent.
    draft: MutableConfig = cfg.thaw()
    if policy is not None:
        # Merge a shallow public policy into the tri-state MutablePolicy
        if "add_only" in policy:
            draft.policy.add_only = bool(policy["add_only"])
        if "update_only" in policy:
            draft.policy.update_only = bool(policy["update_only"])
        if "allow_header_in_empty_files" in policy:
            draft.policy.allow_header_in_empty_files = bool(policy["allow_header_in_empty_files"])

    if policy_by_type is not None:
        for ft, spec in policy_by_type.items():
            mp: MutablePolicy = draft.policy_by_type.get(ft) or MutablePolicy()
            if "add_only" in spec:
                mp.add_only = bool(spec["add_only"])
            if "update_only" in spec:
                mp.update_only = bool(spec["update_only"])
            if "allow_header_in_empty_files" in spec:
                mp.allow_header_in_empty_files = bool(spec["allow_header_in_empty_files"])
            draft.policy_by_type[ft] = mp

    cfg = draft.freeze()  # (No mutation of cfg - Config is frozen)
    logger.debug("cfg for run (2 - after applying policy overlays): %s", cfg)

    if not file_list:
        return cfg, file_list, [], None

    # Ensure all processors are registered before running the pipeline (idempotent)
    Registry.ensure_processors_registered()

    # 3) Final immutable snapshot for this run, carrying apply intent.
    cfg_for_run: Config = replace(cfg, apply_changes=apply_changes)

    logger.debug("cfg_for_run for run (3): %s", cfg_for_run)

    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None
    results, encountered_error_code = run_steps_for_files(
        file_list=file_list,
        pipeline=pipeline,
        config=cfg_for_run,
        prune=prune,
    )

    logger.info("Processing %d files with TopMark %s", len(file_list), TOPMARK_VERSION)

    return cfg, file_list, results, encountered_error_code
