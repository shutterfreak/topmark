# topmark:header:start
#
#   project      : TopMark
#   file         : test_checks_xml.py
#   file_relpath : tests/filetypes/checks/test_checks_xml.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for XML pre-insert checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.filetypes.checks import xml as xml_checks
from topmark.filetypes.checks.xml import _is_newline_equiv  # pyright: ignore[reportPrivateUsage]
from topmark.filetypes.checks.xml import _offset_to_line_col  # pyright: ignore[reportPrivateUsage]
from topmark.filetypes.checks.xml import xml_can_insert
from topmark.filetypes.model import FileType
from topmark.filetypes.model import InsertCapability
from topmark.filetypes.model import InsertCheckResult

if TYPE_CHECKING:
    from collections.abc import Iterable


class XmlOffsetProcessor:
    """Header-processor view that returns a fixed XML insertion offset."""

    offset: int | None

    def __init__(self, offset: int | None) -> None:
        self.offset = offset

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Return the configured offset."""
        return self.offset


class FailingXmlOffsetProcessor:
    """Header-processor view that raises during offset calculation."""

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Raise a deterministic offset error."""
        raise ValueError("invalid XML prolog")


class XmlPreInsertContext:
    """Minimal XML pre-insert context for checker contract tests."""

    lines: tuple[str, ...]
    newline_style: str
    header_processor: XmlOffsetProcessor | FailingXmlOffsetProcessor | None
    file_type: FileType | None

    def __init__(
        self,
        *,
        lines: Iterable[str],
        header_processor: XmlOffsetProcessor | FailingXmlOffsetProcessor | None,
    ) -> None:
        self.lines = tuple(lines)
        self.newline_style = "\n"
        self.header_processor = header_processor
        self.file_type = None


_USE_DEFAULT_XML_PROCESSOR = object()


def _xml_context(
    lines: Iterable[str],
    *,
    offset: int | None = 0,
    header_processor: XmlOffsetProcessor
    | FailingXmlOffsetProcessor
    | None
    | object = _USE_DEFAULT_XML_PROCESSOR,
) -> XmlPreInsertContext:
    """Build a minimal context for `xml_can_insert()`."""
    processor: XmlOffsetProcessor | FailingXmlOffsetProcessor | None
    if isinstance(header_processor, XmlOffsetProcessor | FailingXmlOffsetProcessor):
        processor = header_processor
    elif header_processor is None:
        processor = None
    else:
        processor = XmlOffsetProcessor(offset)
    return XmlPreInsertContext(lines=lines, header_processor=processor)


def _assert_capability(
    result: InsertCheckResult,
    expected: InsertCapability,
    *,
    reason_contains: str | None = None,
) -> None:
    """Assert the XML checker advisory and optional reason fragment."""
    assert result.get("capability") is expected
    if reason_contains is not None:
        assert reason_contains in result.get("reason", "")
    assert result.get("origin") == "topmark.filetypes.checks.xml.xml_can_insert"


def test_xml_can_insert_requires_xml_processor() -> None:
    """XML insertion fails closed when no XML processor is available."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ["<root/>\n"],
            header_processor=None,
        ),
    )

    _assert_capability(result, InsertCapability.SKIP_OTHER, reason_contains="no XML processor")


@pytest.mark.parametrize("lines", [[], [""], ["\ufeff   \t\r\n"]])
def test_xml_can_insert_rejects_effectively_empty_content(lines: list[str]) -> None:
    """BOM and ASCII-whitespace-only XML has no safe body anchor."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            lines,
        )
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_UNSUPPORTED_CONTENT,
        reason_contains="Empty or whitespace-only XML",
    )


def test_xml_can_insert_rejects_unterminated_xml_declaration() -> None:
    """An XML declaration must be closed before insertion is considered."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"\n'],
        )
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_UNSUPPORTED_CONTENT,
        reason_contains="Unterminated XML declaration",
    )


def test_xml_can_insert_rejects_unterminated_doctype() -> None:
    """A dangling DOCTYPE is treated as unsupported content."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ["<!DOCTYPE root\n"],
        )
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_UNSUPPORTED_CONTENT,
        reason_contains="Unterminated DOCTYPE",
    )


def test_xml_can_insert_fails_closed_when_offset_calculation_raises() -> None:
    """Offset failures from the XML processor should not escape the checker."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"?>\n<root/>\n'],
            header_processor=FailingXmlOffsetProcessor(),
        ),
    )

    _assert_capability(result, InsertCapability.SKIP_OTHER, reason_contains="xml offset error")


def test_xml_can_insert_rejects_missing_offset() -> None:
    """A processor that cannot provide an insertion offset is not insertable."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"?>\n<root/>\n'],
            offset=None,
        ),
    )

    _assert_capability(result, InsertCapability.SKIP_OTHER, reason_contains="no insertion offset")


def test_xml_can_insert_rejects_prolog_only_content() -> None:
    """An EOF insertion offset means there is no XML body to anchor before."""
    line = '<?xml version="1.0"?>\n'
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            [line],
            offset=len(line),
        ),
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_UNSUPPORTED_CONTENT,
        reason_contains="no body",
    )


def test_xml_can_insert_rejects_inline_prolog_and_body_reflow() -> None:
    """Insertion is skipped when it would split an existing physical line."""
    line = '<?xml version="1.0"?><root/>\n'
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            [line],
            offset=line.index("<root"),
        ),
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_IDEMPOTENCE_RISK,
        reason_contains="share a line",
    )


@pytest.mark.parametrize("newline", ["\x85", "\u2028", "\u2029"])
def test_xml_can_insert_rejects_early_non_standard_body_newlines(newline: str) -> None:
    """NEL/LS/PS near the XML body are idempotence risks for insertion."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"?>\n', f"<root>{newline}</root>\n"],
            offset=22,
        ),
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_IDEMPOTENCE_RISK,
        reason_contains="non-standard newline",
    )


def test_xml_can_insert_rejects_disallowed_early_body_control_character() -> None:
    """Disallowed XML 1.0 C0 controls in the early body fail closed."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"?>\n', "<root>\x1e</root>\n"],
            offset=22,
        ),
    )

    _assert_capability(
        result,
        InsertCapability.SKIP_UNSUPPORTED_CONTENT,
        reason_contains="Disallowed control U+001E",
    )


def test_xml_can_insert_accepts_body_on_following_line() -> None:
    """A declaration followed by a normal XML body is safe to insert before."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"?>\n', "<root/>\n"],
            offset=22,
        ),
    )

    _assert_capability(result, InsertCapability.OK)


def test_xml_can_insert_accepts_single_body_line_without_following_slice() -> None:
    """A body that starts on the only line does not require a second slice."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ["<root/>\n"],
            offset=0,
        ),
    )

    _assert_capability(result, InsertCapability.OK)


def test_xml_can_insert_accepts_defensive_empty_body_slice_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A defensive invalid offset mapping does not crash XML insertion checks."""

    def _invalid_line_mapping(lines: list[str], offset: int) -> tuple[int, int]:
        assert lines == ["<root/>\n"]
        assert offset == 0
        return (len(lines), 0)

    monkeypatch.setattr(
        xml_checks,
        "_offset_to_line_col",
        _invalid_line_mapping,
    )

    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ["<root/>\n"],
            offset=0,
        ),
    )

    _assert_capability(result, InsertCapability.OK)


def test_offset_to_line_col_handles_empty_and_past_end_offsets() -> None:
    """Offset mapping clamps empty and past-end offsets for checker callers."""
    assert _offset_to_line_col([], 10) == (0, 0)
    assert _offset_to_line_col(["abc\n", "de"], 10) == (1, 4)


@pytest.mark.parametrize("ch", ["\n", "\r", "\x85", "\u2028", "\u2029"])
def test_is_newline_equiv_accepts_supported_xml_newline_variants(ch: str) -> None:
    """XML checker newline equivalence includes standard and Unicode variants."""
    assert _is_newline_equiv(ch) is True


def test_is_newline_equiv_rejects_non_newline_characters() -> None:
    """Non-newline body content is not treated as a newline equivalent."""
    assert _is_newline_equiv("x") is False


def test_xml_can_insert_accepts_offset_past_end_without_body_slice() -> None:
    """Out-of-range offsets do not crash XML insertion checks."""
    result: InsertCheckResult = xml_can_insert(
        _xml_context(
            ['<?xml version="1.0"?>\n', "<root/>\n"],
            offset=10_000,
        ),
    )

    _assert_capability(result, InsertCapability.OK)
