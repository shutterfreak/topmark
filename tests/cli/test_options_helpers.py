# topmark:header:start
#
#   project      : TopMark
#   file         : test_options_helpers.py
#   file_relpath : tests/cli/test_options_helpers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for reusable CLI option parsing and validation helpers."""

from __future__ import annotations

from enum import Enum

import click
import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from topmark.cli.errors import TopmarkCliUsageError
from topmark.cli.keys import CliOpt
from topmark.cli.options import FromOptionStdinText
from topmark.cli.options import FromOptionValues
from topmark.cli.options import common_file_type_filtering_options
from topmark.cli.options import common_header_field_options
from topmark.cli.options import enum_value_help_text
from topmark.cli.options import extend_with_stdin_lines
from topmark.cli.options import extract_stdin_for_from_options
from topmark.cli.options import option_with_hidden_aliases_and_underscore_traps
from topmark.cli.options import option_with_underscore_traps
from topmark.cli.options import split_nonempty_lines
from topmark.cli.options import strip_dash_sentinels
from topmark.cli.validators import validate_mutually_exclusive
from topmark.core.keys import ArgKey


class _OutputMode(Enum):
    """Small enum used to exercise CLI help text rendering."""

    TEXT = "text"
    MACHINE_READABLE = "machine_readable"


def test_split_nonempty_lines_ignores_blank_and_comment_lines() -> None:
    """Split helper should ignore blank lines and comment-only lines."""
    assert split_nonempty_lines("one\n\n# comment\n two \n") == ["one", "two"]


def test_extend_with_stdin_lines_extends_existing_target() -> None:
    """STDIN line helper should append parsed lines to the existing list."""
    target: list[str] = ["existing"]

    result: list[str] = extend_with_stdin_lines(target, "one\n# comment\ntwo\n")

    assert result is target
    assert target == ["existing", "one", "two"]


@pytest.mark.parametrize(
    "stdin_text",
    [
        pytest.param(None, id="none"),
        pytest.param("", id="empty-string"),
    ],
)
def test_extend_with_stdin_lines_ignores_falsy_stdin_text(
    stdin_text: str | None,
) -> None:
    """Falsy STDIN text should leave the target list unchanged."""
    target: list[str] = ["existing"]

    result: list[str] = extend_with_stdin_lines(target, stdin_text)

    assert result is target
    assert target == ["existing"]


def test_strip_dash_sentinels_removes_stdin_markers() -> None:
    """Dash sentinels should be removed from all --*-from values."""
    result: FromOptionValues = strip_dash_sentinels(
        files_from=("files.txt", "-"),
        include_from=("-", "src/**"),
        exclude_from=("build/**", "-"),
    )

    assert result.files_from == ["files.txt"]
    assert result.include_from == ["src/**"]
    assert result.exclude_from == ["build/**"]


def test_extract_stdin_for_from_options_routes_files_from_stdin_text() -> None:
    """A single --files-from dash should receive the provided STDIN text."""
    result: FromOptionStdinText = extract_stdin_for_from_options(
        files_from=("-",),
        include_from=(),
        exclude_from=(),
        stdin_text="README.md\n",
    )

    assert result.files_from == "README.md\n"
    assert result.include_from is None
    assert result.exclude_from is None


def test_extract_stdin_for_from_options_rejects_multiple_stdin_consumers() -> None:
    """Only one --*-from option may consume STDIN."""
    with pytest.raises(TopmarkCliUsageError, match="Only one of"):
        extract_stdin_for_from_options(
            files_from=("-",),
            include_from=("-",),
            exclude_from=(),
            stdin_text="README.md\n",
        )


def test_option_with_underscore_traps_delegates_non_long_options() -> None:
    """Options without long hyphenated spellings should use Click unchanged."""

    @click.command()
    @option_with_underscore_traps("-i", "include_from", is_flag=True)
    def command(include_from: bool) -> None:
        click.echo("enabled" if include_from else "disabled")

    runner = CliRunner()
    result: Result = runner.invoke(command, ["-i"])

    assert_SUCCESS(result)
    assert result.output == "enabled\n"


def test_option_with_underscore_traps_rejects_underscored_spelling() -> None:
    """Underscored long options should raise Click's normal unknown-option error."""
    valid_option: str = CliOpt.INCLUDE_FROM
    destination_name: str = ArgKey.INCLUDE_FROM

    # Preserve the long-option prefix; replace hyphens only in the option name.
    trapped_option: str = f"--{valid_option.removeprefix('--').replace('-', '_')}"

    @click.command()
    @option_with_underscore_traps(valid_option, destination_name)
    def command(include_from: str | None) -> None:
        click.echo(include_from or "none")

    runner = CliRunner()
    result: Result = runner.invoke(command, [trapped_option, "patterns.txt"])

    assert_rich_output_no_such_option(
        result,
        option_name=trapped_option,
        valid_option_name=valid_option,
    )


def test_option_with_hidden_aliases_requires_explicit_destination() -> None:
    """Hidden alias options should fail fast without an explicit destination name."""
    with pytest.raises(ValueError, match="explicit destination"):
        option_with_hidden_aliases_and_underscore_traps(
            CliOpt.INCLUDE_FILE_TYPES,
            hidden_aliases=(CliOpt.INCLUDE_FILE_TYPE,),
        )


def test_enum_value_help_text_marks_raw_string_default_and_boundary_spellings() -> None:
    """Enum help text should distinguish CLI and non-CLI value spellings."""
    assert enum_value_help_text(
        _OutputMode,
        default="machine_readable",
        suffix="Choose carefully.",
    ) == (
        "Accepted values: 'text', 'machine-readable' (default). "
        "Multiword CLI values require hyphens; config, API, and machine-readable output use "
        "underscore values (machine_readable). "
        "Choose carefully."
    )


def test_common_file_type_filtering_options_accept_csv_and_hidden_aliases() -> None:
    """File type filters should accept comma lists and hidden singular aliases."""

    @click.command()
    @common_file_type_filtering_options
    def command(
        include_file_types: tuple[str, ...],
        exclude_file_types: tuple[str, ...],
    ) -> None:
        click.echo(",".join(include_file_types) + "|" + ",".join(exclude_file_types))

    runner = CliRunner()
    result: Result = runner.invoke(
        command,
        [
            CliOpt.INCLUDE_FILE_TYPES,
            "python,, toml",
            CliOpt.INCLUDE_FILE_TYPE,
            "markdown",
            CliOpt.EXCLUDE_FILE_TYPES,
            "json,",
            CliOpt.EXCLUDE_FILE_TYPE,
            "xml",
        ],
    )

    assert_SUCCESS(result)
    assert result.output == "python,toml,markdown|json,xml\n"


def test_common_header_field_options_accepts_header_overrides() -> None:
    """Header field decorators should pass field-selection values to commands."""

    @click.command()
    @common_header_field_options
    def command(header_fields: str | None, field_values: str | None) -> None:
        click.echo(f"{header_fields}|{field_values}")

    runner = CliRunner()
    result: Result = runner.invoke(
        command,
        [
            CliOpt.HEADER_FIELDS,
            "file,license",
            CliOpt.FIELD_VALUES,
            "license=MIT",
        ],
    )

    assert_SUCCESS(result)
    assert result.output == "file,license|license=MIT\n"


def test_validate_mutually_exclusive_joins_two_options() -> None:
    """Mutual-exclusion diagnostics should join two enabled options with 'and'."""
    ctx = click.Context(click.Command("check"), info_name="topmark check")

    with pytest.raises(TopmarkCliUsageError, match="--one and --two are mutually exclusive"):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--one": True,
                "--two": True,
            },
        )


def test_validate_mutually_exclusive_joins_three_options() -> None:
    """Mutual-exclusion diagnostics should join three enabled options readably."""
    ctx = click.Context(click.Command("check"), info_name="topmark check")

    with pytest.raises(
        TopmarkCliUsageError,
        match="--one, --two, and --three are mutually exclusive",
    ):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--one": True,
                "--two": True,
                "--three": True,
            },
        )
