# topmark:header:start
#
#   project      : TopMark
#   file         : test_diff_output.py
#   file_relpath : tests/cli/test_diff_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI diff-output regression tests for check and strip commands.

These tests verify that `--diff` renders an actual unified diff in both
per-file and summary output modes. They intentionally exercise the CLI rather
than only presentation helpers so the selected runtime pipeline, diff view
lifecycle, report assembly, and output renderer are covered together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def _write_plain_python_file(tmp_path: Path) -> Path:
    """Write a Python file without a TopMark header.

    Args:
        tmp_path: Temporary test directory.

    Returns:
        Path to the created file.
    """
    path: Path = tmp_path / "example.py"
    path.write_text('print("hello")\n', encoding="utf-8")
    return path


def _write_markdown_file_with_topmark_header(tmp_path: Path) -> Path:
    """Write a Markdown file containing a removable TopMark header.

    Args:
        tmp_path: Temporary test directory.

    Returns:
        Path to the created file.
    """
    path: Path = tmp_path / "README.md"
    path.write_text(
        "\n".join(
            [
                "<!--",
                TOPMARK_START_MARKER,
                "",
                "  project   : Example",
                "  file      : README.md",
                "  license   : MIT",
                "",
                TOPMARK_END_MARKER,
                "-->",
                "",
                "# Example",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _assert_unified_diff_rendered(output: str, *, path_name: str) -> None:
    """Assert that CLI output contains a unified diff for a file.

    Args:
        output: Captured CLI output.
        path_name: Expected file name in diff headers.
    """
    assert f"--- {path_name}" in output
    assert f"+++ {path_name}" in output
    assert "@@" in output


def test_check_diff_text_per_file_output_renders_patch(tmp_path: Path) -> None:
    """`check --diff` should render a patch in TEXT per-file output."""
    path: Path = _write_plain_python_file(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RENDER_DIFF,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"+# {TOPMARK_START_MARKER}" in result.output


def test_check_diff_text_summary_output_renders_patch(tmp_path: Path) -> None:
    """`check --diff --summary` should render a patch in TEXT summary output."""
    path: Path = _write_plain_python_file(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RENDER_DIFF,
            CliOpt.RESULTS_SUMMARY_MODE,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"+# {TOPMARK_START_MARKER}" in result.output


def test_check_diff_markdown_per_file_output_renders_patch(tmp_path: Path) -> None:
    """`check --diff --output-format markdown` should render a fenced diff."""
    path: Path = _write_plain_python_file(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RENDER_DIFF,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    assert "```diff" in result.output
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"+# {TOPMARK_START_MARKER}" in result.output


def test_check_diff_markdown_summary_output_renders_patch(tmp_path: Path) -> None:
    """Markdown summary output should still render requested check diffs."""
    path: Path = _write_plain_python_file(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RENDER_DIFF,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    assert "## Diffs" in result.output
    assert "```diff" in result.output
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"+# {TOPMARK_START_MARKER}" in result.output


def test_strip_diff_text_per_file_output_renders_patch(tmp_path: Path) -> None:
    """`strip --diff` should render a patch in TEXT per-file output."""
    path: Path = _write_markdown_file_with_topmark_header(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.RENDER_DIFF,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"-{TOPMARK_START_MARKER}" in result.output
    assert "-<!--" in result.output


def test_strip_diff_text_summary_output_renders_patch(tmp_path: Path) -> None:
    """`strip --diff --summary` should render a patch in TEXT summary output."""
    path: Path = _write_markdown_file_with_topmark_header(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.RENDER_DIFF,
            CliOpt.RESULTS_SUMMARY_MODE,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"-{TOPMARK_START_MARKER}" in result.output
    assert "-<!--" in result.output


def test_strip_diff_markdown_per_file_output_renders_patch(tmp_path: Path) -> None:
    """`strip --diff --output-format markdown` should render a fenced diff."""
    path: Path = _write_markdown_file_with_topmark_header(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.RENDER_DIFF,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    assert "```diff" in result.output
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"-{TOPMARK_START_MARKER}" in result.output
    assert "-<!--" in result.output


def test_strip_diff_markdown_summary_output_renders_patch(tmp_path: Path) -> None:
    """Markdown summary output should still render requested strip diffs."""
    path: Path = _write_markdown_file_with_topmark_header(tmp_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.RENDER_DIFF,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.MARKDOWN.value,
            str(path),
        ],
        prune_views=True,
    )

    assert_WOULD_CHANGE(result)
    assert "## Diffs" in result.output
    assert "```diff" in result.output
    _assert_unified_diff_rendered(result.output, path_name=path.name)
    assert f"-{TOPMARK_START_MARKER}" in result.output
    assert "-<!--" in result.output
