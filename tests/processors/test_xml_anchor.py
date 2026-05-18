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

from topmark.core.constants import STANDARD_NEWLINE_RE
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
