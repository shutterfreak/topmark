# topmark:header:start
#
#   project      : TopMark
#   file         : test_enum_mixins.py
#   file_relpath : tests/core/test_enum_mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for core enum mixins and parsing helpers."""

from __future__ import annotations

from enum import Enum
from enum import StrEnum
from pathlib import Path

from topmark.core.enum_mixins import EnumIntrospectionMixin
from topmark.core.machine.schemas import MachineDomain
from topmark.core.machine.schemas import normalize_payload
from topmark.core.merge import opt_enum
from topmark.core.typing_guards import get_string_dict_value
from topmark.core.typing_guards import get_string_list_dict_value


class PlainMode(StrEnum):
    """Simple enum used for name lookup tests."""

    ALPHA = "alpha"
    BETA = "beta"


class IntrospectedMode(EnumIntrospectionMixin, StrEnum):
    """Enum using introspection mixin behavior."""

    SHORT = "a"
    LONG = "alphabet"


def test_enum_introspection_value_length_uses_longest_value() -> None:
    """value_length should report the longest value length for the enum class."""
    assert IntrospectedMode.SHORT.value_length == len("alphabet")
    assert IntrospectedMode.LONG.value_length == len("alphabet")


def test_opt_enum_returns_none_for_invalid_enum_value() -> None:
    """Enum extraction should fail open when a mapping contains an unknown value."""
    assert opt_enum({"domain": "missing"}, key="domain", enum_cls=MachineDomain) is None


def test_typing_guards_filter_invalid_mapping_shapes() -> None:
    """Mapping helpers should filter invalid shapes without coercing nested values."""
    mapping: dict[str, object] = {
        "strings": {"keep": "value", "drop": 1, 2: "drop"},
        "lists": {"keep": ["a", "b"], "drop": ["a", 1], 2: ["drop"]},
        "scalar": "not-a-dict",
    }

    assert get_string_dict_value(mapping, "strings") == {"keep": "value"}
    assert get_string_dict_value(mapping, "scalar") == {}
    assert get_string_list_dict_value(mapping, "lists") == {"keep": ["a", "b"]}
    assert get_string_list_dict_value(mapping, "scalar") == {}


def test_normalize_payload_handles_paths_and_non_string_enums() -> None:
    """Machine payload normalization should stabilize paths and non-string enums."""

    class Status(Enum):
        READY = 1

    payload: dict[object, object] = {
        "path": Path("src/topmark/core/constants.py"),
        "status": Status.READY,
    }

    assert normalize_payload(payload) == {
        "path": "src/topmark/core/constants.py",
        "status": "READY",
    }
