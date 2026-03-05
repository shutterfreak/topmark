# topmark:header:start
#
#   project      : TopMark
#   file         : args_io.py
#   file_relpath : src/topmark/config/args_io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""ArgsLike validation helpers.

These helpers validate values coming from a weakly-typed mapping (CLI or API)
and record diagnostics when a key is present but has an unexpected type.

Design:
- Missing key / None value -> return None (or empty list), no diagnostics.
- Wrong type -> emit a WARNING diagnostic and return None / empty list.
- Enum parsing -> emit WARNING for wrong type, WARNING for invalid value
  (caller decides whether strict mode stops).

This mirrors the TOML `*_checked` helpers in [`topmark.config.io`][topmark.config.io],
but the location string is simply the argument key.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar
from typing import cast

if TYPE_CHECKING:
    from topmark.config.types import ArgsLike
    from topmark.diagnostic.model import DiagnosticLog

_E = TypeVar("_E", bound=Enum)


def get_arg_bool_or_none_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
) -> bool | None:
    """Return an optional boolean value, warning when present but not `bool`.

    Mirrors the TOML helper [`topmark.config.io.getters.get_bool_value_or_none_checked`][].
    """
    value: Any | None = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    diagnostics.add_warning(f"Expected bool in {key}, got {type(value).__name__}: {value}")
    return None


def get_arg_int_or_none_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
) -> int | None:
    """Return an optional int value, warning when present but not `int`.

    Mirrors the TOML helper [`topmark.config.io.getters.get_int_value_or_none_checked`][].
    TODO mirror implementation in config/io.py
    """
    value: Any | None = args.get(key)
    if value is None:
        return None

    # Note: bool is a subclass of int; exclude it.
    if isinstance(value, bool):
        diagnostics.add_warning(f"Expected int in {key}, got bool: {value}")
        return None

    if isinstance(value, int):
        return value

    diagnostics.add_warning(f"Expected int in {key}, got {type(value).__name__}: {value}")
    return None


def get_arg_string_or_none_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
) -> str | None:
    """Return an optional string value, warning when present but not `str`.

    Mirrors the TOML helper [`topmark.config.io.getters.get_string_value_or_none_checked`][].
    """
    value: Any | None = args.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value

    diagnostics.add_warning(f"Expected string in {key}, got {type(value).__name__}: {value}")
    return None


def get_arg_string_list_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
) -> list[str]:
    """Return a list of strings for `key`, warning when present but not a list of strings.

    Mirrors the TOML helper [`topmark.config.io.getters.get_string_list_value_checked`][].

    Behavior:
        - Missing key / None -> []
        - Wrong container type -> warning + []
        - Mixed list -> drop non-strings with warning per dropped item

    Args:
        args: TOML table to query.
        key: Key to extract.
        diagnostics: DiagnosticLog to record warnings.

    Returns:
        Filtered list containing only string entries.
    """
    vals_any: object | None = args.get(key)
    if vals_any is None:
        return []

    if not isinstance(vals_any, list | tuple):
        diagnostics.add_warning(
            f"Expected list of strings in {key}, got {type(vals_any).__name__}: {vals_any!r}"
        )
        return []

    out: list[str] = []

    # Narrow items to `object` so Pyright doesn't treat loop variables as `Unknown`.
    seq = cast("list[object] | tuple[object, ...]", vals_any)
    for v_any in seq:
        if isinstance(v_any, str):
            out.append(v_any)
        else:
            diagnostics.add_warning(f"Ignoring non-string entry in {key}: {v_any!r}")

    return out


def get_arg_enum_checked(
    args: ArgsLike,
    key: str,
    enum_cls: type[_E],
    *,
    diagnostics: DiagnosticLog,
) -> _E | None:
    """Parse an Enum value from ArgsLike.

    Mirrors the TOML helper [`topmark.config.io.getters.get_enum_value_checked`][].

    Expected input is a `str` matching one of the Enum values.

    - Missing key / None -> None
    - Wrong type -> warning + None
    - Unknown enum value -> warning + None
    """
    raw: Any | None = args.get(key)
    if raw is None:
        return None

    if not isinstance(raw, str):
        diagnostics.add_warning(
            f"Expected string enum value in {key}, got {type(raw).__name__}: {raw!r}"
        )
        return None

    try:
        return enum_cls(raw)
    except ValueError:
        allowed: str = ", ".join(str(e.value) for e in enum_cls)
        diagnostics.add_warning(f"Invalid value for {key}: {raw!r} (allowed: {allowed})")
        return None
