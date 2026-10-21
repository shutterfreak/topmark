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
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

import click
import pytest
from rich.text import Text

from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import normalize_rich_cli_output
from tests.cli.conftest import run_cli
from topmark.cli.documentation import command_reference_url
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.keys import CliShortOpt
from topmark.cli.main import cli

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

COMMAND_REFERENCE_PATHS: Final[dict[tuple[str, ...], str]] = {
    (): "cli",
    (CliCmd.PROBE,): "commands/probe",
    (CliCmd.CHECK,): "commands/check",
    (CliCmd.STRIP,): "commands/strip",
    (CliCmd.CONFIG,): "commands/config",
    (CliCmd.CONFIG, CliCmd.CONFIG_CHECK): "commands/config/check",
    (CliCmd.CONFIG, CliCmd.CONFIG_INIT): "commands/config/init",
    (CliCmd.CONFIG, CliCmd.CONFIG_DEFAULTS): "commands/config/defaults",
    (CliCmd.CONFIG, CliCmd.CONFIG_DUMP): "commands/config/dump",
    (CliCmd.REGISTRY,): "commands/registry",
    (CliCmd.REGISTRY, CliCmd.REGISTRY_FILETYPES): "commands/registry/filetypes",
    (CliCmd.REGISTRY, CliCmd.REGISTRY_PROCESSORS): "commands/registry/processors",
    (CliCmd.REGISTRY, CliCmd.REGISTRY_BINDINGS): "commands/registry/bindings",
    (CliCmd.VERSION,): "commands/version",
}


def _command_epilog(command_path: tuple[str, ...]) -> Text:
    """Return the Rich epilog configured for a public command path."""
    command: click.Command = cli
    for command_name in command_path:
        assert isinstance(command, click.Group)
        child: click.Command | None = command.commands.get(command_name)
        assert child is not None, command_path
        command = child

    assert isinstance(command.epilog, Text)
    return command.epilog


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


def test_root_help_links_to_version_aware_reference() -> None:
    """Root help links to the version-aware CLI overview reference."""
    result: Result = run_cli((CliOpt.HELP,))

    assert_SUCCESS(result)
    assert_rich_output_contains(result.output, expected="Full reference:")
    expected_url: str = command_reference_url(COMMAND_REFERENCE_PATHS[()])
    assert expected_url in _command_epilog(()).plain


@pytest.mark.parametrize("reference_path", sorted(COMMAND_REFERENCE_PATHS.values()))
def test_command_reference_paths_match_documentation_sources(
    reference_path: str,
) -> None:
    """Every command-help reference path maps to a checked-in usage source page."""
    documentation_path: Path = Path(__file__).parents[2] / "docs" / "usage" / f"{reference_path}.md"

    assert documentation_path.is_file(), documentation_path


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


@pytest.mark.parametrize("command_path", PUBLIC_COMMAND_PATHS_WITH_HELP)
def test_public_command_help_links_to_version_aware_reference(
    command_path: tuple[str, ...],
) -> None:
    """Every public command help page links to its version-aware reference."""
    result: Result = run_cli(command_path + (CliOpt.HELP,))

    assert_SUCCESS(result)
    assert_rich_output_contains(result.output, expected="Full reference:")
    expected_url = command_reference_url(COMMAND_REFERENCE_PATHS[command_path])
    assert expected_url in _command_epilog(command_path).plain


@pytest.mark.smoke
def test_check_help_is_invariant_under_output_format() -> None:
    """`--output-format` does not change framework-generated command help."""
    default_help: Result = run_cli((CliCmd.CHECK, CliOpt.HELP))
    markdown_help: Result = run_cli((CliCmd.CHECK, CliOpt.OUTPUT_FORMAT, "markdown", CliOpt.HELP))

    assert_SUCCESS(default_help)
    assert_SUCCESS(markdown_help)
    assert markdown_help.output == default_help.output


@pytest.mark.parametrize(
    ("command", "expected_path_help"),
    [
        pytest.param(
            CliCmd.CHECK,
            "Files, directories, or glob patterns to inspect.",
            id="check",
        ),
        pytest.param(
            CliCmd.STRIP,
            "Files, directories, or glob patterns whose TopMark headers to remove.",
            id="strip",
        ),
        pytest.param(
            CliCmd.PROBE,
            "Files, directories, or glob patterns whose resolution to explain.",
            id="probe",
        ),
    ],
)
def test_processing_command_help_documents_paths_and_shared_controls(
    command: str,
    expected_path_help: str,
) -> None:
    """Processing-command help documents paths and shared input/output controls."""
    result: Result = run_cli((command, CliOpt.HELP))

    assert_SUCCESS(result)
    for expected in (
        expected_path_help,
        CliOpt.FILES_FROM,
        CliOpt.OUTPUT_FORMAT,
    ):
        assert_rich_output_contains(
            result.output,
            expected=expected,
        )


def test_check_help_documents_mutation_controls() -> None:
    """`check --help` documents its mutation policy and explicit apply control."""
    result: Result = run_cli((CliCmd.CHECK, CliOpt.HELP))

    assert_SUCCESS(result)
    assert_rich_output_contains(
        result.output,
        expected=CliOpt.POLICY_HEADER_MUTATION_MODE,
    )
    assert_rich_output_contains(
        result.output,
        expected=CliOpt.APPLY_CHANGES,
    )


def test_strip_help_documents_mutation_control() -> None:
    """`strip --help` documents its explicit apply control."""
    result: Result = run_cli((CliCmd.STRIP, CliOpt.HELP))

    assert_SUCCESS(result)
    assert_rich_output_contains(
        result.output,
        expected=CliOpt.APPLY_CHANGES,
    )


def test_probe_help_documents_resolution_control() -> None:
    """`probe --help` documents its content-probing resolution control."""
    result: Result = run_cli((CliCmd.PROBE, CliOpt.HELP))

    assert_SUCCESS(result)
    assert_rich_output_contains(
        result.output,
        expected=CliOpt.POLICY_ALLOW_CONTENT_PROBE,
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
    """Hidden singular file type aliases stay hidden in metadata and rendered help."""
    result: Result = run_cli((cmd, help_opt))

    assert_SUCCESS(result)
    command: click.Command | None = cli.get_command(
        click.Context(cli, info_name="topmark"),
        cmd_name=cmd,
    )
    assert command is not None
    context = click.Context(command)
    for canonical_option_name, hidden_alias_name in (
        (CliOpt.INCLUDE_FILE_TYPES, CliOpt.INCLUDE_FILE_TYPE),
        (CliOpt.EXCLUDE_FILE_TYPES, CliOpt.EXCLUDE_FILE_TYPE),
    ):
        options: list[click.Option] = [
            option for option in command.params if isinstance(option, click.Option)
        ]
        canonical_options: list[click.Option] = [
            option for option in options if canonical_option_name in option.opts
        ]
        hidden_alias_options: list[click.Option] = [
            option for option in options if hidden_alias_name in option.opts
        ]
        assert len(canonical_options) == 1
        assert canonical_options[0].get_help_record(context) is not None
        assert len(hidden_alias_options) == 1
        assert hidden_alias_options[0].hidden
        assert hidden_alias_options[0].get_help_record(context) is None

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
