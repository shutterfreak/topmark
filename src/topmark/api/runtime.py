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
- configuration discovery/normalization
- file list resolution
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
from typing import Literal

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_mapping
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
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.pipelines import Pipeline
from topmark.resolution.files import resolve_file_list

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence

    from topmark.api.protocols import PublicPolicy
    from topmark.core.exit_codes import ExitCode
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step

logger: TopmarkLogger = get_logger(__name__)


def ensure_mutable_config(
    config: Mapping[str, object] | MutableConfig | Config | None,
) -> MutableConfig:
    """Return a **MutableConfig** from a mapping or a frozen `Config`.

    This adapter normalizes public inputs (``Mapping[str, object]`` or frozen ``Config``)
    to a **mutable** builder for merging and final ``freeze()`` before pipeline execution.

    Args:
        config: Optional (TOML) mapping, draft, or frozen config instance.

    Returns:
        A mutable draft configuration.

    Note:
        Public API functions accept **mappings** or **frozen** configs. Passing a
        `MutableConfig` is not part of the public contract; this helper accepts it
        internally for convenience during discovery tests.
    """
    if config is None:
        logger.debug("No config provided - returning MutableConfig.from_defaults()")
        return mutable_config_from_defaults()
    if isinstance(config, MutableConfig):
        logger.debug("Supplied config is MutableConfig - returning as is")
        return config
    if isinstance(config, Config):
        # Thaw a frozen Config into a mutable draft
        logger.debug("Supplied config is Config - returning MutableConfig")
        return MutableConfig(
            timestamp=config.timestamp,
            apply_changes=config.apply_changes,
            policy=config.policy.thaw(),
            policy_by_type={k: v.thaw() for k, v in config.policy_by_type.items()},
            config_files=list(config.config_files),
            header_fields=list(config.header_fields),
            field_values=dict(config.field_values),
            align_fields=config.align_fields,
            relative_to_raw=config.relative_to_raw,
            relative_to=config.relative_to,
            stdin_mode=config.stdin_mode,
            files=list(config.files),
            include_patterns=list(config.include_patterns),
            include_from=list(config.include_from),
            exclude_patterns=list(config.exclude_patterns),
            exclude_from=list(config.exclude_from),
            files_from=list(config.files_from),
            include_file_types=set(config.include_file_types),
            exclude_file_types=set(config.exclude_file_types),
        )
    # Accept plain dict-like, normalize to internal MutableConfig via TOML-like dict
    logger.debug("Supplied config is TOML Mapping - returning mutable_config_from_mapping(config)")
    return mutable_config_from_mapping(config)


def build_config_and_files(
    paths: Iterable[Path | str],
    *,
    base_config: Mapping[str, object] | Config | None,
    include_file_types: Sequence[str] | None,
    exclude_file_types: Sequence[str] | None,
) -> tuple[Config, list[Path]]:
    """Build the frozen config and resolved file list for an API run.

    This helper mirrors the CLI/config-layer split without depending on CLI
    modules:

    - when `base_config is None`, use layered discovery via
      `load_resolved_config()`
    - when `base_config` is provided, honor it as an explicit seed and skip
      discovery
    - in both modes, apply final high-precedence file/file-type overrides via
      `apply_config_overrides()` before freezing and resolving files

    Args:
        paths: Files and/or directories to process.
        base_config: Optional explicit config seed. When omitted, layered config
            discovery is used. When provided, discovery is skipped.
        include_file_types: Optional file-type allowlist override.
        exclude_file_types: Optional file-type denylist override.

    Returns:
        A 2-tuple `(cfg, files)` where `cfg` is the frozen configuration used to
        resolve files and `files` is the resolved/filtered file list.
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

    # Apply final file/file-type intent consistently with the config override
    # layer, then freeze for file resolution.
    overrides = ConfigOverrides(
        files=paths_str,
        include_file_types=list(include_file_types) if include_file_types is not None else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types is not None else None,
    )
    draft = apply_config_overrides(
        draft,
        overrides=overrides,
    )

    cfg: Config = draft.freeze()
    file_list: list[Path] = resolve_file_list(cfg)
    logger.debug("Files found: %s", len(file_list))
    return cfg, file_list


def select_pipeline(
    kind: Literal["check", "strip"],
    *,
    apply: bool,
    diff: bool,
) -> Sequence[Step[ProcessingContext]]:
    """Return the concrete pipeline steps for the requested kind and intent.

    Args:
        kind: The pipeline family to use.
        apply: If `True`, choose an *_APPLY* variant.
        diff: If `True`, choose a *PATCH* variant (includes unified diffs).

    Returns:
        Sequence[Step[ProcessingContext]]: The ordered list of steps to execute.
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
    base_config: Mapping[str, object] | Config | None,
    include_file_types: Sequence[str] | None = None,
    exclude_file_types: Sequence[str] | None = None,
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
        pipeline: The pipeline (steps) to apply.
        paths: Files and/or directories to process.
        base_config: `None` for discovery; a mapping or `Config` to seed the run directly.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        apply_changes: When `True`, run in apply mode; otherwise dry run.
        prune: If `True`, trim heavy views after the run (keeps summaries).
        policy: Optional global policy overlays (public shape) applied **after** discovery
            and before freezing.
        policy_by_type: Optional per-type policy overlays (public shape) applied **after**
            discovery and before freezing.

    Returns:
        A tuple:
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
    cfg, file_list = build_config_and_files(
        paths,
        base_config=base_config,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
    )
    logger.debug("cfg for run (1 - after build_config_and_files): %s", cfg)

    # 2) Apply public policy overlays AFTER discovery, then materialize apply intent.
    has_policy_overlay: bool = policy is not None or policy_by_type is not None
    if has_policy_overlay:
        draft: MutableConfig = cfg.thaw()

        policy_overrides: PolicyOverrides = (
            _build_public_policy_overrides(policy) if policy is not None else PolicyOverrides()
        )
        policy_by_type_overrides: dict[str, PolicyOverrides] = (
            _build_public_policy_by_type_overrides(policy_by_type)
            if policy_by_type is not None
            else {}
        )

        draft = apply_config_overrides(
            draft,
            ConfigOverrides(
                policy=policy_overrides,
                policy_by_type=policy_by_type_overrides,
            ),
        )

        cfg = draft.freeze()  # (No mutation of cfg - Config is frozen)
    logger.debug("cfg for run (2 - after applying policy overlays): %s", cfg)

    if not file_list:
        return cfg, file_list, [], None

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
