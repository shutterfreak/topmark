# topmark:header:start
#
#   project      : TopMark
#   file         : test_getters.py
#   file_relpath : tests/toml/test_getters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for TOML value getter helpers."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pytest

from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.toml.getters import get_bool_value
from topmark.toml.getters import get_bool_value_checked
from topmark.toml.getters import get_bool_value_or_none
from topmark.toml.getters import get_bool_value_or_none_checked
from topmark.toml.getters import get_enum_value_checked
from topmark.toml.getters import get_int_value_or_none_checked
from topmark.toml.getters import get_list_value
from topmark.toml.getters import get_string_list_value_checked
from topmark.toml.getters import get_string_value
from topmark.toml.getters import get_string_value_checked
from topmark.toml.getters import get_string_value_or_none
from topmark.toml.getters import get_string_value_or_none_checked
from topmark.toml.getters import get_table_value

if TYPE_CHECKING:
    from topmark.toml.types import TomlTable


class SampleMode(str, Enum):
    """Small enum used to test checked enum extraction."""

    FAST = "fast"
    SAFE = "safe"


def _warning_messages(diagnostics: MutableDiagnosticLog) -> list[str]:
    """Return warning messages from a diagnostic log."""
    return [item.message for item in diagnostics.items if item.level is DiagnosticLevel.WARNING]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("demo", "demo"),
        (123, "123"),
        (1.5, "1.5"),
        (True, "True"),
    ],
)
def test_get_string_value_returns_strings_and_coerces_scalars(
    value: str | float | bool,
    expected: str,
) -> None:
    """Unchecked string getter should return strings and coerce scalar values."""
    table: TomlTable = {"field": value}

    assert get_string_value(table, "field", default="fallback") == expected


def test_get_string_value_returns_default_for_missing_or_uncoercible_value() -> None:
    """Unchecked string getter should default for missing and non-scalar values."""
    table: TomlTable = {"items": ["a"]}

    assert get_string_value(table, "missing", default="fallback") == "fallback"
    assert get_string_value(table, "items", default="fallback") == "fallback"


def test_get_string_value_or_none_handles_missing_and_uncoercible_value() -> None:
    """Optional unchecked string getter should return None when absent or malformed."""
    table: TomlTable = {"field": 123, "items": ["a"]}

    assert get_string_value_or_none(table, "field") == "123"
    assert get_string_value_or_none(table, "missing") is None
    assert get_string_value_or_none(table, "items") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
    ],
)
def test_get_bool_value_returns_bool_values(value: bool, expected: bool) -> None:
    """Unchecked bool getter should return real booleans."""
    table: TomlTable = {"flag": value}

    assert get_bool_value(table, "flag", default=not expected) is expected


def test_get_bool_value_returns_default_for_missing_or_wrong_type() -> None:
    """Unchecked bool getter should default for missing or non-bool values."""
    table: TomlTable = {"flag": "true"}

    assert get_bool_value(table, "flag", default=True) is True
    assert get_bool_value(table, "missing", default=True) is True


def test_get_bool_value_or_none_handles_missing_and_wrong_type() -> None:
    """Optional unchecked bool getter should return None when absent or malformed."""
    table: TomlTable = {"enabled": False, "count": 1}

    assert get_bool_value_or_none(table, "enabled") is False
    assert get_bool_value_or_none(table, "missing") is None
    assert get_bool_value_or_none(table, "count") is None


def test_get_list_value_returns_shallow_copy() -> None:
    """Unchecked list getter should return a shallow copy of the configured list."""
    original: list[object] = ["src", "tests"]
    table: TomlTable = {"include": ["src", "tests"]}

    result: list[object] = get_list_value(table, "include")

    assert result == original
    assert result is not table["include"]


def test_get_list_value_uses_default_or_empty_list_for_wrong_type() -> None:
    """Unchecked list getter should default for missing or non-list values."""
    table: TomlTable = {"include": "src"}
    default: list[object] = ["fallback"]

    assert get_list_value(table, "include", default=default) == ["fallback"]
    assert get_list_value(table, "missing") == []


def test_get_string_value_checked_returns_default_without_warning_when_missing() -> None:
    """Checked string getter should treat missing values as defaulted, not malformed."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {}

    assert (
        get_string_value_checked(
            table,
            "project",
            where="[header]",
            diagnostics=diagnostics,
            default="Demo",
        )
        == "Demo"
    )
    assert diagnostics.items == []


def test_get_string_value_checked_warns_on_wrong_type() -> None:
    """Checked string getter should not coerce wrong-type values."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"project": 123}

    result: str = get_string_value_checked(
        table,
        "project",
        where="[header]",
        diagnostics=diagnostics,
        default="Demo",
    )

    assert result == "Demo"
    assert _warning_messages(diagnostics) == ["Expected string in [header].project, got int: 123"]


def test_get_string_value_or_none_checked_warns_on_wrong_type() -> None:
    """Checked optional string getter should warn on present wrong-type values."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"license": True}

    assert (
        get_string_value_or_none_checked(
            table,
            "license",
            where="[header]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert _warning_messages(diagnostics) == ["Expected string in [header].license, got bool: True"]


def test_get_bool_value_checked_returns_default_without_warning_when_missing() -> None:
    """Checked bool getter should treat missing values as defaulted, not malformed."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {}

    assert (
        get_bool_value_checked(
            table,
            "root",
            where="[config]",
            diagnostics=diagnostics,
            default=True,
        )
        is True
    )
    assert diagnostics.items == []


def test_get_bool_value_checked_warns_on_wrong_type() -> None:
    """Checked bool getter should not coerce wrong-type values."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"root": 1}

    result: bool = get_bool_value_checked(
        table,
        "root",
        where="[config]",
        diagnostics=diagnostics,
        default=False,
    )

    assert result is False
    assert _warning_messages(diagnostics) == ["Expected bool in [config].root, got int: 1"]


def test_get_bool_value_or_none_checked_warns_on_wrong_type() -> None:
    """Checked optional bool getter should warn on present wrong-type values."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"root": "yes"}

    assert (
        get_bool_value_or_none_checked(
            table,
            "root",
            where="[config]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert _warning_messages(diagnostics) == ["Expected bool in [config].root, got str: yes"]


def test_get_int_value_or_none_checked_accepts_int_but_rejects_bool() -> None:
    """Checked optional int getter should reject bool despite bool being an int subclass."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {
        "count": 3,
        "enabled": True,
        "name": "three",
    }

    assert (
        get_int_value_or_none_checked(
            table,
            "count",
            where="[limits]",
            diagnostics=diagnostics,
        )
        == 3
    )
    assert (
        get_int_value_or_none_checked(
            table,
            "missing",
            where="[limits]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert (
        get_int_value_or_none_checked(
            table,
            "enabled",
            where="[limits]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert (
        get_int_value_or_none_checked(
            table,
            "name",
            where="[limits]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert _warning_messages(diagnostics) == [
        "Expected int in [limits].enabled, got bool: True",
        "Expected int in [limits].name, got str: 'three'",
    ]


def test_get_string_list_value_checked_filters_non_string_items() -> None:
    """Checked string-list getter should retain strings and warn for dropped entries."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"include": ["src", 123, "tests", False]}

    result: list[str] = get_string_list_value_checked(
        table,
        "include",
        where="[files]",
        diagnostics=diagnostics,
    )

    assert result == ["src", "tests"]
    assert _warning_messages(diagnostics) == [
        "Ignoring non-string entry in [files].include: 123",
        "Ignoring non-string entry in [files].include: False",
    ]


def test_get_string_list_value_checked_warns_when_value_is_not_list() -> None:
    """Checked string-list getter should warn when the configured value is scalar."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"include": "src"}

    assert (
        get_string_list_value_checked(
            table,
            "include",
            where="[files]",
            diagnostics=diagnostics,
        )
        == []
    )
    assert _warning_messages(diagnostics) == ["Expected list in [files].include, got str: 'src'"]


def test_get_enum_value_checked_accepts_valid_enum_value() -> None:
    """Checked enum getter should parse valid string enum values."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"mode": "safe"}

    assert (
        get_enum_value_checked(
            table,
            "mode",
            SampleMode,
            where="[config]",
            diagnostics=diagnostics,
        )
        is SampleMode.SAFE
    )
    assert diagnostics.items == []


def test_get_enum_value_checked_warns_on_wrong_type() -> None:
    """Checked enum getter should warn when enum value is not a string."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"mode": True}

    assert (
        get_enum_value_checked(
            table,
            "mode",
            SampleMode,
            where="[config]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert _warning_messages(diagnostics) == [
        "Expected string enum value in [config].mode, got bool: True"
    ]


def test_get_enum_value_checked_warns_on_unknown_value() -> None:
    """Checked enum getter should warn when enum value is outside the allowed set."""
    diagnostics = MutableDiagnosticLog()
    table: TomlTable = {"mode": "turbo"}

    assert (
        get_enum_value_checked(
            table,
            "mode",
            SampleMode,
            where="[config]",
            diagnostics=diagnostics,
        )
        is None
    )
    assert _warning_messages(diagnostics) == [
        "Invalid value for [config].mode: 'turbo' (allowed: fast, safe)"
    ]


def test_get_table_value_returns_table_or_empty_dict() -> None:
    """Table getter should return nested tables and default to an empty dict otherwise."""
    nested: TomlTable = {"project": "Demo"}
    table: TomlTable = {
        "header": nested,
        "file": "not-table",
    }

    assert get_table_value(table, "header") == nested
    assert get_table_value(table, "file") == {}
    assert get_table_value(table, "missing") == {}
