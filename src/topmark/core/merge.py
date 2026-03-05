# topmark:header:start
#
#   project      : TopMark
#   file         : merge.py
#   file_relpath : src/topmark/core/merge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Merge and extraction helpers for TopMark configuration.

This module centralizes small, typed utilities used across TopMark for:

1) Overlay merges of optional values
   (e.g., "use override if provided, else keep current").

2) Extracting typed optional values from config mappings
   (e.g., TOML tables), returning `None` when the key is absent.

These helpers intentionally avoid importing TopMark configuration models to
prevent type-check-time import cycles. They are safe to use in `topmark.config`,
`topmark.pipeline`, CLI code, and plugins.

Design principles:
- *Absent* keys should generally map to `None` (inherit), not to a default.
- Extraction helpers are conservative: invalid values return `None` so the caller
  can decide whether to warn, error, or keep defaults.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

if TYPE_CHECKING:
    from collections.abc import Mapping

T = TypeVar("T")
E = TypeVar("E", bound=Enum)


# NOTE: Python 3.12+ does not need TypeVar("T") and allows:
# def pick[T](*, current: T | None, override: T | None) -> T | None:
def overlay(*, current: T | None, override: T | None) -> T | None:
    """Return `override` when set, otherwise return `current`.

    This is the core "last-wins overlay" primitive used throughout config merging.

    Args:
        current: The current value (possibly inherited).
        override: The overriding value (highest precedence). `None` means "unset".

    Returns:
        The override value if it is not `None`, otherwise the current value.
    """
    return override if override is not None else current


def opt_bool(tbl: Mapping[str, Any] | None, *, key: str) -> bool | None:
    """Return an optional bool value from a mapping.

    Args:
        tbl: Mapping (e.g., a parsed TOML table). If `None`, returns `None`.
        key: Key to read.

    Returns:
        - `None` if `tbl` is falsy or `key` is absent.
        - `bool(tbl[key])` otherwise.

    Notes:
        This mirrors TOML parsing behavior in TopMark today: values are coerced
        via `bool(...)`. If you later want stricter typing (only accept actual
        booleans), introduce a `strict_opt_bool()` variant.
    """
    if not tbl or key not in tbl:
        return None
    return bool(tbl[key])


def opt_enum(tbl: Mapping[str, Any] | None, *, key: str, enum_cls: type[E]) -> E | None:
    """Return an optional Enum member from a mapping.

    Args:
        tbl: Mapping (e.g., a parsed TOML table). If `None`, returns `None`.
        key: Key to read.
        enum_cls: Enum class used to interpret the value.

    Returns:
        - `None` if `tbl` is falsy or `key` is absent.
        - An enum member when `tbl[key]` can be converted via `enum_cls(value)`.
        - `None` when conversion fails (invalid/unknown value).

    Examples:
        ```py
        mode = opt_enum(tbl, key="empty_insert_mode", enum_cls=EmptyInsertMode)
        ```
    """
    if not tbl or key not in tbl:
        return None

    val = tbl[key]
    try:
        # Accept member values ("logical_empty") and already-typed members.
        return enum_cls(val)
    except (ValueError, TypeError):
        return None
