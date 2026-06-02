# topmark:header:start
#
#   project      : TopMark
#   file         : test_filename_rules.py
#   file_relpath : tests/filetypes/test_filename_rules.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for FileType filename-rule normalization and validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.errors import InvalidFileTypeDefinitionError

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


def test_file_type_normalizes_filename_tail_subpath_rules() -> None:
    """Backslash-containing filename rules are stored as POSIX tail rules."""
    file_type: FileType = make_file_type(
        local_key="vscode_settings",
        extensions=[],
        filenames=[r".vscode\settings.json"],
        patterns=[],
    )

    assert file_type.filenames == [".vscode/settings.json"]


def test_file_type_normalizes_mixed_separator_filename_rules() -> None:
    """Mixed separator filename rules are canonicalized during construction."""
    file_type: FileType = make_file_type(
        local_key="nested_config",
        extensions=[],
        filenames=[
            r"config\nested/settings.json",  # raw string containing a backslash, not a newline
        ],
        patterns=[],
    )

    assert file_type.filenames == ["config/nested/settings.json"]


def test_file_type_keeps_basename_filename_rules_unchanged() -> None:
    """Basename filename rules are preserved when no separator is present."""
    file_type: FileType = make_file_type(
        local_key="makefile",
        extensions=[],
        filenames=["Makefile"],
        patterns=[],
    )

    assert file_type.filenames == ["Makefile"]


@pytest.mark.parametrize(
    "rule",
    [
        pytest.param("", id="empty"),
        pytest.param(".", id="dot"),
        pytest.param("..", id="dot-dot"),
        pytest.param("/absolute/settings.json", id="posix-absolute"),
        pytest.param("//server/share/settings.json", id="posix-unc-like"),
        pytest.param(r"\\server\share\settings.json", id="windows-unc"),
        pytest.param("C:/Users/example/settings.json", id="windows-drive-posix"),
        pytest.param(
            r"C:\Users\example\settings.json",
            id="windows-drive-backslash",
        ),
        pytest.param("config//settings.json", id="empty-segment"),
        pytest.param("config/./settings.json", id="dot-segment"),
        pytest.param("config/../settings.json", id="dot-dot-segment"),
        pytest.param("config/settings.json/.", id="trailing-dot-segment"),
        pytest.param("config/settings.json/..", id="trailing-dot-dot-segment"),
    ],
)
def test_file_type_rejects_invalid_filename_rules(rule: str) -> None:
    """Filename rules must be relative registry matching rules, not paths."""
    with pytest.raises(InvalidFileTypeDefinitionError, match="filename rule"):
        make_file_type(
            local_key="invalid_filename_rule",
            extensions=[],
            filenames=[rule],
            patterns=[],
            description="Invalid filename-rule fixture",
        )
