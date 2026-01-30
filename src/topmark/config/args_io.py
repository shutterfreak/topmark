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
from typing import TYPE_CHECKING, Any, TypeVar, cast

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.config.types import ArgsLike
    from topmark.core.diagnostics import DiagnosticLog

E = TypeVar("E", bound=Enum)


logger: TopmarkLogger = get_logger(__name__)


def get_arg_bool_or_none_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> bool | None:
    """Return an optional boolean value, warning when present but not `bool`.

    Mirrors the TOML helper [`topmark.config.io.get_bool_value_or_none_checked`][].
    """
    value: Any | None = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    logger.warning("Expected bool in %s, got %s: %r", key, type(value).__name__, value)
    diagnostics.add_warning(f"Expected bool in {key}, got {type(value).__name__}: {value}")
    return None


def get_arg_int_or_none_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> int | None:
    """Return an optional int value, warning when present but not `int`.

    Mirrors the TOML helper [`topmark.config.io.get_int_value_or_none_checked`][].
    TODO mirror implementation in config/io.py
    """
    value: Any | None = args.get(key)
    if value is None:
        return None

    # Note: bool is a subclass of int; exclude it.
    if isinstance(value, bool):
        logger.warning("Expected int in %s, got bool: %r", key, value)
        diagnostics.add_warning(f"Expected int in {key}, got bool: {value}")
        return None

    if isinstance(value, int):
        return value

    logger.warning("Expected int in %s, got %s: %r", key, type(value).__name__, value)
    diagnostics.add_warning(f"Expected int in {key}, got {type(value).__name__}: {value}")
    return None


def get_arg_string_or_none_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> str | None:
    """Return an optional string value, warning when present but not `str`.

    Mirrors the TOML helper [`topmark.config.io.get_string_value_or_none_checked`][].
    """
    value: Any | None = args.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value

    logger.warning("Expected string in %s, got %s: %r", key, type(value).__name__, value)
    diagnostics.add_warning(f"Expected string in {key}, got {type(value).__name__}: {value}")
    return None


def get_arg_string_list_checked(
    args: ArgsLike,
    key: str,
    *,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> list[str]:
    """Return a list of strings for `key`, warning when present but not a list of strings.

    Mirrors the TOML helper [`topmark.config.io.get_string_list_value_checked`][].

    Behavior:
        - Missing key / None -> []
        - Wrong container type -> warning + []
        - Mixed list -> drop non-strings with warning per dropped item

    Args:
        args (ArgsLike): TOML table to query.
        key (str): Key to extract.
        diagnostics (DiagnosticLog): DiagnosticLog to record warnings.
        logger (TopmarkLogger): Logger for emitting warnings.

    Returns:
        list[str]: Filtered list containing only string entries.
    """
    vals_any: object | None = args.get(key)
    if vals_any is None:
        return []

    if not isinstance(vals_any, (list, tuple)):
        logger.warning(
            "Expected list of strings in %s, got %s: %r",
            key,
            type(vals_any).__name__,
            vals_any,
        )
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
            logger.warning("Ignoring non-string entry in %s: %r", key, v_any)
            diagnostics.add_warning(f"Ignoring non-string entry in {key}: {v_any!r}")

    return out


def get_arg_enum_checked(
    args: ArgsLike,
    key: str,
    enum_cls: type[E],
    *,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> E | None:
    """Parse an Enum value from ArgsLike.

    Mirrors the TOML helper [`topmark.config.io.get_enum_value_checked`][].

    Expected input is a `str` matching one of the Enum values.

    - Missing key / None -> None
    - Wrong type -> warning + None
    - Unknown enum value -> warning + None
    """
    raw: Any | None = args.get(key)
    if raw is None:
        return None

    if not isinstance(raw, str):
        logger.warning(
            "Expected string enum value in %s, got %s: %r",
            key,
            type(raw).__name__,
            raw,
        )
        diagnostics.add_warning(
            f"Expected string enum value in {key}, got {type(raw).__name__}: {raw!r}"
        )
        return None

    try:
        return enum_cls(raw)
    except ValueError:
        allowed: str = ", ".join(str(e.value) for e in enum_cls)
        logger.warning("Invalid value for %s: %r (allowed: %s)", key, raw, allowed)
        diagnostics.add_warning(f"Invalid value for {key}: {raw!r} (allowed: {allowed})")
        return None
