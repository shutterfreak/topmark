# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/io/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TOML I/O helpers for TopMark configuration.

This package centralizes **pure** helpers for reading, validating, and writing TOML
used by TopMark's configuration layer. Keeping these utilities separate helps avoid
import cycles and keeps the model classes small and focused.

Design goals:
    * Minimal side effects: functions **do not** mutate configuration objects.
    * Clear typing: public helpers use small aliases (``TomlTable``, ``TomlTableMap``)
      and TypeGuards where possible to help Pyright catch mistakes.
    * Reusability: helpers are used by both CLI and API paths.

TOML parsing/formatting:
    TopMark uses `tomlkit` (not `toml`) for parsing and rendering.

    - `load_toml_dict()` parses on-disk TOML using tomlkit and returns plain dicts.
    - `to_toml()` renders using tomlkit (after stripping TOML-incompatible values like `None`).
    - `nest_toml_under_section()` performs *lossless* AST surgery using tomlkit so that
      comments and whitespace are preserved when nesting under a dotted section path.

Typical flow:
    1. Load defaults from the packaged resource (``load_defaults_dict``).
    2. Load project/user TOML files (``load_toml_dict``).
    3. Read values with typed getters (unchecked or checked variants).
    4. Serialize back to TOML when needed (``to_toml``).
    5. Optionally wrap a TOML document under a dotted section using
       ``nest_toml_under_section`` (e.g., when generating pyproject.toml blocks).

Notes:
    - We use `tomlkit` instead of other TOML libraries since ``nest_toml_under_section``
      preserves comments and white space in the existing TOML config document.
      This helper is used for converting a topmark.toml file for inclusion into pyproject.toml.
    - No other TOML packages are required, eventhough ``tomllib`` ship with Python 3.11+.
"""

from __future__ import annotations

from .getters import (
    get_bool_value,
    get_bool_value_checked,
    get_bool_value_or_none,
    get_bool_value_or_none_checked,
    get_enum_value_checked,
    get_int_value_or_none_checked,
    get_list_value,
    get_string_list_value_checked,
    get_string_value,
    get_string_value_checked,
    get_string_value_or_none,
    get_string_value_or_none_checked,
)
from .guards import (
    as_toml_table,
    as_toml_table_map,
    get_table_value,
    is_any_list,
    is_str_list,
    is_toml_table,
    is_tomlkit_table,
)
from .loaders import (
    load_defaults_dict,
    load_toml_dict,
)
from .render import clean_toml, to_toml
from .surgery import nest_toml_under_section
from .types import TomlTable, TomlTableMap

# --- Exported symbols ---

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
    "is_str_list",
    "is_toml_table",
    "is_tomlkit_table",
    "load_defaults_dict",
    "load_toml_dict",
    "nest_toml_under_section",
    "to_toml",
]
