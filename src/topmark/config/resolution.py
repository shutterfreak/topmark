# topmark:header:start
#
#   project      : TopMark
#   file         : resolution.py
#   file_relpath : src/topmark/config/resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Layered config resolution for TopMark.

This module converts layered TopMark TOML config fragments into
[`ConfigLayer`][topmark.config.layers.ConfigLayer] objects, merges those layers
in stable precedence order, and builds effective per-path `MutableConfig`
drafts.

Responsibilities:
    - represent resolved layered config sources as `ConfigLayer`
    - load layered TOML-backed config fragments into `MutableConfig`
    - preserve TopMark's layered precedence rules
    - merge discovered config layers into compatibility drafts
    - select applicable layers for a target path and build an effective config

Typical layered precedence (lowest -> highest):
    1. built-in defaults
    2. discovered user config layer
    3. discovered project/local config layers (root-most -> nearest)
    4. explicitly provided extra config layers

This module is intentionally separate from
[`topmark.toml.resolution`][topmark.toml.resolution]:

- [`topmark.toml.resolution`][topmark.toml.resolution] discovers TopMark
  TOML settings files
- this module turns layered TOML config fragments into config provenance layers
  and merges them into effective mutable config drafts

The result of compatibility flattening is a `MutableConfig` draft that can still
be adjusted by callers before being frozen into an immutable `Config`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_toml_file
from topmark.config.layers import ConfigLayer
from topmark.config.layers import ConfigLayerKind
from topmark.core.logging import get_logger
from topmark.toml.resolution import discover_local_config_files
from topmark.toml.resolution import discover_user_config_file

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


# ---- Internal layer construction helpers ----


def _make_config_layer(
    *,
    origin: Path | str,
    kind: ConfigLayerKind,
    precedence: int,
    config: MutableConfig,
    scope_root: Path | None = None,
) -> ConfigLayer:
    """Return a normalized config provenance layer."""
    normalized_origin: Path | str = origin.resolve() if isinstance(origin, Path) else origin
    normalized_scope_root: Path | None = scope_root

    if normalized_scope_root is None and isinstance(normalized_origin, Path):
        normalized_scope_root = normalized_origin.parent.resolve()
    elif normalized_scope_root is not None:
        normalized_scope_root = normalized_scope_root.resolve()

    return ConfigLayer(
        origin=normalized_origin,
        scope_root=normalized_scope_root,
        precedence=precedence,
        kind=kind,
        config=config,
    )


def _default_config_layer() -> ConfigLayer:
    """Return the built-in defaults as the first config provenance layer."""
    return _make_config_layer(
        origin="<defaults>",
        kind=ConfigLayerKind.DEFAULT,
        precedence=0,
        scope_root=None,
        config=mutable_config_from_defaults(),
    )


def _load_layer_from_file(
    path: Path,
    *,
    kind: ConfigLayerKind,
    precedence: int,
) -> ConfigLayer | None:
    """Load a config provenance layer from a TOML-backed config file.

    Note:
        This transitional helper still loads directly from a TOML file into a
        `MutableConfig`. It will likely be replaced or reshaped so that it
        consumes split-parsed layered TOML fragments instead.
    """
    resolved_path: Path = path.resolve()
    config: MutableConfig | None = mutable_config_from_toml_file(resolved_path)
    if config is None:
        logger.debug("Skipping unreadable or invalid config layer file: %s", resolved_path)
        return None

    return _make_config_layer(
        origin=resolved_path,
        kind=kind,
        precedence=precedence,
        scope_root=resolved_path.parent,
        config=config,
    )


def _is_within_scope(path: Path, scope_root: Path) -> bool:
    """Return whether ``path`` is within the given layer scope root."""
    resolved_path: Path = path.resolve()
    resolved_scope_root: Path = scope_root.resolve()
    result: bool
    try:
        resolved_path.relative_to(resolved_scope_root)
        result = True
    except ValueError:
        result = False

    return result


# ---- Layer discovery ----


def discover_config_layers(
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
    no_config: bool = False,
) -> list[ConfigLayer]:
    """Discover config provenance layers in stable precedence order.

    Layer order (lowest -> highest precedence):
        1. built-in defaults
        2. discovered user config
        3. discovered project config files (root-most -> nearest)
        4. explicit extra config files (in the order provided)

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to append after discovered
            layers. Later files have higher precedence than earlier ones.
        strict_config_checking: Reserved compatibility argument. Layer
            discovery does not currently materialize this config-loading
            strictness override as a provenance layer.
        no_config: If True, skip all discovered config layers (user + project)
            and only return built-in defaults plus any explicit extra config
            files.

    Returns:
        Config provenance layers ordered from lowest to highest precedence.
    """
    # Avoid premature modeling of runtime-only overrides as layers:
    del strict_config_checking

    layers: list[ConfigLayer] = []
    precedence: int = 0

    default_layer: ConfigLayer = _default_config_layer()
    layers.append(default_layer)
    logger.debug(
        "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
        default_layer.kind,
        default_layer.precedence,
        default_layer.origin,
        default_layer.scope_root,
    )

    input_path_list: list[Path] = list(input_paths) if input_paths is not None else []
    anchor: Path = input_path_list[0] if input_path_list else Path.cwd()
    if anchor.is_file():
        anchor = anchor.parent
    anchor = anchor.resolve()
    logger.debug("Config layer discovery anchor: %s", anchor)

    precedence = 1

    if not no_config:
        user_cfg_path: Path | None = discover_user_config_file()
        if user_cfg_path is not None:
            user_layer: ConfigLayer | None = _load_layer_from_file(
                user_cfg_path,
                kind=ConfigLayerKind.USER,
                precedence=precedence,
            )
            if user_layer is not None:
                layers.append(user_layer)
                logger.debug(
                    "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
                    user_layer.kind,
                    user_layer.precedence,
                    user_layer.origin,
                    user_layer.scope_root,
                )
                precedence += 1

        discovered: list[Path] = discover_local_config_files(anchor)
        for cfg_path in discovered:
            discovered_layer: ConfigLayer | None = _load_layer_from_file(
                cfg_path,
                kind=ConfigLayerKind.DISCOVERED,
                precedence=precedence,
            )
            if discovered_layer is not None:
                layers.append(discovered_layer)
                logger.debug(
                    "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
                    discovered_layer.kind,
                    discovered_layer.precedence,
                    discovered_layer.origin,
                    discovered_layer.scope_root,
                )
                precedence += 1
    else:
        logger.debug("Skipping discovered config layers because no_config=True")

    for extra in extra_config_files or ():
        explicit_layer: ConfigLayer | None = _load_layer_from_file(
            Path(extra),
            kind=ConfigLayerKind.EXPLICIT,
            precedence=precedence,
        )
        if explicit_layer is not None:
            layers.append(explicit_layer)
            logger.debug(
                "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
                explicit_layer.kind,
                explicit_layer.precedence,
                explicit_layer.origin,
                explicit_layer.scope_root,
            )
            precedence += 1

    return layers


# ---- Layer merge and applicability ----


def merge_layers_globally(layers: Iterable[ConfigLayer]) -> MutableConfig:
    """Merge discovered config provenance layers into one compatibility draft."""
    layer_list: list[ConfigLayer] = list(layers)
    logger.debug("Merging %d config layer(s) into compatibility draft", len(layer_list))

    if not layer_list:
        return mutable_config_from_defaults()

    merged: MutableConfig = layer_list[0].config
    for layer in layer_list[1:]:
        merged = merged.merge_with(layer.config)

    return merged


def select_applicable_layers(
    layers: Iterable[ConfigLayer],
    path: Path,
) -> list[ConfigLayer]:
    """Return config layers whose scope applies to the given file path.

    Global layers (``scope_root is None``) always apply. File-backed layers apply
    only when the target path is within their declared scope root.

    Args:
        layers: Candidate config provenance layers.
        path: Target file path for which applicability should be evaluated.

    Returns:
        Applicable layers in their original precedence order.
    """
    resolved_path: Path = path.resolve()
    layer_list: list[ConfigLayer] = list(layers)
    applicable: list[ConfigLayer] = []

    for layer in layer_list:
        scope_root: Path | None = layer.scope_root
        if scope_root is None or _is_within_scope(resolved_path, scope_root):
            applicable.append(layer)

    logger.debug(
        "Selected %d/%d applicable config layer(s) for %s",
        len(applicable),
        len(layer_list),
        resolved_path,
    )
    return applicable


def build_effective_config_for_path(
    layers: Iterable[ConfigLayer],
    path: Path,
) -> MutableConfig:
    """Build the effective mutable config for a specific file path.

    This helper selects the config provenance layers whose scope applies to the
    target path, then merges them in stable precedence order using the existing
    `MutableConfig.merge_with` compatibility policy.

    Args:
        layers: Candidate config provenance layers.
        path: Target file path for which to build the effective config.

    Returns:
        The merged mutable config draft applicable to ``path``.
    """
    applicable: list[ConfigLayer] = select_applicable_layers(layers, path)
    draft: MutableConfig = merge_layers_globally(applicable)
    logger.debug(
        "Built effective config for %s from %d applicable layer(s)",
        path.resolve(),
        len(applicable),
    )
    return draft


# ---- Compatibility facade ----


def load_resolved_config(
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
    no_config: bool = False,
) -> MutableConfig:
    """Discover and merge configuration layers into a mutable draft.

    Merge order (lowest -> highest precedence):
        1. built-in defaults
        2. discovered user config
        3. discovered project config files (root-most -> nearest)
        4. explicit extra config files (in the order provided)

    This helper is responsible only for layered config layer discovery and
    merge. It does **not** apply CLI/API override intent such as write mode, stdin mode,
    include/exclude filters, or header-formatting overrides; those belong in the
    dedicated override layer.

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to merge after discovered
            layers. Later files override earlier ones.
        strict_config_checking: Optional runtime override for strict config
            checking on the resulting draft.
        no_config: If True, skip all discovered config layers (user + project)
            and only use built-in defaults plus any explicit extra config files.

    Returns:
        A mutable configuration draft ready for later override application and
        eventual freezing.
    """
    layers: list[ConfigLayer] = discover_config_layers(
        input_paths=input_paths,
        extra_config_files=extra_config_files,
        strict_config_checking=None,
        no_config=no_config,
    )
    draft: MutableConfig = merge_layers_globally(layers)

    if strict_config_checking is not None:
        draft.strict_config_checking = strict_config_checking

    return draft
