# topmark:header:start
#
#   project      : TopMark
#   file         : machine.py
#   file_relpath : tests/helpers/machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for machine-readable output tests."""

from __future__ import annotations

import re

from topmark.core.machine.schemas import MachineKey
from topmark.core.machine.schemas import MetaPayload
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping

REQUIRED_META_KEYS: frozenset[str] = frozenset(
    {
        "tool",
        "version",
        "platform",
        "python_version",
        "machine",
    }
)

PYTHON_ENUM_REPR_RE: re.Pattern[str] = re.compile(
    r"(?:<)?(?:[A-Za-z_]\w*\.)+[A-Z][A-Za-z0-9_]*\.[A-Z][A-Za-z0-9_]*",
)
"""Python enum-style representation that must not appear in machine output."""


def machine_meta() -> MetaPayload:
    """Return deterministic metadata for machine serializer tests."""
    return MetaPayload(
        tool="topmark",
        version="test",
        platform="test",
        python_version="3.15.0",
        machine="test-machine",
    )


def assert_machine_meta(
    meta_obj: object,
    *,
    expected_detail_level: str | None = None,
) -> dict[str, object]:
    """Assert shared machine-output metadata and return its mapping.

    Args:
        meta_obj: Candidate metadata object, typically a record's ``meta`` value.
        expected_detail_level: Expected machine ``detail_level`` when emitted.

    Returns:
        The validated metadata mapping.

    Raises:
        AssertionError: If the metadata shape or values are invalid.
    """
    assert is_mapping(meta_obj)
    meta: dict[str, object] = as_object_dict(meta_obj)

    for key in REQUIRED_META_KEYS:
        assert isinstance(meta.get(key), str)

    detail_level_obj: object | None = meta.get("detail_level")
    if detail_level_obj is not None:
        assert isinstance(detail_level_obj, str)
        if expected_detail_level is not None:
            assert detail_level_obj == expected_detail_level

    return meta


def assert_machine_stdout_is_clean(
    output: str,
) -> None:
    """Assert that raw machine output has no presentation or enum-repr leakage.

    Args:
        output: Raw JSON or NDJSON bytes decoded as text by Click's test result.

    Raises:
        AssertionError: If ANSI escapes or a Python enum representation is present.
    """
    assert "\x1b" not in output
    assert PYTHON_ENUM_REPR_RE.search(output) is None


def assert_ndjson_record_envelopes(
    records: list[dict[str, object]],
    *,
    expected_detail_level: str | None = None,
) -> None:
    """Assert the documented envelope shared by all NDJSON records.

    Args:
        records: Parsed NDJSON records in their emitted order.
        expected_detail_level: Expected metadata detail level when emitted.

    Raises:
        AssertionError: If a record lacks its kind, metadata, or payload container.
    """
    assert records
    for record in records:
        kind_obj: object | None = record.get(MachineKey.KIND.value)
        assert isinstance(kind_obj, str)
        assert_machine_meta(
            record.get(MachineKey.META.value),
            expected_detail_level=expected_detail_level,
        )
        assert kind_obj in record
