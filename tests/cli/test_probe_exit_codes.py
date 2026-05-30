# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_exit_codes.py
#   file_relpath : tests/cli/test_probe_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit-code contract tests for `topmark probe`.

These tests pin the public CLI contract for resolution outcomes:
- all inputs resolved → SUCCESS (0)
- missing explicit inputs → FILE_NOT_FOUND (66)
- semantic probe failures (unresolved/unsupported/filtered) → UNSUPPORTED_FILE_TYPE (69)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_FILE_NOT_FOUND
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli

if TYPE_CHECKING:
    from pathlib import Path


# All tests in this module pin documented CLI exit-code behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Fully resolved inputs ---
def test_probe_exit_code_success_for_supported_file(tmp_path: Path) -> None:
    """Supported inputs should resolve fully and exit SUCCESS."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
        ],
    )
    assert_SUCCESS(result)


def test_probe_exit_code_success_for_filtered_directory_with_selected_files(
    tmp_path: Path,
) -> None:
    """Directory inputs with selected children should exit SUCCESS."""
    directory: Path = tmp_path / "project"
    directory.mkdir()
    python_file: Path = directory / "example.py"
    python_file.write_text("print('hello')\n", encoding="utf-8")
    markdown_file: Path = directory / "README.md"
    markdown_file.write_text("# Example\n", encoding="utf-8")
    html_file: Path = directory / "index.html"
    html_file.write_text("<h1>Example</h1>\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.INCLUDE_FILE_TYPES,
            "python",
            CliOpt.INCLUDE_FILE_TYPES,
            "markdown,toml",
            CliOpt.EXCLUDE_FILE_TYPES,
            "html",
            str(directory),
        ],
    )

    assert_SUCCESS(result)


# --- Config validation failures ---
@pytest.mark.parametrize(
    "include_file_types,exclude_file_types",
    [
        ("python", "python"),
        ("python", "topmark:python"),
        ("topmark:python", "python"),
        ("topmark:python", "topmark:python"),
    ],
)
def test_probe_exit_code_config_error_for_strict_file_type_overlap(
    tmp_path: Path,
    include_file_types: str,
    exclude_file_types: str,
) -> None:
    """Strict config warnings should exit CONFIG_ERROR before probing inputs."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            str(file),
        ],
    )

    assert_CONFIG_ERROR(result)


# --- Unsupported / unresolved inputs ---
def test_probe_exit_code_unsupported_for_unknown_file(tmp_path: Path) -> None:
    """Unsupported file types should exit with the UNAVAILABLE contract code."""
    file: Path = tmp_path / "example.unknown"
    file.write_text("data\n", encoding="utf-8")
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
        ],
    )
    assert_UNSUPPORTED_FILE_TYPE(result)


def test_probe_exit_code_unsupported_for_mixed_files(tmp_path: Path) -> None:
    """Mixed inputs should exit UNAVAILABLE when any input is unsupported."""
    file_ok: Path = tmp_path / "example.py"
    file_ok.write_text("print('hello')\n", encoding="utf-8")
    file_bad: Path = tmp_path / "example.unknown"
    file_bad.write_text("data\n", encoding="utf-8")
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file_ok),
            str(file_bad),
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)


# --- Missing explicit inputs beat semantic probe outcomes ---
def test_probe_exit_code_file_not_found_for_missing_file(tmp_path: Path) -> None:
    """Missing explicit inputs should exit FILE_NOT_FOUND."""
    missing_file: Path = tmp_path / "missing.py"
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(missing_file),
        ],
    )

    assert_FILE_NOT_FOUND(result)


def test_probe_exit_code_file_not_found_for_mixed_missing_and_unsupported(
    tmp_path: Path,
) -> None:
    """Missing inputs should beat unsupported semantic probe outcomes."""
    missing_file: Path = tmp_path / "missing.py"
    unsupported_file: Path = tmp_path / "example.unknown"
    unsupported_file.write_text("data\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(missing_file),
            str(unsupported_file),
        ],
    )

    assert_FILE_NOT_FOUND(result)
