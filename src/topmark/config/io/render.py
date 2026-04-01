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
from typing import TYPE_CHECKING
from typing import cast

import tomlkit

from topmark.core.logging import get_logger
from topmark.toml.guards import as_object_dict
from topmark.toml.guards import toml_table_from_mapping

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable

logger: TopmarkLogger = get_logger(__name__)


def _tomlkit_dumps(data: TomlTable) -> str:
    """Render a TOML table via tomlkit behind a small typed boundary."""
    cleaned: object = _strip_none_for_toml(data)
    cleaned_mapping: dict[str, object] = as_object_dict(cleaned)

    # A targeted Pyright suppression is appropriate here because the third-party
    # tomlkit stub exposes `dumps` with partially unknown Mapping parameter types.
    rendered: str = tomlkit.dumps(cleaned_mapping)  # pyright: ignore[reportUnknownMemberType]
    return rendered


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
        toml_dict: TOML mapping to render.

    Returns:
        The rendered TOML document as a string.
    """
    return _tomlkit_dumps(toml_dict)


def clean_toml_text(text: str) -> str:
    """Normalize a TOML document, removing comments and formatting noise.

    This function round-trips the input through the TOML parser and dumper, dropping comments and
    normalizing formatting.

    Args:
        text: Raw TOML content.

    Returns:
        A normalized TOML string produced by round-tripping.
    """
    doc: tomlkit.TOMLDocument = tomlkit.parse(text)
    unwrapped: dict[str, object] = doc.unwrap()
    data: TomlTable = toml_table_from_mapping(as_object_dict(unwrapped))
    return _tomlkit_dumps(data)
