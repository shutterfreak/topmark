# topmark:header:start
#
#   project      : TopMark
#   file         : test_write_error_exit_codes.py
#   file_relpath : tests/cli/test_write_error_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit-code contract tests for permission and apply/write failures.

This module pins two filesystem-related CLI contracts:
- unreadable inputs exit with PERMISSION_DENIED (77),
- apply-mode write failures exit with IO_ERROR (74).

The tests rely on POSIX permission semantics and are skipped on Windows.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_FILE_NOT_FOUND
from tests.cli.conftest import assert_IO_ERROR
from tests.cli.conftest import assert_PERMISSION_DENIED
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.constants import TOPMARK_END_MARKER
from topmark.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from click.testing import Result


pytestmark: list[pytest.MarkDecorator] = [
    pytest.mark.exit_code,
    pytest.mark.skipif(
        os.name == "nt",
        reason="POSIX permission semantics required",
    ),
]


# --- Permission fixtures ---


@pytest.fixture
def unreadable_file(tmp_path: Path) -> Iterator[Path]:
    """Create an unreadable file and restore permissions during teardown."""
    path: Path = tmp_path / "unreadable.py"
    path.write_text("print('x')\n", "utf-8")
    original_mode: int = path.stat().st_mode
    path.chmod(0o222)  # write-only
    try:
        yield path
    finally:
        path.chmod(original_mode)


@pytest.fixture
def unwritable_dir_with_file(tmp_path: Path) -> Iterator[Path]:
    """Create a file in an unwritable directory and restore permissions on teardown."""
    directory: Path = tmp_path / "locked"
    directory.mkdir()
    path: Path = directory / "x.py"
    path.write_text("print('x')\n", "utf-8")

    original_dir_mode: int = directory.stat().st_mode
    directory.chmod(0o555)
    try:
        yield path
    finally:
        directory.chmod(original_dir_mode)


@pytest.fixture
def unwritable_dir_with_header_file(
    tmp_path: Path,
) -> Iterator[Path]:
    """Create a removable-header file in an unwritable directory."""
    directory: Path = tmp_path / "locked_strip"
    directory.mkdir()
    path: Path = directory / "x.py"
    path.write_text(
        f"# {TOPMARK_START_MARKER}\n# project: TopMark\n# {TOPMARK_END_MARKER}\nprint('x')\n",
        "utf-8",
    )

    original_dir_mode: int = directory.stat().st_mode
    directory.chmod(0o555)
    try:
        yield path
    finally:
        directory.chmod(original_dir_mode)


# --- Mixed-result fixtures ---


@pytest.fixture
def unwritable_dir_with_file_and_missing_peer(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Create one write-failing file and one missing peer path."""
    directory: Path = tmp_path / "locked_mixed_missing"
    directory.mkdir()
    writable_failure: Path = directory / "x.py"
    writable_failure.write_text("print('x')\n", "utf-8")
    missing_path: Path = tmp_path / "missing.py"

    original_dir_mode: int = directory.stat().st_mode
    directory.chmod(0o555)
    try:
        yield writable_failure, missing_path
    finally:
        directory.chmod(original_dir_mode)


# --- Input permission contract ---


def test_check_unreadable_file_exits_permission_denied(
    unreadable_file: Path,
) -> None:
    """`check` should exit PERMISSION_DENIED for unreadable inputs."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            str(unreadable_file),
        ]
    )

    assert_PERMISSION_DENIED(result)


def test_check_apply_unreadable_file_exits_permission_denied(
    unreadable_file: Path,
) -> None:
    """`check --apply` should exit PERMISSION_DENIED for unreadable inputs."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(unreadable_file),
        ]
    )

    assert_PERMISSION_DENIED(result)


# --- Apply/write IO_ERROR contract ---


def test_check_apply_write_failure_exits_io_error(
    unwritable_dir_with_file: Path,
) -> None:
    """`check --apply` should exit IO_ERROR when writing fails."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(unwritable_dir_with_file),
        ]
    )

    assert_IO_ERROR(result)


def test_strip_apply_write_failure_exits_io_error(
    tmp_path: Path,
    unwritable_dir_with_header_file: Path,
) -> None:
    """`strip --apply` should exit IO_ERROR when writing fails."""
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.APPLY_CHANGES,
            str(unwritable_dir_with_header_file),
        ],
    )

    assert_IO_ERROR(result)


def test_strip_unreadable_file_exits_permission_denied(
    unreadable_file: Path,
) -> None:
    """`strip` should exit PERMISSION_DENIED for unreadable inputs."""
    result: Result = run_cli(
        [
            CliCmd.STRIP,
            str(unreadable_file),
        ]
    )

    assert_PERMISSION_DENIED(result)


# --- Mixed-result priority contract ---


def test_check_mixed_unreadable_and_would_change_exits_permission_denied(
    tmp_path: Path,
    unreadable_file: Path,
) -> None:
    """Permission failures should beat dry-run WOULD_CHANGE in mixed check runs."""
    needs_header: Path = tmp_path / "needs_header.py"
    needs_header.write_text("print('needs header')\n", "utf-8")

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            str(needs_header),
            str(unreadable_file),
        ]
    )

    assert_PERMISSION_DENIED(result)


def test_check_apply_mixed_unreadable_and_write_failure_exits_permission_denied(
    unreadable_file: Path,
    unwritable_dir_with_file: Path,
) -> None:
    """Permission failures should beat apply/write IO_ERROR in mixed check runs."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(unreadable_file),
            str(unwritable_dir_with_file),
        ]
    )

    assert_PERMISSION_DENIED(result)


@pytest.mark.xfail(
    reason=(
        "CLI input/config resolution still drops explicit missing path arguments "
        "before they reach FileListResolution / pipeline exit-code prioritization"
    ),
    strict=True,
)
def test_check_apply_mixed_missing_and_write_failure_exits_file_not_found(
    unwritable_dir_with_file_and_missing_peer: tuple[Path, Path],
) -> None:
    """Missing CLI inputs should beat apply/write IO_ERROR in mixed check runs."""
    write_failure_path, missing_path = unwritable_dir_with_file_and_missing_peer

    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(write_failure_path),
            str(missing_path),
        ]
    )

    assert_FILE_NOT_FOUND(result)
