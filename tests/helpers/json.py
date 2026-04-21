# topmark:header:start
#
#   project      : TopMark
#   file         : json.py
#   file_relpath : tests/helpers/json.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for JSON-based CLI tests.

This module provides small utilities to parse and validate JSON output emitted
by TopMark CLI commands. These helpers are intentionally strict and fail-fast:
they assert expected structure and ensure payloads conform to the machine-output
contract.

They are designed for test code only and rely on runtime assertions rather than
permissive recovery.
"""

from __future__ import annotations

import json

from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping


def parse_json_object(output: str) -> dict[str, object]:
    """Parse a JSON object from CLI output.

    This helper is used in tests for commands that emit a single JSON document.
    It validates that the output is valid JSON and that the decoded payload is a
    mapping (object).

    Args:
        output: Raw CLI output string.

    Returns:
        The parsed JSON payload as a `dict[str, object]`.

    Raises:
        AssertionError: If the output is not valid JSON or does not decode to
            an object.
    """
    try:
        payload_obj: object = json.loads(output)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Output is not valid JSON: {exc}\nRAW:\n{output}") from exc

    assert is_mapping(payload_obj), "JSON payload must be an object"
    return as_object_dict(payload_obj)
