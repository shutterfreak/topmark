# topmark:header:start
#
#   project      : TopMark
#   file         : io.py
#   file_relpath : src/topmark/config/io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Lightweight TOML I/O helpers for TopMark configuration.

This module centralizes **pure** helpers for reading and writing TOML used by
TopMark's configuration layer. Keeping these utilities separate avoids import
cycles and keeps the model classes small and focused.

Design goals:
    * Minimal side effects: functions **do not** mutate configuration objects.
    * Clear typing: public helpers use small aliases (``TomlTable``, ``TomlTableMap``)
      and TypeGuards where possible to help Pyright catch mistakes.
    * Reusability: functions are used by both CLI and API paths.

Typical flow:
    1. Load defaults from the packaged resource (``load_defaults_dict``).
    2. Load project/user TOML files (``load_toml_dict``).
    3. Normalize and inspect values using typed helpers
       (``get_table_value``, ``get_string_value``, etc.).
    4. Serialize back to TOML when needed (``to_toml``).
    5. Optionally wrap a TOML document under a dotted section using
       nest_toml_under_section (e.g., when generating pyproject.toml blocks).

Notes:
    - Use of `tomlkit` is liminted to nest_toml_under_section() which is used to preserve
      comments and white space in the existing TOML config document. This helper is used
      for converting a topmark.toml file for inclusion into pyproject.toml.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Final, TypeGuard, TypeVar, cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError
from tomlkit.items import Item, Key, Table

from topmark.config.logging import get_logger
from topmark.constants import (
    DEFAULT_TOML_CONFIG_NAME,
    DEFAULT_TOML_CONFIG_PACKAGE,
)

if TYPE_CHECKING:
    import sys
    from _collections_abc import dict_items

    from tomlkit.container import Container

    from topmark.core.diagnostics import DiagnosticLog

    if sys.version_info >= (3, 14):
        # Python 3.14+: Traversable moved here
        from importlib.resources.abc import Traversable
    else:
        # Python <=3.13
        from importlib.abc import Traversable

    from pathlib import Path

    from topmark.config.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)

E = TypeVar("E", bound=Enum)
TomlTable = dict[str, Any]
TomlTableMap = dict[str, TomlTable]

# Alias for items in tomlkit's document body, matching the type used in stubs.
# At runtime, the second element may be any Item subclass (including comments,
# whitespace, and containers), but the stubs treat them uniformly as Item.
TomlkitBodyItem = tuple[Key | None, Item]


__all__: list[str] = [
    "TomlTable",
    "TomlTableMap",
    "as_toml_table",
    "as_toml_table_map",
    "clean_toml",
    "get_bool_value",
    "get_bool_value_checked",
    "get_bool_value_or_none",
    "get_bool_value_or_none_checked",
    "get_enum_value_checked",
    "get_int_value_or_none_checked",
    "get_list_value",
    "get_string_list_value_checked",
    "get_string_value",
    "get_string_value_checked",
    "get_string_value_or_none",
    "get_string_value_or_none_checked",
    "get_table_value",
    "is_any_list",
    "is_toml_table",
    "load_defaults_dict",
    "load_toml_dict",
    "to_toml",
]


def as_toml_table(obj: object) -> TomlTable | None:
    """Return the object as a TOML table when possible.

    A TOML table is represented as ``dict[str, Any]`` in this module.

    Args:
        obj (object): Arbitrary object obtained from parsed TOML.

    Returns:
        TomlTable | None: ``obj`` cast to ``TomlTable`` when it is a ``dict``,
        otherwise ``None``.
    """
    if is_toml_table(obj):
        return obj

    logger.debug("Not a TOML table: %r", obj)
    return None


def as_toml_table_map(obj: object) -> TomlTableMap:
    """Return a mapping of string keys to TOML subtables.

    This helper is useful for normalizing nested sections like ``[policy_by_type]``
    where each value must itself be a TOML table.

    Args:
        obj (object): Arbitrary object obtained from parsed TOML.

    Returns:
        TomlTableMap: A mapping with only ``str -> TomlTable`` entries. Non‑matching
        items are silently dropped.
    """
    out: TomlTableMap = {}
    if isinstance(obj, dict):
        obj_dict: TomlTable = cast("TomlTable", obj)  # narrow for Pyright
        for k, v in obj_dict.items():
            if isinstance(v, dict):
                out[k] = v
            else:
                logger.debug("Ignoring non-dict entry for key %s: %r", k, v)
    return out


def is_toml_table(val: Any) -> TypeGuard[TomlTable]:
    """Type guard for a TOML table‑like mapping.

    Args:
        val (Any): Value to test.

    Returns:
        TypeGuard[TomlTable]: ``True`` if ``val`` is a ``dict[str, Any]``.
    """
    return isinstance(val, dict)


def is_any_list(val: Any) -> TypeGuard[list[Any]]:
    """Type guard for a generic list value.

    Checks only that the value is a ``list``; does not validate item types.

    Args:
        val (Any): Value to test.

    Returns:
        TypeGuard[list[Any]]: True if val is a list.
    """
    return isinstance(val, list)


# Helpers
def get_table_value(table: TomlTable, key: str) -> TomlTable:
    """Extract a sub-table from a TOML table.

    Returns a new empty dict if the sub-table is missing or not a mapping.

    Args:
        table (TomlTable): Parent table mapping.
        key (str): Sub-table key.

    Returns:
        TomlTable: The sub-table if present and a mapping, otherwise an empty dict.
    """
    # Safely extract a sub-table (dict) from the TOML data
    value: Any | None = table.get(key)
    return value if is_toml_table(value) else {}


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


# --- Explicit *checked* helpers for schema/shape validation ---


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
    vals_any: list[Any] = get_list_value(table, key)
    if not vals_any:
        return []

    loc: Final[str] = f"{where}.{key}"

    out: list[str] = []

    for v in vals_any:
        if isinstance(v, str):
            out.append(v)
        else:
            logger.warning("Ignoring non-string entry in %s: %r", loc, v)
            diagnostics.add_warning(f"Ignoring non-string entry in {loc}: {v!r}")

    return out


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
        allowed: str = ", ".join(str(e.value) for e in enum_cls)  # type: ignore[attr-defined]
        logger.warning("Invalid value for %s: %r (allowed: %s)", loc, raw, allowed)
        diagnostics.add_warning(f"Invalid value for {loc}: {raw!r} (allowed: {allowed})")
        return None


def load_defaults_dict() -> TomlTable:
    """Return the packaged default configuration as a Python dict.

    Reads the bundled TOML resource from the ``topmark.config`` package using
    ``importlib.resources.files`` and parses it into a dictionary.

    Returns:
        TomlTable: The parsed default configuration.

    Raises:
        RuntimeError: If the bundled default config resource cannot be read or
            parsed as TOML.
    """
    resource: Traversable = files(DEFAULT_TOML_CONFIG_PACKAGE).joinpath(DEFAULT_TOML_CONFIG_NAME)
    logger.debug("Loading defaults from package resource: %s", resource)
    try:
        text: str = resource.read_text(encoding="utf8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot read bundled default config {DEFAULT_TOML_CONFIG_PACKAGE!r}/"
            f"{DEFAULT_TOML_CONFIG_NAME!r}: {exc}"
        ) from exc

    try:
        doc: tomlkit.TOMLDocument = tomlkit.parse(text)
        data_any: Any = doc.unwrap()
        if not isinstance(data_any, dict):
            raise RuntimeError(
                f"Bundled default config {DEFAULT_TOML_CONFIG_PACKAGE!r}/"
                f"{DEFAULT_TOML_CONFIG_NAME!r} did not parse to a table."
            )
        return cast("TomlTable", data_any)
    except TomlkitParseError as exc:
        raise RuntimeError(
            f"Bundled default config {DEFAULT_TOML_CONFIG_PACKAGE!r}/"
            f"{DEFAULT_TOML_CONFIG_NAME!r} is invalid TOML: {exc}"
        ) from exc


def load_toml_dict(path: Path) -> TomlTable:
    """Load and parse a TOML file from the filesystem.

    Args:
        path (Path): Path to a TOML document (e.g., ``topmark.toml`` or
            ``pyproject.toml``).

    Returns:
        TomlTable: The parsed TOML content.

    Notes:
        - Errors are logged and an empty dict is returned on failure.
        - Encoding is assumed to be UTF-8.
    """
    try:
        text: str = path.read_text(encoding="utf-8")
        doc: tomlkit.TOMLDocument = tomlkit.parse(text)
        data_any: Any = doc.unwrap()
        return cast("TomlTable", data_any) if isinstance(data_any, dict) else {}
    except OSError as e:
        logger.error("Error loading TOML from %s: %s", path, e)
        return {}
    except TomlkitParseError as e:
        logger.error("Error decoding TOML from %s: %s", path, e)
        return {}
    except Exception as e:
        logger.error("Unknown error while reading TOML from %s: %s", path, e)
        return {}


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


def _tomlkit_dumps(data: TomlTable) -> str:
    """Typed wrapper around tomlkit.dumps() for strict type checking."""
    cleaned: Any = _strip_none_for_toml(data)
    # tomlkit expects a Mapping; tomlkit itself is treated as untyped here.
    return cast("str", cast("Any", tomlkit).dumps(cast("Mapping[str, Any]", cleaned)))


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


def to_toml(toml_dict: TomlTable) -> str:
    """Serialize a TOML mapping to a string.

    Args:
        toml_dict (TomlTable): TOML mapping to render.

    Returns:
        str: The rendered TOML document as a string.
    """
    return _tomlkit_dumps(toml_dict)


def nest_toml_under_section(toml_doc: str, section_keys: str) -> str:
    r"""Return a new TOML document nested under a dotted section path.

    This helper uses tomlkit to *losslessly* wrap an existing TOML document
    under a nested section, for example:

        nest_toml_under_section("a = 1\\n", "tool.topmark")

    yields a document equivalent to:

        [tool.topmark]
        a = 1

    Comments and whitespace from the original document are preserved because
    tomlkit nodes are re-used when constructing the nested table. This version
    preserves both leading preamble and trailing postamble content.

    Args:
        toml_doc (str): Original TOML document to nest.
        section_keys (str): Dotted section path such as ``"tool.topmark"``.
            Empty segments (e.g., ``"tool..topmark"``) are not allowed.

    Returns:
        str: A new TOML document where the original content lives under the
        final section table (e.g., ``[tool.topmark]``).

    Raises:
        ValueError: If ``section_keys`` is empty or only contains dots.
        RuntimeError: If the TOML document cannot be parsed or if an existing
            key along the path is not a table, making nesting impossible.
    """
    try:
        # 1. Parse the existing document losslessly
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_doc)
    except TomlkitParseError as exc:
        raise RuntimeError(f"Error parsing TOML document: {exc}") from exc

    # 2. Identify the content slices: preamble (leading unkeyed items) and postamble
    # (trailing unkeyed items). We find the indices of the first and last items that have
    # a key (i.e., not a comment/whitespace entry).
    start_index: int = 0
    end_index: int = -1  # Index of the last keyed item. -1 means no keyed items found.

    # Find start_index (the index of the first item with a key)
    for i, (key, _) in enumerate(doc.body):
        if key is not None:
            start_index = i
            break

    # Find end_index (the index of the last item with a key)
    # We iterate backward to find the last occurrence efficiently.
    for i in range(len(doc.body) - 1, -1, -1):
        key, _ = doc.body[i]
        if key is not None:
            end_index = i
            break

    # Preamble slice: All items before the first keyed item.
    preamble_items: list[TomlkitBodyItem] = doc.body[0:start_index]

    # Postamble slice: All items after the last keyed item.
    # If end_index is -1 (file is all comments/whitespace), end_index + 1 is 0,
    # so doc.body[0:] is the entire body, which is correct for transfer.
    postamble_items: list[TomlkitBodyItem] = doc.body[end_index + 1 :]

    # Split and validate the section path
    keys: list[str] = [k for k in section_keys.split(".") if k]
    if not keys:
        raise ValueError("section_keys must contain at least one non-empty component")

    # 3. Create the wrapper document and prepend the preamble
    new_doc: tomlkit.TOMLDocument = tomlkit.document()

    # Prepend the captured preamble items to the new document's body.
    # We use `cast` to satisfy the type checker by asserting that the list contents
    # conform to the expected types (Key | None, Item).
    new_doc.body.extend(preamble_items)

    # 4. Build nested tables for the full section path
    current_level: tomlkit.TOMLDocument | Table = new_doc

    # Recursively build nested tables for "tool.topmark"
    for key in keys:
        # Ensure a table exists at this level for the key
        if key not in current_level:
            # Both TOMLDocument and Table support `.add`
            current_level.add(key, tomlkit.table())

        # Descend into the nested table; validate the type for Pyright and correctness
        next_level: Item | Container = current_level[key]
        if not isinstance(next_level, Table):
            raise RuntimeError(
                f"Cannot nest configuration under [{section_keys}]: "
                f"intermediate key [{key}] is not a table."
            )
        current_level = next_level

    # 5. Attach the original document's content inside the final table
    # At this point, current_level is the Table for the last key in section_keys.
    assert isinstance(current_level, Table)

    # doc.items() extracts only the key-value pairs (the actual content),
    # preserving item-level trivia (inline comments, etc.).
    items: dict_items[str, Item | Container] = cast(
        "dict_items[str, Item | Container]", doc.items()
    )
    for item_key, item_value in items:
        # The type checker is now happy due to the explicit cast
        current_level.add(item_key, item_value)

    # 6. Append the postamble to the new document's body, *after* all keyed content.
    # The postamble elements will appear after the newly created section table.
    new_doc.body.extend(postamble_items)

    # 7. Return the wrapped TOML as a string
    # Use as_string() to get the full formatted output of the Document object
    return new_doc.as_string()
