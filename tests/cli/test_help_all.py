# topmark:header:start
#
#   project      : TopMark
#   file         : test_help_all.py
#   file_relpath : tests/cli/test_help_all.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI help-output smoke tests.

This module verifies that the top-level CLI and all public command paths expose
a working `--help` page and exit successfully.

These tests are broad command-surface smoke tests, not detailed content checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

from click.testing import Result

from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result

PUBLIC_HELP_COMMAND_PATHS: Final[tuple[tuple[str, ...], ...]] = (
    (CliCmd.PROBE,),
    (CliCmd.CHECK,),
    (CliCmd.STRIP,),
    (CliCmd.CONFIG,),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_CHECK,
    ),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_INIT,
    ),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_DEFAULTS,
    ),
    (
        CliCmd.CONFIG,
        CliCmd.CONFIG_DUMP,
    ),
    (CliCmd.REGISTRY,),
    (
        CliCmd.REGISTRY,
        CliCmd.REGISTRY_FILETYPES,
    ),
    (
        CliCmd.REGISTRY,
        CliCmd.REGISTRY_PROCESSORS,
    ),
    (
        CliCmd.REGISTRY,
        CliCmd.REGISTRY_BINDINGS,
    ),
    (CliCmd.VERSION,),
)


# --- Top-level help ---


def test_top_level_help_exits_success() -> None:
    """`topmark --help` should exit SUCCESS."""
    result: Result = run_cli(
        [CliOpt.HELP],
    )

    assert_SUCCESS(result)
    assert_rich_output_contains(
        result.output,
        expected="Usage:",
    )


# --- Public command help pages ---


def test_each_public_command_path_has_help() -> None:
    """Every public command path should expose a working `--help` page."""
    for command_path in PUBLIC_HELP_COMMAND_PATHS:
        result: Result = run_cli(
            command_path + (CliOpt.HELP,),
        )

        assert_SUCCESS(result)
        assert_rich_output_contains(
            result.output,
            expected="Usage:",
        )


def test_config_dump_help_listed_paths_noop() -> None:
    """Listed paths do not affect the dumped configuration."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.HELP,
        ]
    )

    assert_rich_output_contains(
        result.output,
        expected="Listed paths do not affect the dumped configuration.",
    )
