# topmark:header:start
#
#   project      : TopMark
#   file         : runtime.py
#   file_relpath : src/topmark/api/runtime.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Internal runtime helpers for the public API.

This module contains typed helpers that orchestrate:
- layered resolved-config construction for discovery
- candidate file resolution
- config-like runtime policy overlay application
- execution-only `RunOptions` consumption
- pipeline selection and execution

These functions are **internal to the `topmark.api` package**:
- They are not re-exported from `topmark.api`.
- They may change in minor releases as internal architecture evolves.

Public consumers should call `topmark.api.check()` / `topmark.api.strip()` instead.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_mapping
from topmark.config.io.resolution import build_effective_config_for_path
from topmark.config.io.resolution import discover_config_layers
from topmark.config.io.resolution import load_resolved_config
from topmark.config.model import Config
from topmark.config.model import MutableConfig
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import PolicyOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.constants import TOPMARK_VERSION
from topmark.core.errors import InvalidPolicyError
from topmark.core.logging import get_logger
from topmark.diagnostic.model import DiagnosticLog
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.pipelines import Pipeline
from topmark.resolution.files import resolve_file_list

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence

    from topmark.api.types import PipelineKindLiteral
    from topmark.api.types import PublicPolicy
    from topmark.config.io.types import ConfigLayer
    from topmark.core.exit_codes import ExitCode
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.runtime.model import RunOptions

logger: TopmarkLogger = get_logger(__name__)


def ensure_mutable_config(
    config: Mapping[str, object] | MutableConfig | Config | None,
) -> MutableConfig:
    """Return a **MutableConfig** from a mapping or a frozen `Config`.

    This adapter normalizes public inputs (``Mapping[str, object]`` or frozen ``Config``) to a
    mutable draft that internal runtime helpers can merge, inspect, and re-freeze.

    Args:
        config: Optional (TOML) mapping, draft, or frozen config instance.

    Returns:
        A mutable draft configuration.

    Note:
        Public API functions accept mappings or frozen `Config` instances. Passing a `MutableConfig`
        is an internal/testing convenience, not part of the public API contract.
    """
    if config is None:
        logger.debug("No config provided - returning MutableConfig.from_defaults()")
        return mutable_config_from_defaults()
    if isinstance(config, MutableConfig):
        logger.debug("Supplied config is MutableConfig - returning as is")
        return config
    if isinstance(config, Config):
        # Thaw a frozen Config into a mutable draft.
        logger.debug("Supplied config is Config - returning MutableConfig")
        return MutableConfig(
            policy=config.policy.thaw(),
            policy_by_type={k: v.thaw() for k, v in config.policy_by_type.items()},
            config_files=list(config.config_files),
            strict_config_checking=config.strict_config_checking,
            header_fields=list(config.header_fields),
            field_values=dict(config.field_values),
            align_fields=config.align_fields,
            relative_to_raw=config.relative_to_raw,
            relative_to=config.relative_to,
            files=list(config.files),
            include_from=list(config.include_from),
            exclude_from=list(config.exclude_from),
            files_from=list(config.files_from),
            include_pattern_groups=list(config.include_pattern_groups),
            exclude_pattern_groups=list(config.exclude_pattern_groups),
            include_file_types=set(config.include_file_types),
            exclude_file_types=set(config.exclude_file_types),
            diagnostics=DiagnosticLog.from_iterable(config.diagnostics),
        )
    # Accept a plain mapping and normalize it through the TOML-like config loader.
    logger.debug("Supplied config is TOML Mapping - returning mutable_config_from_mapping(config)")
    return mutable_config_from_mapping(config)


# ---- Resolved config construction helpers ----


def _build_resolved_config_for_run(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, object] | Config | None,
    include_file_types: Sequence[str] | None,
    exclude_file_types: Sequence[str] | None,
) -> Config:
    """Build the layered, file-backed config for an API run.

    This function resolves only config that legitimately participates in layered
    discovery and per-path effective config construction. It must not apply
    execution intent such as apply mode, stdin mode, output routing, file write
    strategy, or run timestamps.

    Resolution mode:

    - when `base_config is None`, perform normal layered discovery via `load_resolved_config()`
      using the supplied paths as discovery anchors
    - when `base_config` is provided, treat it as an explicit seed and skip discovery
    - in both modes, apply final file/file-type intent via `apply_config_overrides()` before
      freezing

    Args:
        paths: Files and/or directories to process.
        base_config: Optional explicit config seed. When omitted, layered config
            discovery is used. When provided, discovery is skipped.
        include_file_types: Optional file-type allowlist override used during
            candidate resolution.
        exclude_file_types: Optional file-type denylist override used during
            candidate resolution.

    Returns:
        The frozen resolved configuration that serves as the base for file discovery
        and later policy overlay application.
    """
    logger.debug("Normalizing input paths: %s", paths)

    # Normalize input paths to strings for stable downstream override handling.
    paths_str: list[str] = [str(Path(p)) for p in paths]

    if base_config is None:
        # Layered discovery mode: defaults -> discovered config -> explicit config
        # files (none here). Use the first input as the discovery anchor, or CWD
        # when no explicit paths were supplied.
        anchor_inputs: list[Path] = [Path(p) for p in paths_str] or [Path.cwd()]
        draft: MutableConfig = load_resolved_config(
            input_paths=tuple(anchor_inputs),
            extra_config_files=(),
        )
    else:
        # Explicit seed mode: start from defaults, merge the supplied mapping /
        # frozen Config on top, and skip all config discovery.
        seeded: MutableConfig = ensure_mutable_config(base_config)
        draft = mutable_config_from_defaults().merge_with(seeded)

    # Apply file/file-type intent needed for candidate resolution. This remains
    # part of the resolved config because it directly affects which files are
    # considered by the resolver.
    overrides = ConfigOverrides(
        config_origin="<API overrides>",
        config_base=Path.cwd().resolve(),
        files=paths_str,
        include_file_types=list(include_file_types) if include_file_types is not None else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types is not None else None,
    )
    draft = apply_config_overrides(
        draft,
        overrides=overrides,
    )

    return draft.freeze()


# ---- Candidate file resolution helpers ----


def _resolve_candidate_files(cfg: Config) -> list[Path]:
    """Resolve the candidate file list for a resolved frozen config.

    This helper exists to make the API runtime split explicit:

    - first build the resolved config used for discovery
    - then resolve the candidate file list from that config
    - only afterwards apply runtime overlays for execution

    Args:
        cfg: Resolved frozen config whose discovery-related fields should be used to build the
            candidate file list.

    Returns:
        The resolved and filtered candidate file list.
    """
    file_list: list[Path] = resolve_file_list(cfg)
    logger.debug("Files found: %s", len(file_list))
    return file_list


# ---- Layer discovery / per-path config helpers ----


def _discover_layers_for_api_run(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, object] | Config | None,
) -> list[ConfigLayer] | None:
    """Discover config layers for an API run when layered discovery is active.

    Explicit `base_config` seeds intentionally bypass layered discovery, so this helper returns
    `None` in that mode.

    Args:
        paths: Input paths for the run. The first path is used as the discovery anchor, mirroring
            the normal config discovery behavior.
        base_config: Optional explicit config seed supplied by the caller.

    Returns:
        The discovered config layers for the run, or `None` when layered discovery is intentionally
        bypassed.
    """
    if base_config is not None:
        return None

    path_list: list[Path] = [Path(p) for p in paths] or [Path.cwd()]
    return discover_config_layers(
        input_paths=tuple(path_list),
        extra_config_files=(),
        strict_config_checking=None,
        no_config=False,
    )


def _build_path_configs(
    *,
    layers: Sequence[ConfigLayer] | None,
    file_list: Sequence[Path],
    effective_cfg: Config,
) -> dict[Path, Config]:
    """Build per-path effective layered configs for a run.

    When provenance layers are available, each file path receives a config built from the subset of
    layers whose scope applies to that path. Config-like runtime policy overlays are copied onto the
    per-path effective config.

    When no layers are available, this helper falls back to using the single run-level config for
    every path.

    Args:
        layers: Optional discovered config provenance layers for the run.
        file_list: Files that will be processed.
        effective_cfg: Final frozen layered config carrying any runtime policy overlays.

    Returns:
        A mapping from file path to the effective frozen config that should be used when
        bootstrapping that file's processing context.
    """
    if layers is None:
        return dict.fromkeys(file_list, effective_cfg)

    path_configs: dict[Path, Config] = {}
    for path in file_list:
        per_path_cfg: Config = build_effective_config_for_path(layers, path).freeze()
        path_configs[path] = replace(
            per_path_cfg,
            policy=effective_cfg.policy,
            policy_by_type=effective_cfg.policy_by_type,
        )

    return path_configs


# ---- Runtime overlay helpers ----


def _apply_runtime_policy_overlays(
    cfg: Config,
    *,
    policy: PublicPolicy | None,
    policy_by_type: Mapping[str, PublicPolicy] | None,
) -> Config:
    """Apply invocation-scoped policy overlays to a resolved layered config.

    These overlays affect processing behavior, but they are still config-like: they modify policy
    resolution rather than execution transport or output intent.

    Args:
        cfg: The resolved config to overlay.
        policy: Optional global public policy overlay.
        policy_by_type: Optional per-type public policy overlays.

    Returns:
        The final frozen layered config for the run after applying any runtime policy overlays.
    """
    if policy is None and policy_by_type is None:
        return cfg

    # Start from the resolved frozen config and apply config-like policy intent on top.
    draft: MutableConfig = cfg.thaw()

    policy_overrides: PolicyOverrides = (
        _build_public_policy_overrides(policy) if policy is not None else PolicyOverrides()
    )
    policy_by_type_overrides: dict[str, PolicyOverrides] = (
        _build_public_policy_by_type_overrides(policy_by_type) if policy_by_type is not None else {}
    )
    draft = apply_config_overrides(
        draft,
        ConfigOverrides(
            config_origin="<API policy overrides>",
            config_base=Path.cwd().resolve(),
            policy=policy_overrides,
            policy_by_type=policy_by_type_overrides,
        ),
    )

    return draft.freeze()


def select_pipeline(
    kind: PipelineKindLiteral,
    *,
    apply: bool,
    diff: bool,
) -> Sequence[Step[ProcessingContext]]:
    """Return the concrete pipeline steps for the requested operation and mode.

    Args:
        kind: The pipeline family to use (`"check"` or `"strip"`).
        apply: If `True`, choose an `*_APPLY*` variant.
        diff: If `True`, choose a `*PATCH*` variant that includes unified diffs.

    Returns:
        The ordered list of steps to execute.
    """
    # TODO: If a future public/API mode needs header rendering without apply, wire it here
    # instead of introducing ad-hoc branching at call sites.
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


def _resolve_public_header_mutation_mode(value: str) -> HeaderMutationMode:
    """Return the internal enum for a public header-mutation token."""
    try:
        return HeaderMutationMode(value)
    except ValueError as exc:
        raise InvalidPolicyError(
            message=f"Invalid value for header_mutation_mode: {value!r}",
            policy_key="header_mutation_mode",
        ) from exc


def _resolve_public_empty_insert_mode(value: str) -> EmptyInsertMode:
    """Return the internal enum for a public empty-insert token."""
    try:
        return EmptyInsertMode(value)
    except ValueError as exc:
        raise InvalidPolicyError(
            message=f"Invalid value for empty_insert_mode: {value!r}",
            policy_key="empty_insert_mode",
        ) from exc


def _build_public_policy_overrides(policy: PublicPolicy) -> PolicyOverrides:
    """Convert a public policy mapping into structured internal overrides.

    Args:
        policy: Public policy overlay.

    Returns:
        Structured internal policy overrides.
    """
    return PolicyOverrides(
        header_mutation_mode=(
            _resolve_public_header_mutation_mode(policy["header_mutation_mode"])
            if "header_mutation_mode" in policy
            else None
        ),
        allow_header_in_empty_files=(
            bool(policy["allow_header_in_empty_files"])
            if "allow_header_in_empty_files" in policy
            else None
        ),
        empty_insert_mode=(
            _resolve_public_empty_insert_mode(policy["empty_insert_mode"])
            if "empty_insert_mode" in policy
            else None
        ),
        render_empty_header_when_no_fields=(
            bool(policy["render_empty_header_when_no_fields"])
            if "render_empty_header_when_no_fields" in policy
            else None
        ),
        allow_reflow=(bool(policy["allow_reflow"]) if "allow_reflow" in policy else None),
        allow_content_probe=(
            bool(policy["allow_content_probe"]) if "allow_content_probe" in policy else None
        ),
    )


def _build_public_policy_by_type_overrides(
    policy_by_type: Mapping[str, PublicPolicy],
) -> dict[str, PolicyOverrides]:
    """Convert public per-file-type policy overlays into internal overrides.

    Args:
        policy_by_type: Per-file-type public policy overlays.

    Returns:
        Structured internal per-file-type policy overrides.
    """
    return {ft: _build_public_policy_overrides(spec) for ft, spec in policy_by_type.items()}


def run_pipeline(
    *,
    pipeline: Sequence[Step[ProcessingContext]],
    paths: Iterable[Path | str],
    run_options: RunOptions,
    base_config: Mapping[str, object] | Config | None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    # public-policy overlays (None = no override)
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
) -> tuple[Config, list[Path], list[ProcessingContext], ExitCode | None]:
    """Resolve layered config and files, consume runtime options, and run the pipeline.

    Behavior:
        * Build the resolved layered config used for candidate discovery.
        * Apply runtime policy overlays to that layered config.
        * Consume execution-only `RunOptions` supplied by the caller.
        * Resolve the candidate file list from the layered config.
        * Build per-path effective configs when layered discovery is active.
        * Execute the selected pipeline for each file.

    Args:
        pipeline: The pipeline (steps) to apply.
        paths: Files and/or directories to process.
        run_options: Invocation-wide execution-only runtime options for the run.
        base_config: `None` for normal layered discovery; otherwise an explicit config seed supplied
            directly by the caller.
        include_file_types: Optional allowlist of file type identifiers used for candidate
            resolution.
        exclude_file_types: Optional denylist of file type identifiers used for candidate
            resolution.
        policy: Optional global public policy overlay applied after config resolution and file
            discovery.
        policy_by_type: Optional per-type public policy overlays applied after config resolution and
            file discovery.

    Returns:
        A tuple containing:
            * the final frozen layered config used for execution
            * the resolved/filtered candidate file list
            * the resulting processing contexts
            * an exit code indicating a fatal condition, if any
    """
    logger.info("Building config and file list for paths: %s", paths)

    path_inputs: list[Path | str] = list(paths)
    discovered_layers: list[ConfigLayer] | None = _discover_layers_for_api_run(
        path_inputs,
        base_config=base_config,
    )

    # 1) Build the resolved layered config used for discovery. Runtime policy overlays,
    # caller-supplied run options, and candidate resolution are handled below.
    cfg: Config = _build_resolved_config_for_run(
        path_inputs,
        base_config=base_config,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
    )
    logger.debug("(1) - resolved config before runtime overlays): %s", cfg)

    # 2) Apply runtime policy overlays after layered config resolution.
    effective_cfg: Config = _apply_runtime_policy_overlays(
        cfg,
        policy=policy,
        policy_by_type=policy_by_type,
    )
    logger.debug("(2) Effective config after runtime policy overlays: %s", effective_cfg)

    # 3) Consume execution-only run options supplied by the caller.
    logger.debug("(3) Run options for invocation: %s", run_options)

    # 4) Resolve the candidate file list after policy overlays.
    file_list: list[Path] = _resolve_candidate_files(effective_cfg)

    if not file_list:
        return effective_cfg, file_list, [], None

    # 5) Build per-path effective configs for layered discovery.
    path_configs: dict[Path, Config] = _build_path_configs(
        layers=discovered_layers,
        file_list=file_list,
        effective_cfg=effective_cfg,
    )

    logger.debug("(5) Effective layered config for execution: %s", effective_cfg)

    # 6) Execute the selected pipeline for each resolved file.
    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None
    results, encountered_error_code = run_steps_for_files(
        run_options=run_options,
        config=effective_cfg,
        path_configs=path_configs,
        pipeline=pipeline,
        file_list=file_list,
    )

    logger.info("Processing %d files with TopMark %s", len(file_list), TOPMARK_VERSION)

    return effective_cfg, file_list, results, encountered_error_code
