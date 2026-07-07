# topmark:header:start
#
#   project      : TopMark
#   file         : test_model_matching.py
#   file_relpath : tests/filetypes/test_model_matching.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for direct FileType filename, extension, and pattern matching."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


def test_file_type_matches_extension_rule() -> None:
    """Extension rules match paths by suffix."""
    file_type: FileType = make_file_type(
        local_key="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
    )

    assert file_type.matches(Path("src/topmark/__init__.py")) is True


def test_file_type_does_not_match_unrelated_extension_rule() -> None:
    """Extension rules do not match unrelated suffixes."""
    file_type: FileType = make_file_type(
        local_key="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
    )

    assert file_type.matches(Path("docs/index.md")) is False


def test_file_type_matches_basename_filename_rule() -> None:
    """Basename filename rules match exact path names."""
    file_type: FileType = make_file_type(
        local_key="makefile",
        extensions=[],
        filenames=["Makefile"],
        patterns=[],
    )

    assert file_type.matches(Path("build/Makefile")) is True


def test_file_type_does_not_match_basename_filename_rule_as_tail() -> None:
    """Basename filename rules do not match partial tail-subpaths."""
    file_type: FileType = make_file_type(
        local_key="makefile",
        extensions=[],
        filenames=["Makefile"],
        patterns=[],
    )

    assert file_type.matches(Path("build/Makefile.local")) is False


def test_file_type_matches_normalized_tail_subpath_filename_rule() -> None:
    """Backslash-origin filename rules match canonical POSIX tail-subpaths."""
    file_type: FileType = make_file_type(
        local_key="vscode_settings",
        extensions=[],
        filenames=[r".vscode\settings.json"],
        patterns=[],
    )

    assert file_type.matches(Path("project/.vscode/settings.json")) is True


def test_file_type_does_not_match_unrelated_tail_subpath_filename_rule() -> None:
    """Tail-subpath filename rules do not match unrelated paths."""
    file_type: FileType = make_file_type(
        local_key="vscode_settings",
        extensions=[],
        filenames=[".vscode/settings.json"],
        patterns=[],
    )

    assert file_type.matches(Path("project/settings.json")) is False


def test_file_type_matches_pattern_rule() -> None:
    """Pattern rules match POSIX-style path strings."""
    file_type: FileType = make_file_type(
        local_key="requirements",
        extensions=[],
        filenames=[],
        patterns=[r"requirements\.(in|txt)"],
    )

    assert file_type.matches(Path("requirements.txt")) is True


def test_file_type_does_not_match_unrelated_pattern_rule() -> None:
    """Pattern rules do not match unrelated POSIX-style path strings."""
    file_type: FileType = make_file_type(
        local_key="requirements",
        extensions=[],
        filenames=[],
        patterns=[r"requirements\.(in|txt)"],
    )

    assert file_type.matches(Path("constraints.txt")) is False


def test_file_type_matches_multi_dot_extension_rule() -> None:
    """Multi-dot extension rules match complete filename suffixes."""
    file_type: FileType = make_file_type(
        local_key="archive",
        extensions=[".tar.gz"],
        filenames=[],
        patterns=[],
    )

    assert file_type.matches(Path("dist/topmark.tar.gz")) is True
    assert file_type.matches(Path("dist/topmark.gz")) is False


def test_file_type_invalid_pattern_fails_closed() -> None:
    """Invalid regex patterns do not crash matching."""
    file_type: FileType = make_file_type(
        local_key="broken-pattern",
        extensions=[],
        filenames=[],
        patterns=["["],
    )

    assert file_type.matches(Path("anything.txt")) is False
