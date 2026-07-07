# topmark:header:start
#
#   project      : TopMark
#   file         : test_checks_json_like.py
#   file_relpath : tests/filetypes/checks/test_checks_json_like.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for JSON-like pre-insert checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.filetypes.checks.json_like import json_like_can_insert
from topmark.filetypes.model import FileType
from topmark.filetypes.model import InsertCapability
from topmark.filetypes.model import InsertCheckResult

if TYPE_CHECKING:
    from collections.abc import Iterable


class JsonLikePreInsertContext:
    """Minimal JSON-like pre-insert context for checker contract tests."""

    lines: tuple[str, ...]
    newline_style: str
    header_processor: None
    file_type: FileType | None

    def __init__(
        self,
        *,
        lines: Iterable[str],
        file_type: FileType | None,
    ) -> None:
        self.lines = tuple(lines)
        self.newline_style = "\n"
        self.header_processor = None
        self.file_type = file_type


def _json_like_context(
    lines: Iterable[str],
    *,
    local_key: str | None = "json-as-jsonc",
) -> JsonLikePreInsertContext:
    """Build a minimal context for `json_like_can_insert()`."""
    file_type: FileType | None = None
    if local_key is not None:
        file_type = make_file_type(local_key=local_key)
    return JsonLikePreInsertContext(lines=lines, file_type=file_type)


def _assert_capability(
    result: InsertCheckResult,
    expected: InsertCapability,
    *,
    reason_contains: str | None = None,
) -> None:
    """Assert the JSON-like checker advisory and optional reason fragment."""
    assert result.get("capability") is expected
    if reason_contains is not None:
        assert reason_contains in result.get("reason", "")
    assert result.get("origin") == "topmark.filetypes.checks.json_like.json_like_can_insert"


@pytest.mark.parametrize("local_key", [None, "json", "jsonc", "python"])
def test_json_like_can_insert_allows_non_json_as_jsonc_types(
    local_key: str | None,
) -> None:
    """The JSON promotion policy only applies to the json-as-jsonc file type."""
    result: InsertCheckResult = json_like_can_insert(
        _json_like_context(["{}\n"], local_key=local_key),
    )

    _assert_capability(result, InsertCapability.OK)


def test_json_like_can_insert_rejects_plain_json_without_promotion() -> None:
    """Plain JSON is not promoted to JSONC unless comments or policy allow it."""
    result: InsertCheckResult = json_like_can_insert(
        _json_like_context(["{\n", '  "name": "topmark"\n', "}\n"]),
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_POLICY,
        reason_contains="promotion to JSONC is disabled",
    )


def test_json_like_can_insert_allows_explicit_jsonc_promotion() -> None:
    """Explicit promotion policy allows comments to be inserted into plain JSON."""
    result: InsertCheckResult = json_like_can_insert(
        _json_like_context(["{}\n"]),
        allow_promote=True,
    )

    _assert_capability(result, InsertCapability.OK)


@pytest.mark.parametrize(
    "lines",
    [
        ["// existing JSONC comment\n", "{ }\n"],
        ["/* existing JSONC block comment */\n", "{ }\n"],
    ],
)
def test_json_like_can_insert_allows_existing_non_topmark_comments(
    lines: list[str],
) -> None:
    """Existing non-TopMark comments indicate that the file is already JSONC."""
    result: InsertCheckResult = json_like_can_insert(_json_like_context(lines))

    _assert_capability(result, InsertCapability.OK)


@pytest.mark.parametrize(
    "lines",
    [
        ["// ", TOPMARK_START_MARKER, "\n", "{}\n"],
        ["/* ", TOPMARK_END_MARKER, " */\n", "{}\n"],
    ],
)
def test_json_like_can_insert_ignores_topmark_comments_for_jsonc_detection(
    lines: list[str],
) -> None:
    """TopMark's own markers do not count as user-authored JSONC comments."""
    result: InsertCheckResult = json_like_can_insert(_json_like_context(lines))

    _assert_capability(
        result,
        InsertCapability.SKIP_POLICY,
        reason_contains="promotion to JSONC is disabled",
    )
