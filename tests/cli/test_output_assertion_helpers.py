# topmark:header:start
#
#   project      : TopMark
#   file         : test_output_assertion_helpers.py
#   file_relpath : tests/cli/test_output_assertion_helpers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for CLI human-output assertion helpers.

The helpers intentionally normalize incidental Rich and Markdown rendering so
CLI regression tests can assert semantic output contracts without depending on
terminal width, ANSI styling, or panel borders.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_human_output_does_not_contain
from tests.cli.conftest import assert_markdown_output_contains
from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_rich_output_does_not_contain
from tests.cli.conftest import assert_strict_file_type_overlap_warning
from tests.cli.conftest import normalize_rich_cli_output
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat

pytestmark: pytest.MarkDecorator = pytest.mark.cli


def test_normalize_rich_cli_output_strips_ansi_panels_and_soft_wraps() -> None:
    """Rich normalization should preserve content while removing layout noise."""
    output: str = (
        "\x1b[31m╭─ Error ─╮\x1b[0m\n"
        "│ No such option '--include-file- │\n"
        "│ types'.                         │\n"
        "╰────────────╯\n"
    )

    assert normalize_rich_cli_output(output) == "No such option '--include-file-types'."


def test_rich_output_assertions_ignore_borders_wrapping_and_ansi() -> None:
    """Rich semantic assertions should tolerate terminal rendering differences."""
    output: str = (
        "\x1b[33m╭─ Warning ─╮\x1b[0m\n"
        "│ File types specified in both include and │\n"
        "│ exclude filters; exclusion wins.         │\n"
        "╰────────────╯\n"
    )

    assert_rich_output_contains(
        output,
        expected="File types specified in both include and exclude filters; exclusion wins.",
    )
    assert_rich_output_does_not_contain(output, expected="unrelated diagnostic")


def test_markdown_output_assertion_ignores_hard_line_break_markers() -> None:
    """Markdown semantic assertions should ignore layout-only hard breaks."""
    output: str = "# TopMark\\\n\nConfig files\\\nprocessed\n"

    assert_markdown_output_contains(output, expected="# TopMark Config files processed")


def test_human_output_facade_dispatches_by_format() -> None:
    """The format-aware helper should normalize TEXT and Markdown appropriately."""
    assert_human_output_contains(
        output_format=OutputFormat.TEXT,
        output="│ selected file │\n│ type          │\n",
        expected="selected file type",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output="## Files\\\n\nexample.py\n",
        expected="## Files example.py",
    )
    assert_human_output_does_not_contain(
        output_format=OutputFormat.TEXT,
        output="│ selected processor │\n",
        expected="selected file type",
    )


def test_strict_file_type_overlap_warning_assertion_is_layout_independent() -> None:
    """The strict overlap helper should tolerate Rich layout differences."""
    result = Result(
        runner=CliRunner(),
        output_bytes=(
            "\x1b[33m╭─ Warning ─╮\x1b[0m\n"
            "│ File types specified in both include and │\n"
            "│ exclude filters; exclusion wins:         │\n"
            "│ python, markdown                         │\n"
            "╰────────────╯\n"
        ).encode(),
        stdout_bytes=b"",
        stderr_bytes=b"",
        return_value=None,
        exit_code=ExitCode.CONFIG_ERROR,
        exception=None,
        exc_info=None,
    )

    assert_strict_file_type_overlap_warning(
        result,
        output_format=OutputFormat.TEXT,
        expected_removed_file_types=("python", "markdown"),
    )


def test_human_output_facade_rejects_machine_format() -> None:
    """The human-output facade should reject machine-readable formats."""
    with pytest.raises(ValueError, match="Invalid human output format"):
        assert_human_output_contains(
            output_format=OutputFormat.JSON,
            output='{"kind":"meta"}\n',
            expected="meta",
        )
