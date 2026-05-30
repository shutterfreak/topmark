# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_human_output.py
#   file_relpath : tests/cli/test_probe_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI probe human-output behavior tests.

This module verifies human-facing `topmark probe` output behavior:
- TEXT output changes progressively with verbosity,
- explicitly filtered inputs are reported with actionable diagnostics,
- Markdown output ignores TEXT-only verbosity and quiet controls.

These are output/rendering tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


# --- TEXT output: verbosity levels ---
def test_probe_text_output_progressively_expands_with_verbosity(tmp_path: Path) -> None:
    """TEXT probe output should progressively expand from default to `-vv`."""
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
            CliOpt.VERBOSE,
        ],
    )
    result_vv: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.VERBOSE,
            CliOpt.VERBOSE,
        ],
    )

    assert_SUCCESS(result_default)
    assert_SUCCESS(result_v)
    assert_SUCCESS(result_vv)

    # Default TEXT output is a compact one-line summary.
    assert "resolved" in result_default.output
    assert "processor=" in result_default.output

    # `-v` adds selected file type and processor details.
    assert "selected file type" in result_v.output
    assert "selected processor" in result_v.output

    # `-vv` adds candidate and match details.
    assert "candidates:" in result_vv.output
    assert "match:" in result_vv.output

    # Each verbosity level should provide a distinct TEXT rendering.
    assert result_default.output != result_v.output
    assert result_v.output != result_vv.output


# --- TEXT output: filtered explicit inputs ---


def test_probe_text_output_reports_explicitly_filtered_input(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """TEXT probe output should explain explicit inputs filtered before resolution."""
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
            CliOpt.EXCLUDE_PATTERNS,
            "__pycache__/",
            input_path,
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)

    assert "<filtered>" in result.output
    assert "filtered: excluded_by_path_filter" in result.output


def test_probe_text_output_omits_directory_filtered_result_when_children_selected(
    tmp_path: Path,
) -> None:
    """Expanded directories should not be reported as filtered inputs."""
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

    assert "example.py" in result.output
    assert "README.md" in result.output
    assert "<filtered>" not in result.output


def test_probe_text_output_reports_missing_input_only_once(
    tmp_path: Path,
) -> None:
    """Missing explicit inputs should not also appear as filtered."""
    missing_directory: Path = tmp_path / "topmark-does-not-exist"
    runner = CliRunner()

    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(missing_directory),
        ],
    )

    assert result.exit_code != 0

    assert "probe-missing" in result.output
    assert "<filtered>" not in result.output


# --- Markdown output: verbosity and quiet controls ---


def test_probe_markdown_output_ignores_text_verbosity(tmp_path: Path) -> None:
    """Markdown probe output should ignore TEXT-only verbosity flags."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result_default: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
        ],
    )
    result_v: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            CliOpt.VERBOSE,
        ],
    )

    assert_SUCCESS(result_default)
    assert_SUCCESS(result_v)

    # Markdown ignores TEXT verbosity, so output should be identical.
    assert result_default.output == result_v.output

    # Basic Markdown structure checks.
    assert "TopMark Resolution Probe Results" in result_default.output
    assert "## Files" in result_default.output
    assert "###" in result_default.output


def test_probe_markdown_output_ignores_text_quiet(tmp_path: Path) -> None:
    """Markdown probe output should ignore TEXT-only quiet suppression."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()

    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            CliOpt.QUIET,
        ],
    )

    assert_SUCCESS(result)

    # Markdown should still render full document output.
    assert result.output.strip() != ""
    assert "TopMark Resolution Probe Results" in result.output
