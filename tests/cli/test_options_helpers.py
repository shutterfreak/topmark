# topmark:header:start
#
#   project      : TopMark
#   file         : test_options_helpers.py
#   file_relpath : tests/cli/test_options_helpers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for reusable CLI option parsing and validation helpers."""

from __future__ import annotations

import click
import pytest

from topmark.cli.errors import TopmarkCliUsageError
from topmark.cli.options import FromOptionStdinText
from topmark.cli.options import FromOptionValues
from topmark.cli.options import extend_with_stdin_lines
from topmark.cli.options import extract_stdin_for_from_options
from topmark.cli.options import split_nonempty_lines
from topmark.cli.options import strip_dash_sentinels
from topmark.cli.validators import validate_mutually_exclusive


def test_split_nonempty_lines_ignores_blank_and_comment_lines() -> None:
    """Split helper should ignore blank lines and comment-only lines."""
    assert split_nonempty_lines("one\n\n# comment\n two \n") == ["one", "two"]


def test_extend_with_stdin_lines_extends_existing_target() -> None:
    """STDIN line helper should append parsed lines to the existing list."""
    target: list[str] = ["existing"]

    result: list[str] = extend_with_stdin_lines(target, "one\n# comment\ntwo\n")

    assert result is target
    assert target == ["existing", "one", "two"]


def test_strip_dash_sentinels_removes_stdin_markers() -> None:
    """Dash sentinels should be removed from all --*-from values."""
    result: FromOptionValues = strip_dash_sentinels(
        files_from=("files.txt", "-"),
        include_from=("-", "src/**"),
        exclude_from=("build/**", "-"),
    )

    assert result.files_from == ["files.txt"]
    assert result.include_from == ["src/**"]
    assert result.exclude_from == ["build/**"]


def test_extract_stdin_for_from_options_routes_files_from_stdin_text() -> None:
    """A single --files-from dash should receive the provided STDIN text."""
    result: FromOptionStdinText = extract_stdin_for_from_options(
        files_from=("-",),
        include_from=(),
        exclude_from=(),
        stdin_text="README.md\n",
    )

    assert result.files_from == "README.md\n"
    assert result.include_from is None
    assert result.exclude_from is None


def test_extract_stdin_for_from_options_rejects_multiple_stdin_consumers() -> None:
    """Only one --*-from option may consume STDIN."""
    with pytest.raises(TopmarkCliUsageError, match="Only one of"):
        extract_stdin_for_from_options(
            files_from=("-",),
            include_from=("-",),
            exclude_from=(),
            stdin_text="README.md\n",
        )


def test_validate_mutually_exclusive_joins_two_options() -> None:
    """Mutual-exclusion diagnostics should join two enabled options with 'and'."""
    ctx = click.Context(click.Command("check"), info_name="topmark check")

    with pytest.raises(TopmarkCliUsageError, match="--one and --two are mutually exclusive"):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--one": True,
                "--two": True,
            },
        )


def test_validate_mutually_exclusive_joins_three_options() -> None:
    """Mutual-exclusion diagnostics should join three enabled options readably."""
    ctx = click.Context(click.Command("check"), info_name="topmark check")

    with pytest.raises(
        TopmarkCliUsageError,
        match="--one, --two and --three are mutually exclusive",
    ):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--one": True,
                "--two": True,
                "--three": True,
            },
        )
