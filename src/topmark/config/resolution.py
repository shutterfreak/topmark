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
from typing import Final

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_toml_dict
from topmark.config.layers import ConfigLayer
from topmark.config.layers import ConfigLayerKind
from topmark.core.logging import get_logger
from topmark.toml.resolution import ResolvedTopmarkTomlSource
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.resolution import resolve_topmark_toml_sources

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable


DEFAULT_LAYER_PRECEDENCE: Final[int] = 0
"""Stable precedence assigned to the built-in defaults layer."""

FIRST_SOURCE_LAYER_PRECEDENCE: Final[int] = 1
"""Stable precedence assigned to the first non-default resolved TOML source layer."""

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
        precedence=DEFAULT_LAYER_PRECEDENCE,
        scope_root=None,
        config=mutable_config_from_defaults(),
    )


def _make_layer_from_toml_table(
    path: Path,
    *,
    data: TomlTable,
    kind: ConfigLayerKind,
    precedence: int,
) -> ConfigLayer:
    """Build one config provenance layer from a layered TOML table.

    Args:
        path: Source TOML file path used for provenance and path-relative
            normalization.
        data: Layered TOML table extracted from one split-parsed TopMark TOML
            source.
        kind: Provenance kind for the resulting config layer.
        precedence: Stable merge precedence for the resulting config layer.

    Returns:
        Normalized config provenance layer built from the layered TOML table.
    """
    resolved_path: Path = path.resolve()
    config: MutableConfig = mutable_config_from_toml_dict(
        data,
        config_file=resolved_path,
    )

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


def _kind_from_resolved_toml_source(source: ResolvedTopmarkTomlSource) -> ConfigLayerKind:
    """Map TOML-source discovery kind to `ConfigLayerKind`."""
    if source.kind == "user":
        return ConfigLayerKind.USER
    if source.kind == "explicit":
        return ConfigLayerKind.EXPLICIT
    return ConfigLayerKind.DISCOVERED


# ---- Public layer construction / merge helpers ----


def build_config_layers_from_resolved_toml_sources(
    sources: list[ResolvedTopmarkTomlSource],
) -> list[ConfigLayer]:
    """Build config provenance layers from resolved TOML source records.

    Args:
        sources: Resolved TOML source records in stable precedence order.

    Returns:
        Config provenance layers including the built-in defaults layer at
        precedence 0, followed by one layer per resolved TOML source.
    """
    layers: list[ConfigLayer] = []

    default_layer: ConfigLayer = _default_config_layer()
    layers.append(default_layer)
    logger.debug(
        "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
        default_layer.kind,
        default_layer.precedence,
        default_layer.origin,
        default_layer.scope_root,
    )

    precedence: int = FIRST_SOURCE_LAYER_PRECEDENCE
    for source in sources:
        layer: ConfigLayer = _make_layer_from_toml_table(
            source.path,
            data=source.parsed.layered_config,
            kind=_kind_from_resolved_toml_source(source),
            precedence=precedence,
        )
        layers.append(layer)
        logger.debug(
            "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
            layer.kind,
            layer.precedence,
            layer.origin,
            layer.scope_root,
        )
        precedence += 1

    return layers


# ---- Layer merge / applicability helpers ----


def merge_layers_globally(layers: Iterable[ConfigLayer]) -> MutableConfig:
    """Merge config provenance layers into one mutable compatibility draft.

    Args:
        layers: Config provenance layers in stable precedence order.

    Returns:
        A mutable compatibility draft produced by merging the supplied layers in
        order.
    """
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


# ---- Compatibility discovery / facade helpers ----


def build_resolved_config_from_toml_sources(
    resolved: ResolvedTopmarkTomlSources,
) -> MutableConfig:
    """Merge resolved TOML sources into one mutable compatibility draft.

    This helper consumes already-resolved TOML-side state and performs only the
    config-layer construction and merge step. It does not re-run TOML
    discovery.

    TOML-side strictness is applied after the layer merge so the compatibility
    draft reflects the final resolved config-loading strictness for the run.

    Args:
        resolved: Resolved TOML-side state for the current run.

    Returns:
        Merged mutable configuration draft built from the defaults layer plus
        all resolved layered TOML sources.
    """
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)
    draft: MutableConfig = merge_layers_globally(layers)

    if resolved.strict_config_checking is not None:
        draft.strict_config_checking = resolved.strict_config_checking

    return draft


def resolve_toml_sources_and_build_config_draft(
    *,
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
    no_config: bool = False,
) -> tuple[ResolvedTopmarkTomlSources, MutableConfig]:
    """Resolve TOML sources once and build the merged config draft from them.

    This helper is the preferred bridge between TOML-side source resolution and
    config-layer merge for callers that need both the resolved TOML-side state
    and the merged mutable compatibility draft.

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to merge after discovered
            layers. Later files override earlier ones.
        strict_config_checking: Optional explicit override for resolved
            config-loading strictness on the resulting draft.
        no_config: If `True`, skip all discovered config layers (user +
            project) and only use built-in defaults plus any explicit extra
            config files.

    Returns:
        A tuple containing the resolved TOML-side state and the merged mutable
        configuration draft built from it.
    """
    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=input_paths,
        extra_config_files=extra_config_files,
        strict_config_checking=strict_config_checking,
        no_config=no_config,
    )
    return resolved, build_resolved_config_from_toml_sources(resolved)


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

    This helper is a compatibility facade over TOML-side source resolution plus
    config-layer construction. It remains useful for callers that still want
    resolved `ConfigLayer` objects directly.

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
    # Avoid premature modeling of config-loading strictness as a provenance
    # layer. Strictness is resolved on the TOML side and may later be applied
    # to the merged compatibility draft.
    del strict_config_checking

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=input_paths,
        extra_config_files=extra_config_files,
        strict_config_checking=None,
        no_config=no_config,
    )
    return build_config_layers_from_resolved_toml_sources(resolved.sources)


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

    This helper is a compatibility facade over TOML-side source resolution plus
    config-layer merge.

    It does **not** apply CLI/API override intent such as write mode,
    stdin mode, include/exclude filters, or header-formatting overrides; those
    belong in the dedicated override layer.

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to merge after discovered
            layers. Later files override earlier ones.
        strict_config_checking: Optional explicit override for resolved
            config-loading strictness on the resulting draft.
        no_config: If True, skip all discovered config layers (user + project)
            and only use built-in defaults plus any explicit extra config files.

    Returns:
        A mutable configuration draft ready for later override application and
        eventual freezing.
    """
    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=input_paths,
        extra_config_files=extra_config_files,
        strict_config_checking=strict_config_checking,
        no_config=no_config,
    )
    return draft
