# topmark:header:start
#
#   project      : TopMark
#   file         : test_help_all.py
#   file_relpath : tests/cli/test_help_all.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI help-output contract tests.

This module verifies that the root command and all public command paths expose
working rich-click help pages for the supported help invocation forms.

These tests protect broad command-surface behavior rather than detailed help
copy or formatting.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Final

import pytest

from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import normalize_rich_cli_output
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.keys import CliShortOpt

if TYPE_CHECKING:
    from click.testing import Result

PUBLIC_COMMAND_PATHS_WITH_HELP: Final[tuple[tuple[str, ...], ...]] = (
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


@pytest.mark.parametrize(
    "args",
    [
        pytest.param((), id="without-args"),
        pytest.param((CliOpt.HELP,), id="help-long"),
        pytest.param((CliShortOpt.HELP,), id="help-short"),
    ],
)
def test_root_help_invocations_exit_success(args: tuple[str, ...]) -> None:
    """The root command should render help for bare, long-help, and short-help forms."""
    result: Result = run_cli(args)

    assert_SUCCESS(result)
    assert_rich_output_contains(
        result.output,
        expected="Usage:",
    )


# --- Public command help pages ---


@pytest.mark.parametrize(
    "help_opt",
    [
        pytest.param(CliOpt.HELP, id="help-long"),
        pytest.param(CliShortOpt.HELP, id="help-short"),
    ],
)
def test_public_command_help_invocations_exit_success(
    help_opt: str,
) -> None:
    """Every public command path should support long and short help options."""
    for command_path in PUBLIC_COMMAND_PATHS_WITH_HELP:
        result: Result = run_cli(command_path + (help_opt,))

        assert_SUCCESS(result)
        assert_rich_output_contains(
            result.output,
            expected="Usage:",
        )


@pytest.mark.parametrize(
    "help_opt",
    [
        pytest.param(CliOpt.HELP, id="help-long"),
        pytest.param(CliShortOpt.HELP, id="help-short"),
    ],
)
def test_config_dump_help_documents_listed_paths_noop(
    help_opt: str,
) -> None:
    """`config dump --help` should document that listed paths are ignored."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            help_opt,
        ]
    )

    assert_rich_output_contains(
        result.output,
        expected="Listed paths do not affect the dumped configuration.",
    )


# ---- Test hidden aliases ----


@pytest.mark.parametrize(
    "cmd",
    [
        pytest.param(CliCmd.CHECK, id="check"),
        pytest.param(CliCmd.STRIP, id="strip"),
    ],
)
@pytest.mark.parametrize(
    "help_opt",
    [
        pytest.param(CliOpt.HELP, id="help-long"),
        pytest.param(CliShortOpt.HELP, id="help-short"),
    ],
)
def test_file_type_hidden_singular_aliases_are_not_shown_in_help(
    cmd: str,
    help_opt: str,
) -> None:
    """Hidden singular file type filter aliases are not shown in help."""
    result: Result = run_cli((cmd, help_opt))

    assert_SUCCESS(result)
    assert_rich_output_contains(result.output, expected=CliOpt.INCLUDE_FILE_TYPES)
    assert_rich_output_contains(result.output, expected=CliOpt.EXCLUDE_FILE_TYPES)

    # We cannot use `assert_rich_output_does_not_contain()` here since the hidden singular alias
    # is a substring of the canonical plural option name. We normalize the rich output by hand and
    # use a regular expression instead:
    normalized_output: str = normalize_rich_cli_output(result.output)
    assert (
        re.search(
            rf"{re.escape(CliOpt.INCLUDE_FILE_TYPE)}(?!s)(?:\s|,)",
            normalized_output,
        )
        is None
    )
    assert (
        re.search(
            rf"{re.escape(CliOpt.EXCLUDE_FILE_TYPE)}(?!s)(?:\s|,)",
            normalized_output,
        )
        is None
    )
