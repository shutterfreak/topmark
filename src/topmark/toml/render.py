# topmark:header:start
#
#   project      : TopMark
#   file         : render.py
#   file_relpath : src/topmark/toml/render.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Render and normalize TopMark TOML documents.

This module contains small TOML-format helpers for:
- rendering a [`TomlTable`][topmark.toml.types.TomlTable] to TOML text
- normalizing TOML text by round-tripping through `tomlkit`

TOML has no `null` value, so `None` entries must be omitted during rendering.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import cast

import tomlkit

from topmark.core.logging import get_logger
from topmark.core.typing_guards import as_object_dict
from topmark.toml.typing_guards import toml_table_from_mapping

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable

logger: TopmarkLogger = get_logger(__name__)


def _strip_none_for_toml(value: object) -> object:
    """Remove TOML-incompatible `None` values from mappings and lists.

    TOML has no `null`. During rendering, keys with `None` values are omitted
    and `None` items are dropped from lists.

    Notes:
        - The input is typed as `object` (not `Any`) so Pyright does not treat
          mapping/list iterators as `Unknown`.
        - Mapping keys are defensively normalized to strings, since TOML tables
          are string-keyed.
    """
    # Recursively normalize mappings/lists into TOML-compatible plain-Python
    # shapes while dropping `None` entries.
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


def _tomlkit_dumps(data: TomlTable) -> str:
    """Render a TOML table through `tomlkit` behind a small typed boundary.

    Args:
        data: TOML table to render.

    Returns:
        Rendered TOML document text.
    """
    # Strip TOML-incompatible `None` values first, then normalize to a plain
    # string-keyed mapping acceptable to `tomlkit.dumps()`.
    cleaned: object = _strip_none_for_toml(data)
    cleaned_mapping: dict[str, object] = as_object_dict(cleaned)

    # A targeted Pyright suppression is appropriate here because the third-party
    # `tomlkit` stub exposes `dumps()` with partially unknown mapping parameter
    # types.
    rendered: str = tomlkit.dumps(cleaned_mapping)  # pyright: ignore[reportUnknownMemberType]
    return rendered


def render_toml_table(toml_dict: TomlTable) -> str:
    """Render a TOML table to TOML text.

    Args:
        toml_dict: TOML table to render.

    Returns:
        The rendered TOML document as a string.
    """
    return _tomlkit_dumps(toml_dict)


def clean_toml_text(text: str) -> str:
    """Normalize TOML text by round-tripping through `tomlkit`.

    This helper parses the input, unwraps it to plain Python data, and renders
    it again. Comments and formatting noise are dropped during the round-trip.

    Args:
        text: Raw TOML content.

    Returns:
        A normalized TOML string produced by round-tripping.
    """
    # Parse -> unwrap -> normalize -> re-render, yielding a canonicalized TOML
    # text form without original comments or formatting details.
    doc: tomlkit.TOMLDocument = tomlkit.parse(text)
    unwrapped: dict[str, object] = doc.unwrap()
    data: TomlTable = toml_table_from_mapping(as_object_dict(unwrapped))
    return _tomlkit_dumps(data)
