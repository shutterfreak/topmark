# topmark:header:start
#
#   project      : TopMark
#   file         : getters.py
#   file_relpath : src/topmark/config/io/getters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Value getters for TOML config tables.

This module contains small helpers for extracting values from parsed TOML tables.

Two families of getters exist:
- *Unchecked* getters: return defaults and only emit **debug** logs.
- *Checked* getters: validate the expected shape and record **warnings** in a
  `DiagnosticLog` (and also log a warning).

The checked getters are used when parsing config files so that user mistakes are
surfaced without crashing or changing defaulting behavior.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Final, TypeVar

from topmark.config.logging import get_logger

from .guards import is_any_list

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger
    from topmark.core.diagnostics import DiagnosticLog

    from .types import TomlTable

logger: TopmarkLogger = get_logger(__name__)

E = TypeVar("E", bound=Enum)


def get_string_value(table: TomlTable, key: str, default: str = "") -> str:
    """Extract a string value from a TOML table.

    If the value is a ``str``, it is returned as is. If the value is of type
    ``int``, ``float``, or ``bool``, it is coerced to a string using ``str(...)``.
    When the key is missing or the value is not coercible, ``default`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.
        default (str): Default value if the key is not found or not coercible.

    Returns:
        str: The extracted or coerced string value, or ``default``.
    """
    # Coerce various types to string if possible; fallback to default
    value: Any | None = table.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    logger.debug(
        "Cannot coerce %r to string, returning default (%s)",
        value,
        default,
    )
    return default


def get_string_value_or_none(table: TomlTable, key: str) -> str | None:
    """Extract an optional string value from a TOML table.

    If the value is a ``str``, it is returned as is. If the value is of type
    ``int``, ``float``, or ``bool``, it is coerced to a string using ``str(...)``.
    When the key is missing, ``None`` is returned. If the key is present but
    the value is not coercible, ``None`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.

    Returns:
        str | None: The extracted or coerced string value, or ``None`` when absent or not coercible.
    """
    # Coerce various types to string if possible
    value: Any | None = table.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    logger.debug(
        "Cannot coerce %r to string, returning None",
        value,
    )
    return None


def get_bool_value(
    table: TomlTable,
    key: str,
    default: bool = False,
) -> bool:
    """Extract a boolean value from a TOML table.

    If the value is a ``bool``, it is returned as is. If the value is an integer,
    it is coerced via ``bool(value)``. When the key is missing or the value is not
    coercible, ``default`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.
        default (bool): Default value if the key is not found or not coercible.

    Returns:
        bool: The extracted or coerced boolean value, or ``default``.
    """
    # Extract boolean value, coercing int to bool if needed; fallback to default
    value: Any | None = table.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    logger.debug(
        "Cannot coerce %r to bool, returning default (%r)",
        value,
        default,
    )
    return default


def get_bool_value_or_none(table: TomlTable, key: str) -> bool | None:
    """Extract an optional boolean value from a TOML table.

    If the value is a ``bool``, it is returned as is. If the value is an integer,
    it is coerced via ``bool(value)``. When the key is missing, ``None`` is returned.
    If the key is present but not coercible, ``None`` is returned.

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.

    Returns:
        bool | None: The extracted or coerced boolean value, or ``None``
            when absent or not coercible.
    """
    # Extract boolean value, coercing int to bool if needed
    value: Any | None = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    logger.debug(
        "Cannot coerce %r to bool, returning None",
        value,
    )
    return None


def get_list_value(
    table: TomlTable,
    key: str,
    default: list[Any] | None = None,
) -> list[Any]:
    """Extract a list value from a TOML table.

    If the key is present and the value is a list, it is returned (shallow copy;
    no item-level validation).
    Otherwise, ``default`` is returned (or ``[]`` when ``default`` is ``None``).

    Args:
        table (TomlTable): Table to query.
        key (str): Key to extract.
        default (list[Any] | None): Default list when the key is missing or not a list.

    Returns:
        list[Any]: The list value, ``default``, or an empty list.
    """
    # Extract list value, ensure list type or fallback to default
    value: Any | None = table.get(key)
    if is_any_list(value):
        return value
    logger.debug(
        "Expected list for key %s, got %r; using default (%r)",
        key,
        value,
        default or [],
    )
    return default or []


# --- Schema/shape validation helpers (checked): scalar types ---


def get_string_value_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
    default: str = "",
) -> str:
    """Return a string value, recording a warning when the type is not `str`.

    Unlike `get_string_value()`, this helper does **not** coerce ints/bools/floats
    to strings. If the key is missing, `default` is returned.
    """
    value: Any | None = table.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return value

    loc: Final[str] = f"{where}.{key}"
    logger.warning("Expected string in %s, got %s: %r", loc, type(value).__name__, value)
    diagnostics.add_warning(f"Expected string in {loc}, got {type(value).__name__}: {value}")
    return default


def get_string_value_or_none_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> str | None:
    """Return an optional string value, warning when present but not `str`.

    Mirrors [`topmark.config.args_io.get_arg_string_or_none_checked`][].
    """
    value: Any | None = table.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value

    loc: Final[str] = f"{where}.{key}"
    logger.warning("Expected string in %s, got %s: %r", loc, type(value).__name__, value)
    diagnostics.add_warning(f"Expected string in {loc}, got {type(value).__name__}: {value}")
    return None


def get_bool_value_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
    default: bool = False,
) -> bool:
    """Return a boolean value, recording a warning when the type is not `bool`.

    Unlike `get_bool_value()`, this helper does **not** coerce integers.
    If the key is missing, `default` is returned.
    """
    value: Any | None = table.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    loc: Final[str] = f"{where}.{key}"
    logger.warning("Expected bool in %s, got %s: %r", loc, type(value).__name__, value)
    diagnostics.add_warning(f"Expected bool in {loc}, got {type(value).__name__}: {value}")
    return default


def get_bool_value_or_none_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> bool | None:
    """Return an optional boolean value, warning when present but not `bool`.

    Mirrors [`topmark.config.args_io.get_arg_bool_or_none_checked`][].
    """
    value: Any | None = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    loc: Final[str] = f"{where}.{key}"
    logger.warning("Expected bool in %s, got %s: %r", loc, type(value).__name__, value)
    diagnostics.add_warning(f"Expected bool in {loc}, got {type(value).__name__}: {value}")
    return None


def get_int_value_or_none_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> int | None:
    """Return an optional int value, warning when present but not `int`.

    Mirrors [`topmark.config.args_io.get_arg_int_or_none_checked`][].

    Notes:
        - Missing key / None -> None
        - `bool` is rejected (since `bool` is a subclass of `int`).
    """
    value: Any | None = table.get(key)
    if value is None:
        return None

    loc: Final[str] = f"{where}.{key}"

    # Note: bool is a subclass of int; exclude it.
    if isinstance(value, bool):
        logger.warning("Expected int in %s, got bool: %r", loc, value)
        diagnostics.add_warning(f"Expected int in {loc}, got bool: {value!r}")
        return None

    if isinstance(value, int):
        return value

    logger.warning("Expected int in %s, got %s: %r", loc, type(value).__name__, value)
    diagnostics.add_warning(f"Expected int in {loc}, got {type(value).__name__}: {value!r}")
    return None


# --- Schema/shape validation helpers (checked): list types ---


def get_string_list_value_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> list[str]:
    """Extract a list of strings from a TOML table, recording a warning when the type is incorrect.

    Mirrors [`topmark.config.args_io.get_arg_string_list_checked`][].

    By using `get_string_list_value()` we enforce "list of strings" for header field
    selection in TOML, drop non-strings with a warning + diagnostic, and give uniform,
    stable warning locations like: "Ignoring non-string entry in [header].fields: ..."

    Behavior:
        - If the key is missing or not a list, returns [].
        - If the list contains non-string items, they are ignored.
        - Each ignored entry emits a warning and a diagnostic with TOML location.

    Args:
        table (TomlTable): TOML table to query.
        key (str): Key to extract.
        where (str): TOML location prefix (e.g. "[files]").
        diagnostics (DiagnosticLog): DiagnosticLog to record warnings.
        logger (TopmarkLogger): Logger for emitting warnings.

    Returns:
        list[str]: Filtered list containing only string entries.
    """
    value: Any | None = table.get(key)
    if value is None:
        return []

    loc: Final[str] = f"{where}.{key}"

    if not is_any_list(value):
        logger.warning("Expected list in %s, got %s: %r", loc, type(value).__name__, value)
        diagnostics.add_warning(f"Expected list in {loc}, got {type(value).__name__}: {value!r}")
        return []

    vals_any: list[Any] = value
    if not vals_any:
        return []

    out: list[str] = []
    for v in vals_any:
        if isinstance(v, str):
            out.append(v)
        else:
            logger.warning("Ignoring non-string entry in %s: %r", loc, v)
            diagnostics.add_warning(f"Ignoring non-string entry in {loc}: {v!r}")

    return out


# --- Schema/shape validation helpers (checked): enum types ---


def get_enum_value_checked(
    table: TomlTable,
    key: str,
    enum_cls: type[E],
    *,
    where: str,
    diagnostics: DiagnosticLog,
    logger: TopmarkLogger,
) -> E | None:
    """Parse an enum value from TOML.

    Mirrors [`topmark.config.args_io.get_arg_enum_checked`][].

    Expected input is a `str` matching one of the Enum values.

    - Missing key -> None
    - Wrong type -> warning + None
    - Unknown enum value -> error + None

    This is intended for schema-level validation (e.g. `[writer].target`).
    """
    raw: Any | None = table.get(key)
    if raw is None:
        return None

    loc: Final[str] = f"{where}.{key}"
    if not isinstance(raw, str):
        logger.warning(
            "Expected string enum value in %s, got %s: %r",
            loc,
            type(raw).__name__,
            raw,
        )
        diagnostics.add_warning(
            f"Expected string enum value in {loc}, got {type(raw).__name__}: {raw!r}"
        )
        return None

    try:
        return enum_cls(raw)
    except ValueError:
        allowed: str = ", ".join(str(e.value) for e in enum_cls)
        logger.warning("Invalid value for %s: %r (allowed: %s)", loc, raw, allowed)
        diagnostics.add_warning(f"Invalid value for {loc}: {raw!r} (allowed: {allowed})")
        return None
