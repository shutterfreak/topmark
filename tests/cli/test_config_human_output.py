# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_human_output.py
#   file_relpath : tests/cli/test_config_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI config command human-output behavior tests.

This module verifies output-control behavior for the `topmark config` command
family:
- quiet mode for status/inspection commands,
- rejection of quiet mode for pure content commands,
- Markdown output independence from TEXT-only quiet/verbosity controls,
- progressive disclosure for verbose TEXT output.

These are output-control tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result


pytestmark: pytest.MarkDecorator = pytest.mark.cli


# --- Quiet mode: TEXT output ---
@pytest.mark.parametrize(
    "cmd",
    [
        CliCmd.CONFIG_CHECK,
        CliCmd.CONFIG_DUMP,
    ],
)
def test_config_status_and_inspection_commands_text_quiet_suppress_output(cmd: str) -> None:
    """Status/inspection config commands should suppress TEXT output with `--quiet`."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
        ]
    )

    assert_SUCCESS(result)
    assert result.output == ""


@pytest.mark.parametrize(
    "cmd",
    [
        CliCmd.CONFIG_DEFAULTS,
        CliCmd.CONFIG_INIT,
    ],
)
def test_config_content_commands_reject_text_quiet_option(cmd: str) -> None:
    """Pure content-producing config commands should reject TEXT `--quiet`."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
        ]
    )

    assert_rich_output_no_such_option(
        result,
        option_name=CliOpt.QUIET,
    )


# --- Quiet mode: Markdown output ---
@pytest.mark.parametrize(
    "cmd",
    [
        CliCmd.CONFIG_CHECK,
        CliCmd.CONFIG_DUMP,
    ],
)
def test_config_status_and_inspection_commands_markdown_ignore_quiet(cmd: str) -> None:
    """Markdown output should ignore TEXT-only quiet mode where supported."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(result)
    assert result.output.strip() != ""


@pytest.mark.parametrize(
    "cmd",
    [
        CliCmd.CONFIG_DEFAULTS,
        CliCmd.CONFIG_INIT,
    ],
)
def test_config_content_commands_reject_quiet_option_with_markdown_output(cmd: str) -> None:
    """Pure content-producing config commands should reject `--quiet` for Markdown too."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_rich_output_no_such_option(
        result,
        option_name=CliOpt.QUIET,
    )


# --- Verbosity: Markdown output ---
@pytest.mark.parametrize(
    "cmd",
    [
        CliCmd.CONFIG_CHECK,
        CliCmd.CONFIG_DEFAULTS,
        CliCmd.CONFIG_DUMP,
        CliCmd.CONFIG_INIT,
    ],
)
def test_config_commands_markdown_ignores_verbose(cmd: str) -> None:
    """Markdown output should ignore TEXT-only verbosity for all config commands."""
    base: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )
    verbose: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(base)
    assert_SUCCESS(verbose)
    assert verbose.output == base.output


# --- Verbosity: TEXT output ---
def test_config_dump_text_verbose_adds_progressive_disclosure_details() -> None:
    """Verbose TEXT output should add config dump progressive-disclosure details."""
    base: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_COLOR_MODE,
        ]
    )
    verbose: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
        ]
    )

    assert_SUCCESS(base)
    assert_SUCCESS(verbose)
    assert verbose.output != base.output
    assert_human_output_contains(
        output_format=None,
        output=verbose.output,
        expected="Config files processed",
    )


# --- Markdown document content ---
def test_config_dump_markdown_includes_document_sections_by_default() -> None:
    """Markdown config dump should include document sections without verbosity."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="Config files processed",
    )
