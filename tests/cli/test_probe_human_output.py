# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_human_output.py
#   file_relpath : tests/cli/test_probe_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI human-output tests for `topmark probe`.

These tests validate TEXT and Markdown rendering behavior for the probe
command, including verbosity handling and Markdown invariants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from topmark.cli.keys import CliCmd
from topmark.cli.main import cli

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_probe_text_output_default_and_verbose_levels(tmp_path: Path) -> None:
    """TEXT output should change with verbosity levels."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result_default: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
        ],
    )
    result_v: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            "-v",
        ],
    )
    result_vv: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            "-vv",
        ],
    )

    assert result_default.exit_code == 0
    assert result_v.exit_code == 0
    assert result_vv.exit_code == 0

    # Default: compact one-line summary
    assert "resolved" in result_default.output
    assert "processor=" in result_default.output

    # -v: selected details appear
    assert "selected file type" in result_v.output
    assert "selected processor" in result_v.output

    # -vv: candidate details appear
    assert "candidates:" in result_vv.output
    assert "match:" in result_vv.output

    # Ensure outputs differ across verbosity levels
    assert result_default.output != result_v.output
    assert result_v.output != result_vv.output


def test_probe_text_output_reports_explicit_filtered_input(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """TEXT output should explain explicit inputs filtered before probing."""
    monkeypatch.chdir(tmp_path)
    filtered_dir: Path = tmp_path / "__pycache__"
    filtered_dir.mkdir()
    file: Path = filtered_dir / "example.cpython-312.pyc"
    file.write_bytes(b"\x00\x00\x00\x00")
    input_path: str = "__pycache__/example.cpython-312.pyc"

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            "--exclude",
            "__pycache__/",
            input_path,
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)

    assert "<filtered>" in result.output
    assert "filtered: excluded_by_discovery_filter" in result.output


def test_probe_markdown_output_ignores_verbosity(tmp_path: Path) -> None:
    """Markdown output should not depend on verbosity flags."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result_default: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            "--output-format",
            "markdown",
        ],
    )
    result_v: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            "--output-format",
            "markdown",
            "-v",
        ],
    )

    assert result_default.exit_code == 0
    assert result_v.exit_code == 0

    # Markdown ignores verbosity → outputs should be identical
    assert result_default.output == result_v.output

    # Basic Markdown structure checks
    assert "TopMark Resolution Probe Results" in result_default.output
    assert "## Files" in result_default.output
    assert "###" in result_default.output


def test_probe_markdown_output_ignores_quiet(tmp_path: Path) -> None:
    """Markdown output should not be suppressed by --quiet."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            "--output-format",
            "markdown",
            "--quiet",
        ],
    )

    assert result.exit_code == 0

    # Markdown should still render full output
    assert result.output.strip() != ""
    assert "TopMark Resolution Probe Results" in result.output
