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
- file-list resolution for pipeline execution
- config-like runtime policy overlay application
- execution-only `RunOptions` consumption
- config/preflight validation using effective resolved strictness across
  staged validation logs
- pipeline selection and execution

These functions are **internal to the `topmark.api` package**:
- They are not re-exported from `topmark.api`.
- They may change in minor releases as internal architecture evolves.

Public consumers should call `topmark.api.probe()`, `topmark.api.check()`, or
`topmark.api.strip()` instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.api.types import ApiPipelineRun
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_mapping
from topmark.config.model import FrozenConfig
from topmark.config.model import MutableConfig
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import PolicyOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_mutable_config
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import build_effective_config_for_path
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.constants import TOPMARK_VERSION
from topmark.core.errors import InvalidPolicyError
from topmark.core.logging import get_logger
from topmark.pipeline.engine import PipelineExecution
from topmark.pipeline.engine import exit_code_from_pipeline_results
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.synthetic import build_filtered_probe_contexts
from topmark.pipeline.synthetic import build_missing_file_contexts
from topmark.resolution.files import probe_explicit_file_selection
from topmark.resolution.files import resolve_file_list_with_diagnostics
from topmark.runtime.writer_options import WriterOptions
from topmark.runtime.writer_options import apply_resolved_writer_options

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence

    from topmark.api.types import PublicPolicy
    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.config.resolution.layers import ConfigLayer
    from topmark.core.exit_codes import ExitCode
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.protocols import Step
    from topmark.resolution.discovery import FileSelectionProbeResult
    from topmark.resolution.files import FileListResolution
    from topmark.runtime.model import RunOptions
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


logger: TopmarkLogger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True, slots=True)
class PreparedApiRun:
    """Shared resolved state needed to execute an API pipeline.

    This value object captures the common setup performed by all public API
    commands before command-specific orchestration begins. It is private to the
    API runtime layer and deliberately not re-exported from `topmark.api`.

    Attributes:
        effective_cfg: Final runtime config after layered discovery, explicit
            config seeding, file-type filters, and runtime policy overlays.
        run_options: Execution-only runtime options after persisted writer
            options have been applied.
        file_resolution: Diagnostic file-list resolution result.
        file_list: Selected files that should enter pipeline execution.
        discovered_layers: FrozenConfig provenance layers used to compute per-path
            effective configs, or `None` when discovery was bypassed.
    """

    effective_cfg: FrozenConfig
    run_options: RunOptions
    file_resolution: FileListResolution
    file_list: list[Path]
    discovered_layers: Sequence[ConfigLayer] | None


# ---- API run prepared value objects ----


@dataclass(frozen=True, kw_only=True, slots=True)
class PreparedTomlConfig:
    """TOML-side resolved state prepared for an API run.

    This value object replaces the private mixed tuple previously used while
    preparing layered config discovery. Both fields are `None` when the caller
    supplied an explicit `base_config`, because explicit config seeds
    intentionally bypass layered TOML discovery.

    Attributes:
        resolved: Resolved TOML-side state used for config provenance and
            writer-option discovery, or `None` when discovery was bypassed.
        draft: Pre-merged mutable config draft built from `resolved`, or `None`
            when discovery was bypassed.
    """

    resolved: ResolvedTopmarkTomlSources | None
    draft: MutableConfig | None


def ensure_mutable_config(
    config: Mapping[str, object] | MutableConfig | FrozenConfig | None,
) -> MutableConfig:
    """Return a **MutableConfig** from a mapping or immutable `Config`.

    This adapter normalizes public inputs (``Mapping[str, object]`` or immutable
    [`FrozenConfig`][topmark.config.model.FrozenConfig]) to a mutable draft that
    internal runtime helpers can merge, inspect, and re-freeze.

    Args:
        config: Optional (TOML) mapping, mutable, or immutable config instance.

    Returns:
        A mutable draft configuration.

    Note:
        Public API functions accept mappings or immutable
        [`FrozenConfig`][topmark.config.model.FrozenConfig] instances. Passing a
        mutable [`MutableConfig`][topmark.config.model.MutableConfig] is an
        internal/testing convenience, not part of the public API contract.
        It normalizes config-like inputs, but it is not a TOML schema-validation entry point.
    """
    if config is None:
        logger.debug("No config provided - returning MutableConfig.from_defaults()")
        return mutable_config_from_defaults()
    if isinstance(config, MutableConfig):
        logger.debug("Supplied config is MutableConfig - returning as is")
        return config
    if isinstance(config, FrozenConfig):
        # Thaw a n immutable FrozenConfig into a mutable draft while preserving
        # staged validation logs and the flattened compatibility diagnostics.
        logger.debug("Supplied config is FrozenConfig - returning config.thaw()")
        return config.thaw()
    # Accept a plain mapping and normalize it through the TOML-like config loader.
    logger.debug("Supplied config is TOML Mapping - returning mutable_config_from_mapping(config)")
    return mutable_config_from_mapping(config)


# ---- Config validation ----


def is_config_valid(
    cfg: FrozenConfig | MutableConfig,
    *,
    resolved: ResolvedTopmarkTomlSources,
    override: bool | None = None,
) -> bool:
    """Return whether the config is valid under effective resolved strictness.

    Config validity follows the staged config-loading validation semantics:
    TOML-source diagnostics, merged-config diagnostics, and
    runtime-applicability diagnostics are evaluated together. In non-strict
    mode, validation fails only when at least one stage contains an error
    diagnostic. In strict mode, validation fails when any stage contains either
    a warning or an error diagnostic.

    The strictness used here is the effective resolved value of
    `strict`, derived from:
    - an explicit API/CLI override when provided,
    - otherwise the TOML-resolved source-local preference in `resolved`,
    - otherwise non-strict behavior.

    The flattened compatibility diagnostics remain available for reporting and
    exception payloads, but the validity decision itself is evaluated across
    the staged validation logs.

    Args:
        cfg: Frozen or mutable config to validate.
        resolved: Resolved TOML-side state for the current run.
        override: Optional API/CLI override for `strict`.

    Returns:
        `True` if the config is valid under the effective strictness, else
        `False`.
    """
    effective_strict: bool = bool(override if override is not None else resolved.strict)
    return cfg.is_valid(strict=effective_strict)


def ensure_config_valid(
    cfg: FrozenConfig | MutableConfig,
    *,
    resolved: ResolvedTopmarkTomlSources,
    override: bool | None = None,
) -> None:
    """Raise `ConfigValidationError` if the config is not valid.

    Config validity follows the staged config-loading validation semantics:
    TOML-source diagnostics, merged-config diagnostics, and
    runtime-applicability diagnostics are evaluated together. In non-strict
    mode, validation fails only when at least one stage contains an error
    diagnostic. In strict mode, validation fails when any stage contains either
    a warning or an error diagnostic.

    The strictness used here is the effective resolved value of
    `strict`, derived from:
    - an explicit API/CLI override when provided,
    - otherwise the TOML-resolved source-local preference in `resolved`,
    - otherwise non-strict behavior.

    The flattened compatibility diagnostics remain available for reporting and
    exception payloads, but the validity decision itself is evaluated across
    the staged validation logs.

    Args:
        cfg: Frozen or mutable config to validate.
        resolved: Resolved TOML-side state for the current run.
        override: Optional API/CLI override for `strict`.

    Raises:
        ConfigValidationError: If the config is invalid under the effective
            strictness.
    """  # noqa: DOC502 - documents propagated exceptions from `cfg.ensure_valid()``
    effective_strict: bool = bool(override if override is not None else resolved.strict)
    cfg.ensure_valid(strict=effective_strict)


# ---- Resolved config construction helpers ----


def _build_resolved_config_for_run(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, object] | FrozenConfig | None,
    resolved_draft: MutableConfig | None,
    include_file_types: Sequence[str] | None,
    exclude_file_types: Sequence[str] | None,
) -> FrozenConfig:
    """Build the layered, file-backed config for an API run.

    This function resolves only config that legitimately participates in layered
    discovery and per-path effective config construction. It must not apply
    execution intent such as apply mode, stdin mode, output routing, file write
    strategy, or run timestamps.

    Resolution mode:

    - when `base_config is None`, consume already-resolved TOML-side state for layered config
      construction
    - when `base_config` is provided, treat it as an explicit seed and skip discovery
    - in both modes, apply final file/file-type intent via `apply_config_overrides()` before
      freezing

    Args:
        paths: Files and/or directories to process.
        base_config: Optional explicit config seed. When omitted, layered config
            discovery is used. When provided, discovery is skipped.
        resolved_draft: Pre-merged mutable config draft built from already
            resolved TOML-side state, if layered discovery is active.
        include_file_types: Optional file-type allowlist override used during
            file-list resolution.
        exclude_file_types: Optional file-type denylist override used during
            file-list resolution.

    Returns:
        The resolved runtime configuration that serves as the base for file discovery
        and later policy overlay application.
    """
    logger.debug("Normalizing input paths: %s", paths)

    # Normalize input paths to strings for stable downstream override handling.
    paths_str: list[str] = [str(Path(p)) for p in paths]

    if resolved_draft is not None:
        draft: MutableConfig = resolved_draft
    else:
        # Explicit seed mode: start from defaults, merge the supplied mapping /
        # immutable FrozenConfig on top, and skip all config discovery.
        seeded: MutableConfig = ensure_mutable_config(base_config)
        draft = mutable_config_from_defaults().merge_with(seeded)

    # Apply file/file-type intent needed for file-list resolution. This remains
    # part of the resolved config because it directly affects which files are
    # selected for pipeline execution.
    overrides = ConfigOverrides(
        config_origin=SyntheticConfigSource(label="<API overrides>"),
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


# ---- TOML-source resolution helpers ----


def _prepare_toml_and_mutable_config_for_api_run(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, object] | FrozenConfig | None,
) -> PreparedTomlConfig:
    """Resolve TOML sources once and prebuild the merged config draft.

    Explicit `base_config` seeds intentionally bypass layered TOML discovery,
    so this helper returns a result with both fields set to `None` in that
    mode.

    In normal discovery mode, TOML schema validation has already happened before
    the merged draft is returned here.

    Args:
        paths: Input paths for the run. They are passed through as discovery
            anchors, mirroring normal config discovery behavior.
        base_config: Optional explicit config seed supplied by the caller.

    Returns:
        Prepared TOML-side state and merged mutable config draft, or empty
        fields when layered discovery is intentionally bypassed.
    """
    if base_config is not None:
        return PreparedTomlConfig(resolved=None, draft=None)

    path_list: list[Path] = [Path(p) for p in paths] or [Path.cwd()]
    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=tuple(path_list),
        extra_config_files=(),
        strict=None,
        no_config=False,
    )
    return PreparedTomlConfig(
        resolved=resolved_config.resolved,
        draft=resolved_config.draft,
    )


# ---- Per-path config helpers ----


def _build_path_configs(
    *,
    layers: Sequence[ConfigLayer] | None,
    file_list: Sequence[Path],
    effective_cfg: FrozenConfig,
) -> dict[Path, FrozenConfig]:
    """Build per-path effective layered configs for a run.

    When provenance layers are available, each file path receives a config built from the subset of
    layers whose scope applies to that path. Config-like runtime policy overlays are copied onto the
    per-path effective config.

    When no layers are available, this helper falls back to using the single run-level config for
    every path.

    Args:
        layers: Optional discovered config provenance layers for the run.
        file_list: Files that will be processed.
        effective_cfg: Final runtime runtime config carrying any runtime policy overlays.

    Returns:
        A mapping from file path to the effective runtime config that should be used when
        bootstrapping that file's processing context.
    """
    if layers is None:
        return dict.fromkeys(file_list, effective_cfg)

    path_configs: dict[Path, FrozenConfig] = {}
    for path in file_list:
        per_path_cfg: FrozenConfig = build_effective_config_for_path(layers, path).freeze()
        path_configs[path] = replace(
            per_path_cfg,
            policy=effective_cfg.policy,
            policy_by_type=effective_cfg.policy_by_type,
        )

    return path_configs


# ---- Runtime overlay helpers ----


def _apply_runtime_policy_overlays(
    cfg: FrozenConfig,
    *,
    policy: PublicPolicy | None,
    policy_by_type: Mapping[str, PublicPolicy] | None,
) -> FrozenConfig:
    """Apply invocation-scoped policy overlays to a resolved layered config.

    These overlays affect processing behavior, but they are still config-like: they modify policy
    resolution rather than execution transport or output intent.

    Args:
        cfg: The resolved config to overlay.
        policy: Optional global public policy overlay.
        policy_by_type: Optional per-type public policy overlays.

    Returns:
        The final runtime runtime config for the run after applying any runtime policy overlays.
    """
    if policy is None and policy_by_type is None:
        return cfg

    # Start from the resolved immutable config and apply config-like policy intent on top.
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
            config_origin=SyntheticConfigSource(label="<API policy overrides>"),
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
        kind: The pipeline family to use (`"probe"`, `"check"` or `"strip"`).
        apply: If `True`, choose a mutating variant for commands that support mutation.
            Ignored for `"probe"`, which is always read-only.
        diff: If `True`, choose a patch-producing variant for commands that support diffs.
            Ignored for `"probe"`, which does not produce content diffs.

    Returns:
        The ordered immutable sequence of steps to execute.

    Raises:
        RuntimeError: if an invalid pipeline kind was specified.
    """
    pipeline: Pipeline
    match kind:
        case "check":
            if apply:  # Mutate files
                pipeline = Pipeline.CHECK_APPLY_PATCH if diff else Pipeline.CHECK_APPLY
            else:  # Dry-run
                pipeline = Pipeline.CHECK_PATCH if diff else Pipeline.CHECK

        case "strip":
            if apply:  # Mutate files
                pipeline = Pipeline.STRIP_APPLY_PATCH if diff else Pipeline.STRIP_APPLY
            else:  # Dry-run
                pipeline = Pipeline.STRIP_PATCH if diff else Pipeline.STRIP

        case "probe":
            # Probe has a single diagnostic pipeline. It never writes files and
            # does not have patch/apply variants.
            pipeline = Pipeline.PROBE

        case _:
            # Defensive guard:
            raise RuntimeError(f"Invalid pipeline kind specified: {kind}")

    logger.info("Selected pipeline: %r", pipeline)
    return pipeline.steps


def _resolve_public_header_mutation_mode(
    value: str,
) -> HeaderMutationMode:
    """Return the internal enum for a public header-mutation token."""
    try:
        return HeaderMutationMode(value)
    except ValueError as exc:
        raise InvalidPolicyError(
            message=f"Invalid value for header_mutation_mode: {value!r}",
            policy_key="header_mutation_mode",
        ) from exc


def _resolve_public_empty_insert_mode(
    value: str,
) -> EmptyInsertMode:
    """Return the internal enum for a public empty-insert token."""
    try:
        return EmptyInsertMode(value)
    except ValueError as exc:
        raise InvalidPolicyError(
            message=f"Invalid value for empty_insert_mode: {value!r}",
            policy_key="empty_insert_mode",
        ) from exc


def _build_public_policy_overrides(
    policy: PublicPolicy,
) -> PolicyOverrides:
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


def _prepare_api_pipeline_run(
    *,
    paths: Iterable[Path | str],
    run_options: RunOptions,
    base_config: Mapping[str, object] | FrozenConfig | None,
    include_file_types: Sequence[str] | None,
    exclude_file_types: Sequence[str] | None,
    policy: PublicPolicy | None,
    policy_by_type: Mapping[str, PublicPolicy] | None,
) -> PreparedApiRun:
    """Resolve config, runtime options, and candidate files for an API run.

    This helper owns the setup that must remain identical across `check()`,
    `strip()`, and `probe()`: TOML/config discovery, runtime policy overlays,
    persisted writer-option consumption, and selected-file resolution.

    Args:
        paths: Files and/or directories supplied to the public API command.
        run_options: Execution-only runtime options supplied by the caller.
        base_config: `None` for layered discovery, otherwise an explicit config
            seed supplied directly by the caller.
        include_file_types: Optional allowlist of file type identifiers for
            file-list resolution.
        exclude_file_types: Optional denylist of file type identifiers for
            file-list resolution.
        policy: Optional global public policy overlay.
        policy_by_type: Optional per-type public policy overlays.

    Returns:
        Prepared state shared by normal and probe-specific pipeline execution.
    """
    path_inputs: list[Path | str] = list(paths)

    prepared_toml: PreparedTomlConfig = _prepare_toml_and_mutable_config_for_api_run(
        path_inputs,
        base_config=base_config,
    )

    discovered_layers: list[ConfigLayer] | None = (
        build_config_layers_from_resolved_toml_sources(prepared_toml.resolved.sources)
        if prepared_toml.resolved is not None
        else None
    )
    resolved_writer_options: WriterOptions | None = (
        prepared_toml.resolved.writer_options if prepared_toml.resolved is not None else None
    )

    # (1) Build the resolved config used for discovery from TOML-side resolved
    # state when available. Runtime policy overlays, writer options, and
    # file-list resolution are handled below so all API commands share the same
    # ordering.
    cfg: FrozenConfig = _build_resolved_config_for_run(
        path_inputs,
        base_config=base_config,
        resolved_draft=prepared_toml.draft,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
    )
    logger.debug("(1) Resolved config before runtime overlays: %s", cfg)

    # (2) Apply runtime policy overlays after layered config resolution.
    effective_cfg: FrozenConfig = _apply_runtime_policy_overlays(
        cfg,
        policy=policy,
        policy_by_type=policy_by_type,
    )
    logger.debug("(2) Effective config after runtime policy overlays: %s", effective_cfg)

    # (3) Consume execution-only run options supplied by the caller and overlay
    # resolved persisted writer preferences when they do not conflict with
    # explicit runtime intent.
    effective_run_options: RunOptions = apply_resolved_writer_options(
        run_options,
        resolved_writer_options,
    )
    logger.debug("(3) Run options for invocation: %s", effective_run_options)

    # (4) Resolve the selected file list after policy overlays.
    file_resolution: FileListResolution = resolve_file_list_with_diagnostics(effective_cfg)
    file_list: list[Path] = list(file_resolution.selected)
    logger.debug("(4) Files found: %s", len(file_list))

    return PreparedApiRun(
        effective_cfg=effective_cfg,
        run_options=effective_run_options,
        file_resolution=file_resolution,
        file_list=file_list,
        discovered_layers=discovered_layers,
    )


def _execute_pipeline_for_file_list(
    *,
    prepared: PreparedApiRun,
    pipeline: Sequence[Step[ProcessingContext]],
) -> PipelineExecution:
    """Execute pipeline steps for the selected files in a prepared API run.

    Args:
        prepared: Shared resolved state for the API run.
        pipeline: Pipeline steps to execute.

    Returns:
        Pipeline execution result containing processing contexts and any fatal
        exit code reported by the pipeline engine. If no files were selected,
        returns an empty context list with no exit code.
    """
    if not prepared.file_list:
        return PipelineExecution(
            contexts=[],
            exit_code=None,
        )

    # (1) Build per-path effective configs for layered discovery.
    path_configs: dict[Path, FrozenConfig] = _build_path_configs(
        layers=prepared.discovered_layers,
        file_list=prepared.file_list,
        effective_cfg=prepared.effective_cfg,
    )

    # (2) Execute the selected pipeline for each resolved file.
    pipeline_run: PipelineExecution = run_steps_for_files(
        run_options=prepared.run_options,
        config=prepared.effective_cfg,
        path_configs=path_configs,
        pipeline=pipeline,
        file_list=prepared.file_list,
    )
    return pipeline_run


def run_pipeline(
    *,
    pipeline: Sequence[Step[ProcessingContext]],
    paths: Iterable[Path | str],
    run_options: RunOptions,
    base_config: Mapping[str, object] | FrozenConfig | None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    # public-policy overlays (None = no override)
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
) -> ApiPipelineRun:
    """Resolve shared API runtime state and run a content-processing pipeline.

    Args:
        pipeline: The pipeline steps to apply.
        paths: Files and/or directories to process.
        run_options: Invocation-wide execution-only runtime options for the run.
        base_config: `None` for normal layered discovery; otherwise an explicit
            config seed supplied directly by the caller.
        include_file_types: Optional allowlist of file type identifiers used for
            file-list resolution.
        exclude_file_types: Optional denylist of file type identifiers used for
            file-list resolution.
        policy: Optional global public policy overlay applied after config
            resolution and before file discovery.
        policy_by_type: Optional per-type public policy overlays applied after
            config resolution and before file discovery.

    Returns:
        A tuple containing the resolved runtime config, selected file list, pipeline
        contexts, and any fatal exit code.
    """
    logger.info("Building config and file list for paths: %s", paths)

    prepared: PreparedApiRun = _prepare_api_pipeline_run(
        paths=paths,
        run_options=run_options,
        base_config=base_config,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        policy=policy,
        policy_by_type=policy_by_type,
    )

    execution: PipelineExecution = _execute_pipeline_for_file_list(
        prepared=prepared,
        pipeline=pipeline,
    )
    results: list[ProcessingContext] = execution.contexts
    encountered_exit_code: ExitCode | None = execution.exit_code

    logger.info("Processing %d file(s) with TopMark %s", len(prepared.file_list), TOPMARK_VERSION)

    return ApiPipelineRun(
        effective_cfg=prepared.effective_cfg,
        file_list=prepared.file_list,
        contexts=results,
        exit_code=encountered_exit_code,
    )


def run_probe_pipeline(
    *,
    pipeline: Sequence[Step[ProcessingContext]],
    paths: Iterable[Path | str],
    run_options: RunOptions,
    base_config: Mapping[str, object] | FrozenConfig | None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
    # public-policy overlays (None = no override)
    policy: PublicPolicy | None = None,
    policy_by_type: Mapping[str, PublicPolicy] | None = None,
) -> ApiPipelineRun:
    """Resolve shared API runtime state and run the probe pipeline.

    Probe has one behavior beyond `run_pipeline()`: it preserves explicit inputs
    that disappear before normal pipeline execution. Those inputs receive
    synthetic contexts so `topmark.api.probe()` can explain missing literals and
    discovery-filtered paths without exposing resolver internals.

    Args:
        pipeline: The probe pipeline steps to execute.
        paths: Files and/or directories to probe.
        run_options: Invocation-wide execution-only runtime options for the run.
        base_config: `None` for normal layered discovery; otherwise an explicit
            config seed supplied directly by the caller.
        include_file_types: Optional allowlist of file type identifiers used for
            file-list resolution.
        exclude_file_types: Optional denylist of file type identifiers used for
            file-list resolution.
        policy: Optional global public policy overlay applied after config
            resolution and before file discovery.
        policy_by_type: Optional per-type public policy overlays applied after
            config resolution and before file discovery.

    Returns:
        A tuple containing the resolved runtime config, selected file list, real plus
        synthetic probe contexts, and any fatal exit code.
    """
    logger.info("Building probe config and file list for paths: %s", paths)

    prepared: PreparedApiRun = _prepare_api_pipeline_run(
        paths=paths,
        run_options=run_options,
        base_config=base_config,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        policy=policy,
        policy_by_type=policy_by_type,
    )

    # Explain only explicit inputs that disappear during discovery/filtering.
    # Recursive traversal may exclude many files; reporting all excluded
    # recursive candidates would be too noisy and would diverge from the CLI
    # probe contract.
    filtered_selection_results: tuple[FileSelectionProbeResult, ...] = (
        ()
        if prepared.run_options.stdin_mode
        else probe_explicit_file_selection(
            prepared.effective_cfg,
            selected_files=prepared.file_list,
            missing_literals=prepared.file_resolution.missing_literals,
        )
    )

    execution: PipelineExecution = _execute_pipeline_for_file_list(
        prepared=prepared,
        pipeline=pipeline,
    )
    results: list[ProcessingContext] = execution.contexts
    encountered_exit_code: ExitCode | None = execution.exit_code

    # Missing explicit literals are hard resolver-level failures. Add them
    # before fatal precedence is derived so they can influence `had_errors`.
    results.extend(
        build_missing_file_contexts(
            paths=prepared.file_resolution.missing_literals,
            config=prepared.effective_cfg,
            run_options=prepared.run_options,
        )
    )

    pipeline_error_code: ExitCode | None = exit_code_from_pipeline_results(results)
    encountered_exit_code = encountered_exit_code or pipeline_error_code

    # Discovery-filtered explicit inputs are semantic probe outcomes rather than
    # hard execution errors, so append them after fatal precedence is computed.
    results.extend(
        build_filtered_probe_contexts(
            selection_results=filtered_selection_results,
            config=prepared.effective_cfg,
            run_options=prepared.run_options,
        )
    )

    logger.info("Probing %d result(s) with TopMark %s", len(results), TOPMARK_VERSION)

    return ApiPipelineRun(
        effective_cfg=prepared.effective_cfg,
        file_list=prepared.file_list,
        contexts=results,
        exit_code=encountered_exit_code,
    )
