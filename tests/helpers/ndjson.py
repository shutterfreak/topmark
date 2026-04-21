# topmark:header:start
#
#   project      : TopMark
#   file         : ndjson.py
#   file_relpath : tests/helpers/ndjson.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for NDJSON-based CLI tests.

This module provides small utilities to parse and validate NDJSON output
emitted by TopMark CLI commands. These helpers are intentionally strict and
fail-fast: they assert expected structure (e.g., exactly one record when a
single-record helper is used) and ensure payloads conform to the machine-output
contract.

They are designed for test code only and rely on runtime assertions rather
than defensive error handling.
"""

from __future__ import annotations

import json

from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping


def parse_ndjson_records(output: str) -> list[dict[str, object]]:
    """Parse all non-empty NDJSON records from CLI output.

    This helper is used in tests for commands that emit multi-record NDJSON
    streams (for example `topmark config check`). It validates that every
    non-empty output line is valid JSON and that each parsed payload is a
    mapping (object).

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

    This helper is used in tests for commands that emit a single NDJSON
    record (e.g., `topmark version`). It validates that:
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
