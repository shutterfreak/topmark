# topmark:header:start
#
#   project      : TopMark
#   file         : test_mixins.py
#   file_relpath : tests/pipeline/processors/test_mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for processor mixins (line-based and positional)."""

from __future__ import annotations

from topmark.pipeline.processors.mixins import (
    LineCommentMixin,
    XmlPositionalMixin,
)


class _LineProc(LineCommentMixin):
    line_prefix = "# "


def test_line_is_header_line() -> None:
    """Detect header line by prefix."""
    p = _LineProc()
    assert p.is_header_line("# hello")
    assert not p.is_header_line("hello # world")
    assert not p.is_header_line("hello")


def test_line_strip_prefix() -> None:
    """Strip only one leading prefix."""
    p = _LineProc()
    assert p.strip_line_prefix("# a") == "a"
    assert p.strip_line_prefix("# # b") == "# b"
    assert p.strip_line_prefix("raw") == "raw"


def test_line_render_header_line() -> None:
    """Render line with prefix (no suffix by default)."""
    p = _LineProc()
    assert p.render_header_line("title") == "# title"


def test_shebang_skip_without_bom() -> None:
    """Insertion index skips shebang only."""
    p = _LineProc()
    lines: list[str] = ["#!/usr/bin/env python3", "print(42)"]
    assert p.find_insertion_index(lines) == 1


class _Xml(XmlPositionalMixin):
    pass


def test_xml_insertion_after_decl_and_doctype() -> None:
    """XML insertion index sits after XML decl and DOCTYPE."""
    x = _Xml()
    lines: list[str] = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        "<!DOCTYPE note SYSTEM 'Note.dtd'>",
        "<note>",
    ]
    assert x.find_xml_insertion_index(lines) == 2


def test_xml_insertion_with_bom_only() -> None:
    """XML insertion index skips just the BOM when present."""
    bom = "\ufeff"
    x = _Xml()
    lines: list[str] = [bom + "<note>", "<to>Tove</to>"]
    assert x.find_xml_insertion_index(lines) == 1


def test_xml_declaration_predicate() -> None:
    """Detect XML declaration line."""
    x = _Xml()
    assert x.is_xml_declaration("<?xml version='1.0'?>")
    assert not x.is_xml_declaration("<note>")


def test_doctype_predicate() -> None:
    """Detect DOCTYPE declaration line."""
    x = _Xml()
    assert x.is_doctype_declaration("<!DOCTYPE html>")
    assert not x.is_doctype_declaration("<html>")


def test_line_mixin_respects_no_shebang_policy() -> None:
    """Do not skip shebang when policy.supports_shebang is False."""
    from topmark.filetypes.base import FileType
    from topmark.filetypes.policy import FileTypeHeaderPolicy
    from topmark.pipeline.processors.mixins import LineCommentMixin

    class _P(LineCommentMixin):
        line_prefix = "# "

    p = _P()
    p.file_type = FileType(  # type: ignore[attr-defined]
        name="fake",
        extensions=[".fake"],
        filenames=[],
        patterns=[],
        description="",
        header_policy=FileTypeHeaderPolicy(supports_shebang=False),
    )

    lines: list[str] = ["#!/usr/bin/env fake", "echo hi\n"]
    assert p.find_insertion_index(lines) == 0


def test_line_mixin_skips_encoding_line_after_shebang() -> None:
    """Skip encoding line after shebang if policy encoding_line_regex is set."""
    from topmark.filetypes.base import FileType
    from topmark.filetypes.policy import FileTypeHeaderPolicy
    from topmark.pipeline.processors.mixins import LineCommentMixin

    class _P(LineCommentMixin):
        line_prefix = "# "

    p = _P()
    p.file_type = FileType(  # type: ignore[attr-defined]
        name="py",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True, encoding_line_regex=r"coding[:=]\s*([-\w.]+)"
        ),
    )

    lines: list[str] = ["#!/usr/bin/env python\n", "# coding: utf-8\n", "print(1)\n"]
    assert p.find_insertion_index(lines) == 2
