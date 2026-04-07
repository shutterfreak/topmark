# topmark:header:start
#
#   project      : TopMark
#   file         : layers.py
#   file_relpath : src/topmark/config/resolution/layers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Config provenance layer models and construction helpers.

This module defines the immutable provenance objects used during layered config
resolution and provides pure helpers to construct `ConfigLayer` records from
resolved TOML sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_toml_dict
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.resolution import ResolvedTopmarkTomlSource
    from topmark.toml.types import TomlTable

logger: TopmarkLogger = get_logger(__name__)

DEFAULT_LAYER_ORIGIN: Final[str] = "<defaults>"
"""Origin of built-in defaults layer."""

DEFAULT_LAYER_PRECEDENCE: Final[int] = 0
"""Stable precedence assigned to the built-in defaults layer."""

FIRST_SOURCE_LAYER_PRECEDENCE: Final[int] = 1
"""Stable precedence assigned to the first non-default resolved TOML source layer."""


class ConfigLayerKind(str, Enum):
    """Provenance kinds used during layered config resolution."""

    DEFAULT = "default"
    USER = "user"
    DISCOVERED = "discovered"
    EXPLICIT = "explicit"
    CLI = "cli"
    API = "api"


@dataclass(frozen=True, slots=True)
class ConfigLayer:
    """Immutable config provenance layer used during layered resolution.

    Attributes:
        origin: Provenance origin for the layer, usually a config file path or
            a synthetic marker such as `DEFAULT_LAYER_ORIGIN`.
        scope_root: Optional scope root for applicability checks. File-backed
            layers usually use the containing config directory; synthetic
            layers such as defaults, CLI, or API layers typically use `None`.
        precedence: Stable merge precedence; lower values are applied earlier.
        kind: Provenance kind for the layer.
        config: Parsed layered config fragment contributed by this layer only.
    """

    origin: Path | str
    scope_root: Path | None
    precedence: int
    kind: ConfigLayerKind
    config: MutableConfig


# ---- Internal layer construction helpers ----


def _make_config_layer(
    *,
    origin: Path | str,
    kind: ConfigLayerKind,
    precedence: int,
    config: MutableConfig,
    scope_root: Path | None = None,
) -> ConfigLayer:
    """Return a normalized config provenance layer.

    Path origins and scope roots are resolved eagerly so downstream precedence
    and applicability logic can compare normalized filesystem locations.
    """
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


def _make_default_config_layer() -> ConfigLayer:
    """Return the built-in defaults as the first config provenance layer."""
    return _make_config_layer(
        origin=DEFAULT_LAYER_ORIGIN,
        kind=ConfigLayerKind.DEFAULT,
        precedence=DEFAULT_LAYER_PRECEDENCE,
        scope_root=None,
        config=mutable_config_from_defaults(),
    )


def _make_layer_from_layered_toml_table(
    path: Path,
    *,
    data: TomlTable,
    kind: ConfigLayerKind,
    precedence: int,
) -> ConfigLayer:
    """Build one config provenance layer from a layered TOML fragment.

    Args:
        path: Source TOML file path used for provenance and path-relative
            normalization.
        data: Layered TOML fragment extracted from one split-parsed TopMark
            TOML source.
        kind: Provenance kind for the resulting config layer.
        precedence: Stable merge precedence for the resulting config layer.

    Returns:
        Normalized config provenance layer built from the layered TOML
        fragment.
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


def _kind_from_resolved_toml_source(source: ResolvedTopmarkTomlSource) -> ConfigLayerKind:
    """Map a resolved TOML source record to its config-layer provenance kind."""
    if source.kind == "user":
        return ConfigLayerKind.USER
    if source.kind == "explicit":
        return ConfigLayerKind.EXPLICIT
    return ConfigLayerKind.DISCOVERED


# ---- Public layer construction helpers ----


def build_config_layers_from_resolved_toml_sources(
    sources: list[ResolvedTopmarkTomlSource],
) -> list[ConfigLayer]:
    """Build config provenance layers from resolved TOML source records.

    Args:
        sources: Resolved TOML source records in stable precedence order.

    Returns:
        Config provenance layers in stable precedence order, including the
        built-in defaults layer first followed by one layer per resolved TOML
        source.
    """
    layers: list[ConfigLayer] = []

    default_layer: ConfigLayer = _make_default_config_layer()
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
        layer: ConfigLayer = _make_layer_from_layered_toml_table(
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
