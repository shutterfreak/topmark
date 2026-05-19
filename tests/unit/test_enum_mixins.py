# topmark:header:start
#
#   project      : TopMark
#   file         : test_enum_mixins.py
#   file_relpath : tests/unit/test_enum_mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for core enum mixins and parsing helpers."""

from __future__ import annotations

from enum import Enum

import pytest

from topmark.core.enum_mixins import EnumIntrospectionMixin
from topmark.core.enum_mixins import KeyedStrEnum
from topmark.core.enum_mixins import enum_from_name


class PlainMode(str, Enum):
    """Simple enum used for name lookup tests."""

    ALPHA = "alpha"
    BETA = "beta"


class IntrospectedMode(EnumIntrospectionMixin, str, Enum):
    """Enum using introspection mixin behavior."""

    SHORT = "a"
    LONG = "alphabet"


class OutputTarget(KeyedStrEnum):
    """Enum using stable keys, labels, and aliases."""

    FILE = ("file", "Write to file", ("filesystem", "fs"))
    STDOUT = ("stdout", "Write to STDOUT", ("standard-output", "standard output"))


def test_enum_from_name_returns_none_for_none_key() -> None:
    """Name lookup should fail open for missing input."""
    assert enum_from_name(PlainMode, None) is None


def test_enum_from_name_matches_exact_member_name() -> None:
    """Name lookup should match exact enum member names."""
    assert enum_from_name(PlainMode, "ALPHA") is PlainMode.ALPHA


def test_enum_from_name_is_case_sensitive_by_default() -> None:
    """Name lookup should be case-sensitive unless explicitly requested."""
    assert enum_from_name(PlainMode, "alpha") is None


def test_enum_from_name_supports_case_insensitive_lookup() -> None:
    """Name lookup should support uppercase normalization when requested."""
    assert enum_from_name(PlainMode, "alpha", case_insensitive=True) is PlainMode.ALPHA


def test_enum_from_name_returns_none_for_unknown_member() -> None:
    """Name lookup should return None for unknown member names."""
    assert enum_from_name(PlainMode, "GAMMA") is None


def test_enum_introspection_value_length_uses_longest_value() -> None:
    """value_length should report the longest value length for the enum class."""
    assert IntrospectedMode.SHORT.value_length == len("alphabet")
    assert IntrospectedMode.LONG.value_length == len("alphabet")


def test_keyed_str_enum_exposes_value_key_label_and_aliases() -> None:
    """KeyedStrEnum should expose machine value, identity key, and metadata."""
    assert OutputTarget.FILE.value == "file"
    assert OutputTarget.FILE.key == "OutputTarget.FILE"
    assert str(OutputTarget.FILE) == "OutputTarget.FILE"
    assert OutputTarget.FILE.label == "Write to file"
    assert OutputTarget.FILE.aliases == ("filesystem", "fs")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("file", OutputTarget.FILE),
        ("FILE", OutputTarget.FILE),
        ("filesystem", OutputTarget.FILE),
        ("fs", OutputTarget.FILE),
        ("stdout", OutputTarget.STDOUT),
        ("STDOUT", OutputTarget.STDOUT),
        ("standard-output", OutputTarget.STDOUT),
        ("standard output", OutputTarget.STDOUT),
        (" standard output ", OutputTarget.STDOUT),
        ("missing", None),
    ],
)
def test_keyed_str_enum_parse_matches_keys_names_aliases_and_normalized_tokens(
    raw: str | None,
    expected: OutputTarget | None,
) -> None:
    """parse() should match values, names, aliases, normalized tokens, and misses."""
    assert OutputTarget.parse(raw) is expected
