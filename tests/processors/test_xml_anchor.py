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
