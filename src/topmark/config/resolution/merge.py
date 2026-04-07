# topmark:header:start
#
#   project      : TopMark
#   file         : merge.py
#   file_relpath : src/topmark/config/resolution/merge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Layer applicability and merge helpers for config resolution.

This module contains pure helpers that:
    - select which config provenance layers apply to a target path
    - merge config provenance layers in stable precedence order
    - build effective per-path mutable config drafts

Layer construction from resolved TOML sources lives in
[`topmark.config.resolution.layers`][topmark.config.resolution.layers].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.config.resolution.layers import ConfigLayer
    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


def _is_within_scope(path: Path, scope_root: Path) -> bool:
    """Return whether `path` is within the given layer scope root."""
    resolved_path: Path = path.resolve()
    resolved_scope_root: Path = scope_root.resolve()
    result: bool
    try:
        resolved_path.relative_to(resolved_scope_root)
        result = True
    except ValueError:
        result = False

    return result


# ---- Layer merge / applicability helpers ----


def merge_layers_globally(layers: Iterable[ConfigLayer]) -> MutableConfig:
    """Merge config provenance layers into one mutable config draft.

    Args:
        layers: Config provenance layers in stable precedence order.

    Returns:
        Mutable config draft produced by merging the supplied layers in order.
    """
    layer_list: list[ConfigLayer] = list(layers)
    logger.debug("Merging %d config layer(s) into mutable config draft", len(layer_list))

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
    """Return the config provenance layers that apply to a file path.

    Global layers (`scope_root is None`) always apply. File-backed layers apply
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
    target path, then merges them in stable precedence order using
    `MutableConfig.merge_with`.

    Args:
        layers: Candidate config provenance layers.
        path: Target file path for which to build the effective config.

    Returns:
        The merged mutable config draft applicable to `path`.
    """
    applicable: list[ConfigLayer] = select_applicable_layers(layers, path)
    draft: MutableConfig = merge_layers_globally(applicable)
    logger.debug(
        "Built effective config for %s from %d applicable layer(s)",
        path.resolve(),
        len(applicable),
    )

    return draft
