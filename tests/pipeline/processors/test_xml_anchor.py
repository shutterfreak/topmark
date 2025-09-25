# topmark:header:start
#
#   project      : TopMark
#   file         : test_xml_anchor.py
#   file_relpath : tests/pipeline/processors/test_xml_anchor.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Assert XML processor reports NO_LINE_ANCHOR (char-offset strategy)."""

from __future__ import annotations

from topmark.pipeline.processors.base import NO_LINE_ANCHOR
from topmark.pipeline.processors.xml import XmlHeaderProcessor


def test_xml_processor_reports_no_line_anchor() -> None:
    """get_header_insertion_index returns NO_LINE_ANCHOR."""
    p = XmlHeaderProcessor()
    assert p.get_header_insertion_index(["<xml>"]) == NO_LINE_ANCHOR
