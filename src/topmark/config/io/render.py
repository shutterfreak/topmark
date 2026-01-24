# topmark:header:start
#
#   project      : TopMark
#   file         : render.py
#   file_relpath : src/topmark/config/io/render.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Render and normalize TOML for config dumps.

This module contains helpers for serializing a `TomlTable` to a TOML string,
and for round-tripping TOML for normalization.

TOML has no `null` value, so `None` entries are stripped during rendering.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

import tomlkit

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger

    from .types import TomlTable

logger: TopmarkLogger = get_logger(__name__)


def _tomlkit_dumps(data: TomlTable) -> str:
    """Typed wrapper around tomlkit.dumps() for strict type checking."""
    cleaned: Any = _strip_none_for_toml(data)
    # tomlkit expects a Mapping; tomlkit itself is treated as untyped here.
    return cast("str", cast("Any", tomlkit).dumps(cast("Mapping[str, Any]", cleaned)))


def _strip_none_for_toml(value: object) -> object:
    """Remove TOML-incompatible `None` from mappings/lists.

    TOML has no `null`. For config dumps we omit keys with None values and drop
    None items from lists.

    Notes:
        - The input is typed as `object` (not `Any`) so Pyright does not treat
          mapping/list iterators as `Unknown`.
        - We defensively normalize mapping keys to strings, since TOML tables
          are string-keyed.
    """
    if isinstance(value, Mapping):
        out: dict[str, object] = {}
        m: Mapping[object, object] = cast("Mapping[object, object]", value)
        for k_any, v_any in m.items():
            if v_any is None:
                logger.debug("Ignoring `None` entry in Mapping for key %s", k_any)
                continue
            k: str = k_any if isinstance(k_any, str) else str(k_any)
            out[k] = _strip_none_for_toml(v_any)
        return out

    if isinstance(value, list):
        out_list: list[object] = []
        seq: list[object] = cast("list[object]", value)
        for v_any in seq:
            if v_any is None:
                logger.debug("Ignoring `None` entry in list")
                continue
            out_list.append(_strip_none_for_toml(v_any))
        return out_list

    return value


def to_toml(toml_dict: TomlTable) -> str:
    """Serialize a TOML mapping to a string.

    Args:
        toml_dict (TomlTable): TOML mapping to render.

    Returns:
        str: The rendered TOML document as a string.
    """
    return _tomlkit_dumps(toml_dict)


def clean_toml(text: str) -> str:
    """Normalize a TOML document, removing comments and formatting noise.

    This function round-trips the input through the TOML parser and dumper,
    dropping comments and normalizing formatting.

    Args:
        text (str): Raw TOML content.

    Returns:
        str: A normalized TOML string produced by round-tripping.
    """
    doc: tomlkit.TOMLDocument = tomlkit.parse(text)
    data_any: Any = doc.unwrap()
    data: TomlTable = cast("TomlTable", data_any) if isinstance(data_any, dict) else {}
    return _tomlkit_dumps(data)
