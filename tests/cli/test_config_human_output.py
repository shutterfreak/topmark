# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_human_output.py
#   file_relpath : tests/cli/test_config_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for human-facing config command output."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.conftest import parametrize
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result


pytestmark = pytest.mark.cli


@parametrize(
    "cmd",
    [
        CliCmd.CONFIG_CHECK,
        CliCmd.CONFIG_DUMP,
    ],
)
def test_config_status_or_inspection_commands_text_quiet_suppresses_output(cmd: str) -> None:
    """Config commands with useful silent status/inspection signals support `--quiet`."""
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


@parametrize(
    "cmd",
    [
        CliCmd.CONFIG_DEFAULTS,
        CliCmd.CONFIG_INIT,
    ],
)
def test_config_content_commands_reject_quiet_option(cmd: str) -> None:
    """Pure content-producing config commands do not support TEXT quiet suppression."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
        ]
    )

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert CliOpt.QUIET in result.output


@parametrize(
    "cmd",
    [
        CliCmd.CONFIG_CHECK,
        CliCmd.CONFIG_DUMP,
    ],
)
def test_config_status_or_inspection_commands_markdown_ignores_quiet(cmd: str) -> None:
    """Config Markdown output ignores TEXT-only quiet mode where `--quiet` is supported."""
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


@parametrize(
    "cmd",
    [
        CliCmd.CONFIG_DEFAULTS,
        CliCmd.CONFIG_INIT,
    ],
)
def test_config_content_commands_reject_quiet_option_with_markdown_output(cmd: str) -> None:
    """Config content commands reject `--quiet` even when Markdown output is requested."""
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

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert CliOpt.QUIET in result.output


@parametrize(
    "cmd",
    [
        CliCmd.CONFIG_CHECK,
        CliCmd.CONFIG_DEFAULTS,
        CliCmd.CONFIG_DUMP,
        CliCmd.CONFIG_INIT,
    ],
)
def test_config_commands_markdown_ignores_verbose(cmd: str) -> None:
    """Config Markdown output should ignore TEXT-only verbosity."""
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


def test_config_dump_text_verbose_adds_progressive_details() -> None:
    """TEXT verbosity should still control config dump progressive disclosure."""
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
    assert "Config files processed" in verbose.output


def test_config_dump_markdown_includes_document_sections_by_default() -> None:
    """Markdown config dump should include document sections without `-v`."""
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
    assert "Config files processed" in result.output
