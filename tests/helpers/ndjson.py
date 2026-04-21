# topmark:header:start
#
#   project      : TopMark
#   file         : ndjson.py
#   file_relpath : tests/helpers/ndjson.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for NDJSON-based CLI machine-output tests.

This module provides small, strict helpers for parsing and validating NDJSON
output emitted by TopMark CLI commands. The helpers are intentionally narrow in
scope: they decode NDJSON lines, assert basic record structure, and provide a
few convenience accessors used by machine-contract tests.

They are designed for test code only and favor fail-fast assertions over
permissive recovery or defensive error handling.

The helpers are generic enough for any NDJSON-emitting command, while some of
them are especially convenient for record-oriented machine outputs that follow
TopMark's canonical ``kind`` + ``meta`` + payload-container pattern.
"""

from __future__ import annotations

import json

from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping

REQUIRED_META_KEYS: frozenset[str] = frozenset({"tool", "version", "platform"})


def parse_ndjson_records(output: str) -> list[dict[str, object]]:
    """Parse all non-empty NDJSON records from CLI output.

    This helper is used in tests for commands that emit multi-record NDJSON
    streams. It validates that every non-empty output line is valid JSON and
    that each parsed payload is a mapping (object).

    Args:
        output: Raw CLI output string.

    Returns:
        The parsed NDJSON records as `list[dict[str, object]]`.

    Raises:
        AssertionError: If any non-empty output line is not valid JSON or does
            not decode to an object.
    """
    lines: list[str] = [line for line in output.splitlines() if line.strip()]
    records: list[dict[str, object]] = []
    for line in lines:
        try:
            payload: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"Output is not valid NDJSON: {exc}\nRAW:\n{output}") from exc

        assert is_mapping(payload), "NDJSON payload must be an object"
        records.append(as_object_dict(payload))

    return records


def parse_single_ndjson_record(output: str) -> dict[str, object]:
    """Parse exactly one NDJSON record from CLI output.

    This helper is used in tests for commands that emit exactly one NDJSON
    record. It validates that:
    - the output contains exactly one non-empty line
    - the line is valid JSON
    - the parsed payload is a mapping (object)

    Args:
        output: Raw CLI output string.

    Returns:
        The parsed NDJSON record as a `dict[str, object]`.

    Raises:
        AssertionError: If the output does not contain exactly one record,
            is not valid JSON, or is not an object.
    """
    lines: list[str] = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 1, f"Expected exactly one NDJSON record, got {len(lines)}: {lines!r}"

    try:
        payload: object = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Output is not valid NDJSON: {exc}\nRAW:\n{output}") from exc

    assert is_mapping(payload), "NDJSON payload must be an object"
    return as_object_dict(payload)


def record_payload(record: dict[str, object]) -> dict[str, object]:
    """Return the mapping payload stored under a record's ``kind`` key.

    This is most useful for TopMark NDJSON record shapes of the form:
    ``{"kind": "...", "meta": {...}, "<kind>": {...}}``.

    Args:
        record: Parsed NDJSON record object.

    Returns:
        The mapping payload stored under the key named by ``record["kind"]``.

    Raises:
        AssertionError: If the record is missing a string ``kind`` field or if
            the payload stored under that key is not a mapping.
    """
    kind_obj: object | None = record.get("kind")
    assert isinstance(kind_obj, str)
    payload_obj: object | None = record.get(kind_obj)
    assert is_mapping(payload_obj)
    return as_object_dict(payload_obj)


def record_kinds(records: list[dict[str, object]]) -> list[str]:
    """Return record ``kind`` values in their original emitted order.

    Args:
        records: Parsed NDJSON record objects.

    Returns:
        A list of ``kind`` field values preserving the original stream order.

    Raises:
        AssertionError: If any record is missing a string ``kind`` field.
    """
    kinds: list[str] = []
    for record in records:
        kind_obj: object | None = record.get("kind")
        assert isinstance(kind_obj, str), "NDJSON record must contain a string 'kind' field"
        kinds.append(kind_obj)
    return kinds


def assert_ndjson_meta(
    meta_obj: object,
    *,
    expected_detail_level: str | None = None,
) -> dict[str, object]:
    """Assert common TopMark machine-output metadata for an NDJSON record.

    This helper validates the standard machine metadata fields currently used by
    TopMark's NDJSON-emitting command surfaces and returns the normalized
    metadata mapping for any additional assertions in the calling test.

    The baseline NDJSON metadata contract requires ``tool``, ``version``, and
    ``platform``. Some command surfaces also emit ``detail_level``; when an
    expected detail level is supplied, this helper validates it only if the
    field is present.

    Args:
        meta_obj: Candidate metadata object, typically ``record["meta"]``.
        expected_detail_level: Expected machine ``detail_level`` value when that
            field is emitted by the command surface.

    Returns:
        The validated metadata mapping.

    Raises:
        AssertionError: If the metadata object is not a mapping, if required
            baseline fields are missing, or if a present ``detail_level`` does
            not match the expected value.
    """
    assert is_mapping(meta_obj)

    meta: dict[str, object] = as_object_dict(meta_obj)

    for key in REQUIRED_META_KEYS:
        assert key in meta
        assert isinstance(meta[key], str)

    detail_level_obj: object | None = meta.get("detail_level")
    if detail_level_obj is not None:
        assert isinstance(detail_level_obj, str)
        if expected_detail_level is not None:
            assert detail_level_obj == expected_detail_level

    return meta
