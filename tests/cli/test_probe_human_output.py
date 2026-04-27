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

from topmark.cli.keys import CliCmd
from topmark.cli.main import cli

if TYPE_CHECKING:
    from pathlib import Path


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
    assert "TopMark probe Results" in result_default.output
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
    assert "TopMark probe Results" in result.output
