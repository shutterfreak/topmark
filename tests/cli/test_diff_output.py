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

import pytest

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_markdown_output_does_not_contain
from tests.cli.conftest import assert_rich_output_does_not_contain
from tests.cli.conftest import assert_SUCCESS
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


def _write_python_file_with_topmark_header(tmp_path: Path) -> Path:
    """Write a Python file containing a compliant TopMark header.

    Args:
        tmp_path: Temporary test directory.

    Returns:
        Path to the created file.
    """
    path: Path = tmp_path / "example.py"
    path.write_text(
        "\n".join(
            [
                f"# {TOPMARK_START_MARKER}",
                "#",
                "#   file         : example.py",
                "#   file_relpath : example.py",
                "#",
                f"# {TOPMARK_END_MARKER}",
                "",
                'print("hello")',
                "",
            ]
        ),
        encoding="utf-8",
    )
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


def _assert_text_diff_output_absent(output: str) -> None:
    """Assert that TEXT CLI output does not contain diff markers.

    Args:
        output: Captured CLI output.
    """
    assert_rich_output_does_not_contain(
        output=output,
        expected="diffs - start",
    )
    assert_rich_output_does_not_contain(
        output=output,
        expected="diffs - end",
    )
    assert_rich_output_does_not_contain(output=output, expected="--- example.py")
    assert_rich_output_does_not_contain(output=output, expected="+++ example.py")
    assert_rich_output_does_not_contain(output=output, expected="@@")


def _assert_markdown_diff_output_absent(output: str) -> None:
    """Assert that Markdown CLI output does not contain diff markers.

    Args:
        output: Captured CLI output.
    """
    assert_markdown_output_does_not_contain(
        output=output,
        expected="## Diffs",
    )
    assert_markdown_output_does_not_contain(output=output, expected="```diff")
    assert_markdown_output_does_not_contain(output=output, expected="--- example.py")
    assert_markdown_output_does_not_contain(output=output, expected="+++ example.py")
    assert_markdown_output_does_not_contain(output=output, expected="@@")


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


def test_check_diff_summary_output_suppresses_empty_diff_section(tmp_path: Path) -> None:
    """TEXT summary output should omit diff fences when no check diff exists."""
    path: Path = _write_plain_python_file(tmp_path)
    run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(path),
        ],
        prune_views=True,
    )

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

    assert_SUCCESS(result)
    assert_rich_output_does_not_contain(
        output=result.output,
        expected="diffs - start",
    )
    assert_rich_output_does_not_contain(
        output=result.output,
        expected="diffs - end",
    )


def test_check_diff_markdown_summary_output_suppresses_empty_diff_section(
    tmp_path: Path,
) -> None:
    """Markdown summary output should omit `## Diffs` when no check diff exists."""
    path: Path = _write_plain_python_file(tmp_path)
    run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            str(path),
        ],
        prune_views=True,
    )

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

    assert_SUCCESS(result)
    assert_markdown_output_does_not_contain(
        output=result.output,
        expected="## Diffs",
    )
    assert_markdown_output_does_not_contain(
        output=result.output,
        expected="```diff",
    )


@pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
    ],
)
def test_check_apply_summary_output_reports_inserted_file(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """`check --apply --summary` should report the inserted summary bucket."""
    path: Path = _write_plain_python_file(tmp_path)

    args: list[str] = [
        CliCmd.CHECK,
        CliOpt.APPLY_CHANGES,
        CliOpt.RESULTS_SUMMARY_MODE,
    ]
    if output_format is OutputFormat.MARKDOWN:
        args.extend([CliOpt.OUTPUT_FORMAT, output_format.value])
    args.append(str(path))

    result: Result = run_cli_in(tmp_path, args, prune_views=True)

    assert_SUCCESS(result)
    assert TOPMARK_START_MARKER in path.read_text(encoding="utf-8")
    assert "inserted" in result.output.lower()


@pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
    ],
)
def test_check_diff_per_file_output_suppresses_empty_diff_section(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """`check --diff` per-file output should omit diff sections without a diff."""
    path: Path = _write_python_file_with_topmark_header(tmp_path)

    args: list[str] = [
        CliCmd.CHECK,
        CliOpt.RENDER_DIFF,
        CliOpt.REPORT,
        "all",
    ]
    if output_format is OutputFormat.MARKDOWN:
        args.extend([CliOpt.OUTPUT_FORMAT, output_format.value])
    args.append(str(path))

    result: Result = run_cli_in(tmp_path, args, prune_views=True)

    assert_SUCCESS(result)
    if output_format is OutputFormat.MARKDOWN:
        assert "# TopMark" in result.output
        _assert_markdown_diff_output_absent(result.output)
    else:
        assert path.name in result.output
        _assert_text_diff_output_absent(result.output)


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


def test_strip_diff_summary_output_suppresses_empty_diff_section(tmp_path: Path) -> None:
    """TEXT summary output should omit diff fences when no strip diff exists."""
    path: Path = _write_plain_python_file(tmp_path)

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

    assert_SUCCESS(result)
    assert_rich_output_does_not_contain(
        output=result.output,
        expected="diffs - start",
    )
    assert_rich_output_does_not_contain(
        output=result.output,
        expected="diffs - end",
    )


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


def test_strip_diff_markdown_summary_output_suppresses_empty_diff_section(
    tmp_path: Path,
) -> None:
    """Markdown summary output should omit `## Diffs` when no strip diff exists."""
    path: Path = _write_plain_python_file(tmp_path)

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

    assert_SUCCESS(result)
    assert_markdown_output_does_not_contain(
        output=result.output,
        expected="## Diffs",
    )
    assert_markdown_output_does_not_contain(
        output=result.output,
        expected="```diff",
    )


@pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
    ],
)
def test_strip_apply_summary_output_reports_removed_file(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """`strip --apply --summary` should report the removed summary bucket."""
    path: Path = _write_markdown_file_with_topmark_header(tmp_path)

    args: list[str] = [
        CliCmd.STRIP,
        CliOpt.APPLY_CHANGES,
        CliOpt.RESULTS_SUMMARY_MODE,
    ]
    if output_format is OutputFormat.MARKDOWN:
        args.extend([CliOpt.OUTPUT_FORMAT, output_format.value])
    args.append(str(path))

    result: Result = run_cli_in(tmp_path, args, prune_views=True)

    assert_SUCCESS(result)
    updated: str = path.read_text(encoding="utf-8")
    assert TOPMARK_START_MARKER not in updated
    assert_human_output_contains(
        output_format=output_format,
        output=result.output,
        expected="stripped",
    )


@pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
    ],
)
def test_strip_diff_per_file_output_suppresses_empty_diff_section(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """`strip --diff` per-file output should omit diff sections without a diff."""
    path: Path = _write_plain_python_file(tmp_path)

    args: list[str] = [
        CliCmd.STRIP,
        CliOpt.RENDER_DIFF,
        CliOpt.REPORT,
        "all",
    ]
    if output_format is OutputFormat.MARKDOWN:
        args.extend([CliOpt.OUTPUT_FORMAT, output_format.value])
    args.append(str(path))

    result: Result = run_cli_in(tmp_path, args, prune_views=True)

    assert_SUCCESS(result)
    if output_format is OutputFormat.MARKDOWN:
        assert "# TopMark" in result.output
        _assert_markdown_diff_output_absent(result.output)
    else:
        assert path.name in result.output
        _assert_text_diff_output_absent(result.output)
