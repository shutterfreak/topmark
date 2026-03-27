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
from typing import TYPE_CHECKING
from typing import Final
from typing import TypeVar

from topmark.config.io.guards import is_any_list
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.io.types import TomlTable
    from topmark.config.io.types import TomlValue
    from topmark.core.logging import TopmarkLogger
    from topmark.diagnostic.model import DiagnosticLog

logger: TopmarkLogger = get_logger(__name__)

E = TypeVar("E", bound=Enum)


def get_string_value(table: TomlTable, key: str, default: str = "") -> str:
    """Extract a string value from a TOML table.

    If the value is a ``str``, it is returned as is. If the value is of type
    ``int``, ``float``, or ``bool``, it is coerced to a string using ``str(...)``.
    When the key is missing or the value is not coercible, ``default`` is returned.

    Args:
        table: Table to query.
        key: Key to extract.
        default: Default value if the key is not found or not coercible.

    Returns:
        The extracted or coerced string value, or ``default``.
    """
    # Coerce various types to string if possible; fallback to default
    value: TomlValue = table.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool):
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
        table: Table to query.
        key: Key to extract.

    Returns:
        The extracted or coerced string value, or ``None`` when absent or not coercible.
    """
    # Coerce various types to string if possible
    value: TomlValue = table.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool):
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

    If the value is a ``bool``, it is returned as is. If the value is missing or
    not of type ``bool``, ``default`` is returned.

    Args:
        table: Table to query.
        key: Key to extract.
        default: Default value if the key is not found or not coercible.

    Returns:
        The extracted boolean value, or ``default``.
    """
    # Extract boolean value, coercing int to bool if needed; fallback to default
    value: TomlValue = table.get(key)
    if isinstance(value, bool):
        return value
    logger.debug(
        "Expecting bool value, found %r of type %r, returning default (%r)",
        value,
        type(value),
        default,
    )
    return default


def get_bool_value_or_none(table: TomlTable, key: str) -> bool | None:
    """Extract an optional boolean value from a TOML table.

    If the value is a ``bool``, it is returned as is. If the value is missing or
    not of type ``bool``, ``None`` is returned.

    Args:
        table: Table to query.
        key: Key to extract.

    Returns:
        The extracted boolean value, or ``None`` when absent or not of type ``bool``.
    """
    value: TomlValue = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    logger.debug("Expecting bool value, found %r of type %r, returning None", value, type(value))
    return None


def get_list_value(
    table: TomlTable,
    key: str,
    default: list[object] | None = None,
) -> list[object]:
    """Extract a list value from a TOML table.

    If the key is present and the value is a list, a shallow copy is returned
    without item-level validation.
    Otherwise, ``default`` is returned (or ``[]`` when ``default`` is ``None``).

    Args:
        table: Table to query.
        key: Key to extract.
        default: Default list when the key is missing or not a list.

    Returns:
        A shallow copy of the list value, ``default``, or an empty list.
    """
    value: TomlValue = table.get(key)
    if is_any_list(value):
        return list(value)  # Return a copy

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
    default: str = "",
) -> str:
    """Return a string value, recording a warning when the type is not `str`.

    Unlike `get_string_value()`, this helper does **not** coerce ints/bools/floats
    to strings. If the key is missing, `default` is returned.
    """
    value: TomlValue = table.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        return value

    loc: Final[str] = f"{where}.{key}"
    diagnostics.add_warning(f"Expected string in {loc}, got {type(value).__name__}: {value}")
    return default


def get_string_value_or_none_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
) -> str | None:
    """Return an optional string value, warning when present but not `str`."""
    value: TomlValue = table.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value

    loc: Final[str] = f"{where}.{key}"
    diagnostics.add_warning(f"Expected string in {loc}, got {type(value).__name__}: {value}")
    return None


def get_bool_value_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
    default: bool = False,
) -> bool:
    """Return a boolean value, recording a warning when the type is not `bool`.

    Unlike `get_bool_value()`, this helper does **not** coerce integers.
    If the key is missing, `default` is returned.
    """
    value: TomlValue = table.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    loc: Final[str] = f"{where}.{key}"
    diagnostics.add_warning(f"Expected bool in {loc}, got {type(value).__name__}: {value}")
    return default


def get_bool_value_or_none_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
) -> bool | None:
    """Return an optional boolean value, warning when present but not `bool`."""
    value: TomlValue = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    loc: Final[str] = f"{where}.{key}"
    diagnostics.add_warning(f"Expected bool in {loc}, got {type(value).__name__}: {value}")
    return None


def get_int_value_or_none_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
) -> int | None:
    """Return an optional int value, warning when present but not `int`.

    Notes:
        - Missing key / None -> None
        - `bool` is rejected (since `bool` is a subclass of `int`).
    """
    value: TomlValue = table.get(key)
    if value is None:
        return None

    loc: Final[str] = f"{where}.{key}"

    # Note: bool is a subclass of int; exclude it.
    if isinstance(value, bool):
        diagnostics.add_warning(f"Expected int in {loc}, got bool: {value!r}")
        return None

    if isinstance(value, int):
        return value

    diagnostics.add_warning(f"Expected int in {loc}, got {type(value).__name__}: {value!r}")
    return None


# --- Schema/shape validation helpers (checked): list types ---


def get_string_list_value_checked(
    table: TomlTable,
    key: str,
    *,
    where: str,
    diagnostics: DiagnosticLog,
) -> list[str]:
    """Extract a list of strings from a TOML table, recording a warning when the type is incorrect.

    This helper enforces a “list of strings” shape for TOML list fields.

    Non-string values in the list are dropped with a diagnostic with a uniform,
    stable warning location like: "Ignoring non-string entry in [header].fields: ..."

    Behavior:
        - If the key is missing or not a list, returns [].
        - If the list contains non-string items, they are ignored.
        - Each ignored entry emits a warning and a diagnostic with TOML location.

    Args:
        table: TOML table to query.
        key: Key to extract.
        where: TOML location prefix (e.g. "[files]").
        diagnostics: DiagnosticLog to record warnings.

    Returns:
        Filtered list containing only string entries.
    """
    value: TomlValue = table.get(key)
    if value is None:
        return []

    loc: Final[str] = f"{where}.{key}"

    if not is_any_list(value):
        diagnostics.add_warning(f"Expected list in {loc}, got {type(value).__name__}: {value!r}")
        return []

    vals_any: list[object] = value
    if not vals_any:
        return []

    out: list[str] = []
    for v in vals_any:
        if isinstance(v, str):
            out.append(v)
        else:
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
) -> E | None:
    """Parse an enum value from TOML.

    Expected input is a `str` matching one of the Enum values.

    - Missing key -> None
    - Wrong type -> warning + None
    - Unknown enum value -> error + None

    This is intended for schema-level validation (e.g. `[writer].target`).
    """
    raw: TomlValue = table.get(key)
    if raw is None:
        return None

    loc: Final[str] = f"{where}.{key}"
    if not isinstance(raw, str):
        diagnostics.add_warning(
            f"Expected string enum value in {loc}, got {type(raw).__name__}: {raw!r}"
        )
        return None

    try:
        return enum_cls(raw)
    except ValueError:
        allowed: str = ", ".join(str(e.value) for e in enum_cls)
        diagnostics.add_warning(f"Invalid value for {loc}: {raw!r} (allowed: {allowed})")
        return None
