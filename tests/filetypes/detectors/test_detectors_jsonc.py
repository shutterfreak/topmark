# topmark:header:start
#
#   project      : TopMark
#   file         : test_detectors_jsonc.py
#   file_relpath : tests/filetypes/detectors/test_detectors_jsonc.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for JSONC content detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.filetypes.detectors.jsonc import looks_like_jsonc

if TYPE_CHECKING:
    from pathlib import Path


def _write_json(tmp_path: Path, content: str) -> Path:
    """Write JSON-like detector input using UTF-8 text."""
    path: Path = tmp_path / "settings.json"
    path.write_text(
        content,
        encoding="utf-8",
        newline="",
    )
    return path


def test_looks_like_jsonc_fails_closed_for_unreadable_path(tmp_path: Path) -> None:
    """Unreadable or missing files are not classified as JSONC."""
    assert looks_like_jsonc(tmp_path / "missing.json") is False


@pytest.mark.parametrize(
    "content",
    [
        "plain text with // comment marker\n",
        "// comment without JSON structure\n",
        "/* block comment without JSON structure */\n",
    ],
)
def test_looks_like_jsonc_requires_json_structure(
    tmp_path: Path,
    content: str,
) -> None:
    """Comment markers alone are insufficient without JSON braces or brackets."""
    assert looks_like_jsonc(_write_json(tmp_path, content)) is False


@pytest.mark.parametrize(
    "content",
    [
        '{\n  // comment\n  "name": "topmark"\n}\n',
        "[\n  /* comment */\n  1\n]\n",
    ],
)
def test_looks_like_jsonc_detects_comments_outside_strings(
    tmp_path: Path,
    content: str,
) -> None:
    """Line and block comments outside strings classify content as JSONC."""
    assert looks_like_jsonc(_write_json(tmp_path, content)) is True


@pytest.mark.parametrize(
    "content",
    [
        '{"url": "https://example.test/path"}\n',
        '{"pattern": "not /* a comment */ inside a string"}\n',
        '{"escaped": "a string with an escaped quote \\" // still text"}\n',
        r'{"slashes": "escaped backslash before quote \\\\\" and // still text"}' "\n",
    ],
)
def test_looks_like_jsonc_ignores_comment_markers_inside_strings(
    tmp_path: Path,
    content: str,
) -> None:
    """Comment-looking tokens inside JSON strings are not JSONC evidence."""
    assert looks_like_jsonc(_write_json(tmp_path, content)) is False


# Additional tests for escaped backslash and comment detection edge cases
def test_looks_like_jsonc_closes_string_after_escaped_backslash_pair(
    tmp_path: Path,
) -> None:
    """An even backslash run before a quote lets detection resume outside strings."""
    path: Path = _write_json(
        tmp_path,
        r'{"path": "C:\\"} // comment outside string' "\n",
    )

    assert looks_like_jsonc(path) is True


def test_looks_like_jsonc_keeps_string_open_after_odd_backslash_run(
    tmp_path: Path,
) -> None:
    """An odd backslash run before a quote keeps following markers inside strings."""
    path: Path = _write_json(
        tmp_path,
        r'{"path": "C:\\\" // still inside string"}' "\n",
    )

    assert looks_like_jsonc(path) is False


def test_looks_like_jsonc_ignores_non_comment_slash_outside_strings(
    tmp_path: Path,
) -> None:
    """A slash outside strings is not JSONC evidence unless it starts a comment."""
    path: Path = _write_json(
        tmp_path,
        '{"division": 1 / 2}\n',
    )

    assert looks_like_jsonc(path) is False


def test_looks_like_jsonc_allows_comment_after_string_closes(tmp_path: Path) -> None:
    """Comment detection resumes after a quoted JSON string closes."""
    path: Path = _write_json(
        tmp_path,
        '{"url": "https://example.test"}\n// trailing comment\n',
    )

    assert looks_like_jsonc(path) is True


def test_looks_like_jsonc_detects_unterminated_block_comment(tmp_path: Path) -> None:
    """A block comment start outside strings is enough even if EOF closes nothing."""
    assert looks_like_jsonc(_write_json(tmp_path, "{\n  /* unfinished\n")) is True


def test_looks_like_jsonc_continues_after_line_comment_newline(tmp_path: Path) -> None:
    """Line comments end at CR/LF and later content remains detectable."""
    path: Path = _write_json(
        tmp_path,
        "{\n  // first comment\r\n  /* second comment */\n}\n",
    )

    assert looks_like_jsonc(path) is True
