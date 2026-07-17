# topmark:header:start
#
#   project      : TopMark
#   file         : test_mixins.py
#   file_relpath : tests/processors/test_mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the runtime-bearing line-comment processor mixin."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.processors.mixins import LineCommentMixin

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


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


@pytest.mark.parametrize("lines", [[], ["body\n"]])
def test_line_mixin_without_shebang_uses_top_of_file(lines: list[str]) -> None:
    """Empty and ordinary files retain the top-of-file insertion anchor."""
    assert _LineProc().find_insertion_index(lines) == 0


def test_line_mixin_respects_no_shebang_policy() -> None:
    """Do not skip shebang when policy.supports_shebang is False."""

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    p = _P()
    p.file_type = make_file_type(
        local_key="fake",
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

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    p = _P()
    p.file_type = make_file_type(
        local_key="py",
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


@pytest.mark.parametrize(
    "lines",
    [
        ["#!/usr/bin/env python\n"],
        ["#!/usr/bin/env python\n", "# ordinary comment\n"],
    ],
)
def test_line_mixin_keeps_shebang_anchor_without_matching_encoding_line(
    lines: list[str],
) -> None:
    """An absent or nonmatching encoding line is not consumed."""

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    processor = _P()
    processor.file_type = make_file_type(
        local_key="encoding-nonmatch",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=r"coding[:=]\s*([-\w.]+)",
        ),
    )

    assert processor.find_insertion_index(lines) == 1


def test_line_render_header_line_uses_optional_suffix() -> None:
    """Line comments with suffix delimiters append that suffix exactly once."""

    class _SuffixProc(LineCommentMixin):
        line_prefix = "-- "
        line_suffix = " --"

    assert _SuffixProc().render_header_line("payload") == "-- payload --"


def test_line_mixin_invalid_encoding_regex_does_not_break_insertion() -> None:
    """Invalid configured encoding regexes should fall back to shebang-only skipping."""

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    p = _P()
    p.file_type = make_file_type(
        local_key="invalid_regex",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex="[",
        ),
    )

    lines: list[str] = ["#!/usr/bin/env python\n", "# coding: utf-8\n", "print(1)\n"]
    assert p.find_insertion_index(lines) == 1


def test_line_prepare_header_for_insertion_adds_policy_spacers() -> None:
    """Line insertion adds owned leading/trailing spacers when policy requests them."""

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    p = _P()
    p.file_type = make_file_type(
        local_key="line_spacing",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="",
        header_policy=FileTypeHeaderPolicy(
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    )

    out: list[str] = p.prepare_header_for_insertion(
        original_lines=["preamble\n", "body\n"],
        insert_index=1,
        rendered_header_lines=["# header\n"],
        newline_style="\n",
    )

    assert out == ["\n", "# header\n", "\n"]


def test_line_prepare_header_for_insertion_preserves_user_whitespace_body() -> None:
    """Whitespace-only body lines are not mistaken for owned exact blank separators."""

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    p = _P()
    p.file_type = make_file_type(
        local_key="line_user_whitespace",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="",
        header_policy=FileTypeHeaderPolicy(ensure_blank_after_header=True),
    )

    out: list[str] = p.prepare_header_for_insertion(
        original_lines=[" \n", "body\n"],
        insert_index=0,
        rendered_header_lines=["# header\n"],
        newline_style="\n",
    )

    assert out == ["# header\n", "\n"]


@pytest.mark.parametrize(
    ("original_lines", "insert_index", "policy", "expected"),
    [
        (["body\n"], 0, None, ["# header\n", "\n"]),
        ([], 0, None, ["# header\n"]),
        (
            ["\n", "body\n"],
            1,
            FileTypeHeaderPolicy(
                pre_header_blank_after_block=1,
                ensure_blank_after_header=True,
            ),
            ["# header\n", "\n"],
        ),
        (
            ["body\n"],
            0,
            FileTypeHeaderPolicy(ensure_blank_after_header=False),
            ["# header\n"],
        ),
        (["\n"], 0, FileTypeHeaderPolicy(), ["# header\n"]),
        (["\rbody"], 0, FileTypeHeaderPolicy(), ["# header\n"]),
        (["\x85body"], 0, FileTypeHeaderPolicy(), ["# header\n"]),
        (["\u2028body"], 0, FileTypeHeaderPolicy(), ["# header\n"]),
        (["\u2029body"], 0, FileTypeHeaderPolicy(), ["# header\n"]),
    ],
)
def test_line_padding_policy_matrix_is_non_mutating(
    original_lines: list[str],
    insert_index: int,
    policy: FileTypeHeaderPolicy | None,
    expected: list[str],
) -> None:
    """Shared padding handles defaults, EOF, existing separators, and sentinels."""

    class _P(LineCommentMixin):
        file_type: FileType
        line_prefix = "# "

    processor = _P()
    if policy is not None:
        processor.file_type = make_file_type(
            local_key="padding-matrix",
            header_policy=policy,
        )
    rendered: list[str] = ["# header\n"]
    original_snapshot: list[str] = list(original_lines)
    rendered_snapshot: list[str] = list(rendered)

    result: list[str] = processor.prepare_header_for_insertion(
        original_lines=original_lines,
        insert_index=insert_index,
        rendered_header_lines=rendered,
        newline_style="\n",
    )

    assert result == expected
    assert original_lines == original_snapshot
    assert rendered == rendered_snapshot
