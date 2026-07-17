# topmark:header:start
#
#   project      : TopMark
#   file         : test_xml_anchor.py
#   file_relpath : tests/processors/test_xml_anchor.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Assert XML processor reports NO_LINE_ANCHOR (char-offset strategy)."""

from __future__ import annotations

import re

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.constants import STANDARD_NEWLINE_RE
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.processors.base import NO_LINE_ANCHOR
from topmark.processors.builtins.xml import XmlHeaderProcessor


def test_xml_processor_reports_no_line_anchor() -> None:
    """get_header_insertion_index returns NO_LINE_ANCHOR."""
    p = XmlHeaderProcessor()
    assert p.get_header_insertion_index(["<xml>"]) == NO_LINE_ANCHOR


def test_xml_processor_newline_anchor_regex_is_standard_only() -> None:
    """XML char-offset anchoring must only split on LF/CRLF/CR."""
    text: str = "alpha\u2028beta\x85gamma\u2029delta"

    assert re.search(STANDARD_NEWLINE_RE, text) is None


def test_xml_char_offset_empty_document_is_start() -> None:
    """Empty XML-like documents should use the start-of-file char anchor."""
    processor = XmlHeaderProcessor()

    assert processor.get_header_insertion_char_offset("") == 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\ufeff", 1),
        ("\ufeff \t\r\n", 5),
        (" \t\r\n<root/>", 4),
    ],
)
def test_xml_char_offset_preserves_bom_and_leading_ascii_whitespace(
    text: str,
    expected: int,
) -> None:
    """BOM-only and leading-whitespace inputs anchor after preserved preamble text."""
    assert XmlHeaderProcessor().get_header_insertion_char_offset(text) == expected


@pytest.mark.parametrize("newline", ["\r", "\n", "\r\n"])
def test_xml_char_offset_handles_supported_newline_styles(newline: str) -> None:
    """Declaration and root offsets are character-correct for CR, LF, and CRLF."""
    processor = XmlHeaderProcessor()
    text: str = f'<?xml version="1.0"?>{newline}<root/>'

    assert processor.get_header_insertion_char_offset(text) == text.index("<root/>")


def test_xml_char_offset_nonleading_declaration_is_not_skipped() -> None:
    """A declaration after root content is handled conservatively as body text."""
    processor = XmlHeaderProcessor()
    text: str = "<root/>\n<?xml version='1.0'?>"

    assert processor.get_header_insertion_char_offset(text) == 0


def test_xml_char_offset_unclosed_doctype_stops_at_doctype_start() -> None:
    """Malformed DOCTYPE content is not skipped or split speculatively."""
    processor = XmlHeaderProcessor()
    text: str = '<?xml version="1.0"?>\n<!DOCTYPE root [\n<root/>'

    assert processor.get_header_insertion_char_offset(text) == text.index("<!DOCTYPE")


@pytest.mark.parametrize(
    "doctype",
    [
        '<!DOCTYPE root SYSTEM "urn:example>a">',
        "<!DOCTYPE root [\n  <!ELEMENT root EMPTY>\n]>",
    ],
)
def test_xml_char_offset_skips_complete_doctype_without_stopping_at_inner_gt(
    doctype: str,
) -> None:
    """Quoted and internal-subset greater-than signs do not end the DOCTYPE."""
    processor = XmlHeaderProcessor()
    text = f'<?xml version="1.0"?>\n{doctype}\n<root/>'

    assert processor.get_header_insertion_char_offset(text) == text.index("<root/>")


def test_xml_char_offset_skips_bom_leading_space_decl_and_doctype() -> None:
    """Char-offset anchor should skip BOM, leading whitespace, declaration, and DOCTYPE."""
    processor = XmlHeaderProcessor()
    text = '\ufeff  \n<?xml version="1.0"?>\n<!DOCTYPE note SYSTEM "Note.dtd">\n<note/>\n'

    offset: int | None = processor.get_header_insertion_char_offset(text)

    assert offset == text.index("<note/>")


def test_xml_char_offset_malformed_declaration_returns_conservative_offset() -> None:
    """Malformed XML declarations should return the offset at the declaration start."""
    processor = XmlHeaderProcessor()
    text = '\ufeff  <?xml version="1.0"<root/>'

    assert processor.get_header_insertion_char_offset(text) == text.index("<?xml")


def test_xml_prepare_text_insertion_adds_single_leading_blank_after_prolog() -> None:
    """Text insertion after a line-ended XML prolog should add one leading blank."""
    processor = XmlHeaderProcessor()
    original = '<?xml version="1.0"?>\n<root/>\n'
    offset: int = original.index("<root/>")

    block: str = processor.prepare_header_for_insertion_text(
        original_text=original,
        insert_offset=offset,
        rendered_header_text="<!-- header -->\n",
        newline_style="\n",
    )

    assert block.startswith("\n<!-- header -->\n")
    assert block.endswith("\n\n")


def test_xml_prepare_text_insertion_preserves_crlf_padding() -> None:
    """Text insertion keeps CRLF for both owned separators around the header."""
    processor = XmlHeaderProcessor()
    original = '<?xml version="1.0"?>\r\n<root/>\r\n'
    offset: int = original.index("<root/>")

    block: str = processor.prepare_header_for_insertion_text(
        original_text=original,
        insert_offset=offset,
        rendered_header_text="<!-- header -->\r\n",
        newline_style="\r\n",
    )

    assert block == "\r\n<!-- header -->\r\n\r\n"


def test_xml_prepare_text_insertion_splits_single_line_prolog_with_blank() -> None:
    """Text insertion that splits prolog and root on one line should add two leading newlines."""
    processor = XmlHeaderProcessor()
    original = '<?xml version="1.0"?><root/>'
    offset: int = original.index("<root/>")

    block: str = processor.prepare_header_for_insertion_text(
        original_text=original,
        insert_offset=offset,
        rendered_header_text="<!-- header -->",
        newline_style="\n",
    )

    assert block.startswith("\n\n<!-- header -->\n")
    assert block.endswith("\n\n")


def test_xml_prepare_text_insertion_respects_disabled_trailing_policy() -> None:
    """Text insertion should not add trailing spacer when policy disables it."""
    processor = XmlHeaderProcessor()
    processor.file_type = make_file_type(
        local_key="xml-test",
        namespace="test",
        header_policy=FileTypeHeaderPolicy(ensure_blank_after_header=False),
    )
    original = '<?xml version="1.0"?>\n<root/>\n'
    offset: int = original.index("<root/>")

    block = processor.prepare_header_for_insertion_text(
        original_text=original,
        insert_offset=offset,
        rendered_header_text="<!-- header -->\n",
        newline_style="\n",
    )

    assert block == "\n<!-- header -->\n"


def test_xml_prepare_line_insertion_after_multiline_doctype_adds_leading_blank() -> None:
    """Line insertion should detect a nearby multiline DOCTYPE opener."""
    processor = XmlHeaderProcessor()
    original_lines: list[str] = [
        '<?xml version="1.0"?>\n',
        "<!DOCTYPE root [\n",
        "  <!ELEMENT root EMPTY>\n",
        "]>\n",
        "<root/>\n",
    ]

    lines: list[str] = processor.prepare_header_for_insertion(
        original_lines=original_lines,
        insert_index=4,
        rendered_header_lines=["<!-- header -->\n"],
        newline_style="\n",
    )

    assert lines == ["\n", "<!-- header -->\n", "\n"]


def test_xml_prepare_line_insertion_handles_long_internal_subset() -> None:
    """Line padding recognizes a DOCTYPE opener beyond any fixed look-back window."""
    processor = XmlHeaderProcessor()
    original_lines: list[str] = [
        '<?xml version="1.0"?>\n',
        "<!DOCTYPE root [\n",
        "  <!ELEMENT root EMPTY>\n",
        "  <!ENTITY one '1'>\n",
        "  <!ENTITY two '2'>\n",
        "  <!ENTITY three '3'>\n",
        "  <!ENTITY four '4'>\n",
        "]>\n",
        "<root/>\n",
    ]

    lines: list[str] = processor.prepare_header_for_insertion(
        original_lines=original_lines,
        insert_index=8,
        rendered_header_lines=["<!-- header -->\n"],
        newline_style="\n",
    )

    assert lines == ["\n", "<!-- header -->\n", "\n"]


def test_xml_prepare_line_insertion_at_eof_does_not_add_trailing_spacer() -> None:
    """Line insertion at EOF should not append an unnecessary trailing spacer."""
    processor = XmlHeaderProcessor()
    original_lines: list[str] = ["<root/>\n"]

    lines: list[str] = processor.prepare_header_for_insertion(
        original_lines=original_lines,
        insert_index=1,
        rendered_header_lines=["<!-- header -->\n"],
        newline_style="\n",
    )

    assert lines == ["<!-- header -->\n"]


def test_xml_prepare_line_insertion_respects_disabled_trailing_policy() -> None:
    """Line insertion should respect file-type policy disabling trailing blank lines."""
    processor = XmlHeaderProcessor()
    processor.file_type = make_file_type(
        local_key="xml-test",
        namespace="test",
        header_policy=FileTypeHeaderPolicy(ensure_blank_after_header=False),
    )

    lines: list[str] = processor.prepare_header_for_insertion(
        original_lines=["<root/>\n"],
        insert_index=0,
        rendered_header_lines=["<!-- header -->\n"],
        newline_style="\n",
    )

    assert lines == ["<!-- header -->\n"]
