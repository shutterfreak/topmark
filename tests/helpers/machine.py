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
