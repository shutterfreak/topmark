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
from topmark.config.io.deserializers import mutable_config_from_layered_toml_table
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.logging import get_logger
from topmark.utils.path import canonical_processing_path

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


@dataclass(frozen=True, kw_only=True, slots=True)
class ConfigLayer:
    """Immutable config provenance layer used during layered resolution.

    Attributes:
        origin: Provenance origin for the layer, either a real config file path
            or a typed synthetic source marker such as built-in defaults.
        scope_root: Optional scope root for applicability checks. File-backed
            layers usually use the containing config directory; synthetic
            layers such as defaults, CLI, or API layers typically use `None`.
        precedence: Stable merge precedence; lower values are applied earlier.
        kind: Provenance kind for the layer.
        config: Parsed layered config fragment contributed by this layer only.
    """

    origin: Path | SyntheticConfigSource
    scope_root: Path | None
    precedence: int
    kind: ConfigLayerKind
    config: MutableConfig


# ---- Internal layer construction helpers ----


def _make_config_layer(
    *,
    origin: SyntheticConfigSource,
    kind: ConfigLayerKind,
    precedence: int,
    config: MutableConfig,
) -> ConfigLayer:
    """Return a config provenance layer for a synthetic origin.

    File-backed TOML sources are handled by `_make_layer_from_layered_toml_table()`
    so it can distinguish strict processing identity from best-effort provenance
    normalization. Synthetic origins are preserved as typed provenance markers and
    never normalized as paths.
    """
    return ConfigLayer(
        origin=origin,
        scope_root=None,
        precedence=precedence,
        kind=kind,
        config=config,
    )


def _best_effort_provenance_path(path: Path) -> Path:
    """Return a normalized provenance path without requiring the file to exist.

    Resolved TOML source records normally point to existing files because loaded
    sources were canonicalized by `resolve_topmark_toml_sources()`. Some machine
    payload and bridge tests intentionally construct provenance-only paths that
    do not exist on disk. For those records, use non-strict resolution so layer
    construction can still preserve stable provenance without pretending the path
    is a processable filesystem target.

    Args:
        path: File-backed provenance path.

    Returns:
        Canonical processing path when the file exists, otherwise a non-strict
        resolved path suitable for provenance-only records.
    """
    try:
        return canonical_processing_path(path)
    except FileNotFoundError:
        return path.resolve()


def _make_default_config_layer() -> ConfigLayer:
    """Return the built-in defaults as the first config provenance layer."""
    return _make_config_layer(
        origin=SyntheticConfigSource(label=DEFAULT_LAYER_ORIGIN),
        kind=ConfigLayerKind.DEFAULT,
        precedence=DEFAULT_LAYER_PRECEDENCE,
        config=mutable_config_from_defaults(),
    )


def _make_layer_from_layered_toml_table(
    path: Path | SyntheticConfigSource,
    *,
    data: TomlTable,
    kind: ConfigLayerKind,
    precedence: int,
) -> ConfigLayer:
    """Build one config provenance layer from a layered TOML fragment.

    Args:
        path: Real source TOML file path or synthetic source marker used for
            provenance and, for real paths, path-relative normalization.
        data: Layered TOML fragment extracted from one split-parsed TopMark
            TOML source and already validated at the TOML layer.
        kind: Provenance kind for the resulting config layer.
        precedence: Stable merge precedence for the resulting config layer.

    Returns:
        Normalized config provenance layer built from the layered TOML
        fragment.
    """
    if isinstance(path, Path):
        # This path is provenance for a TOML layer, not necessarily a file that
        # TopMark will process. Use best-effort normalization here; strict
        # processing identity belongs to loaded source resolution and target-file
        # applicability checks.
        resolved_path: Path = _best_effort_provenance_path(path)
        config: MutableConfig = mutable_config_from_layered_toml_table(
            data,
            config_file=resolved_path,
        )
        return ConfigLayer(
            origin=resolved_path,
            kind=kind,
            precedence=precedence,
            scope_root=resolved_path.parent,
            config=config,
        )

    config = mutable_config_from_layered_toml_table(
        data,
        config_file=path,
    )
    return _make_config_layer(
        origin=path,
        kind=kind,
        precedence=precedence,
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
        if source.parsed is None:
            logger.debug(
                "Skipping config layer for unreadable or invalid TOML source: %s",
                source.path,
            )
            continue
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
