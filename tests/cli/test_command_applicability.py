# topmark:header:start
#
#   project      : TopMark
#   file         : test_command_applicability.py
#   file_relpath : tests/cli/test_command_applicability.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI command-specific option applicability tests.

These tests intentionally import the production applicability groups so every
centralized forbidden option remains covered. Argument values stay local to the
test module because they are test fixtures, not CLI metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_FILE_NOT_FOUND
from tests.cli.conftest import assert_rich_output_does_not_contain
from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.option_groups import PROBE_FORBIDDEN_OPTIONS
from topmark.cli.option_groups import STRIP_FORBIDDEN_OPTIONS
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

_STDIN_FLAG: str = "--stdin"
_STDIN_FILENAME: str = CliOpt.STDIN_FILENAME


# Values used when exercising option spellings that require an argument. Keep
# these local to the tests: production applicability metadata should describe
# whether an option applies to a command, not how a test should invoke it.
_OPTION_VALUES: dict[str, str | None] = {
    CliOpt.APPLY_CHANGES: None,
    CliOpt.WRITE_MODE: "stdout",
    CliOpt.RENDER_DIFF: None,
    # --summary is a flag, takes no argv:
    CliOpt.RESULTS_SUMMARY_MODE: None,
    CliOpt.REPORT: ReportScope.ALL,
    # Valid: "all", "add-only", "update-only":
    CliOpt.POLICY_HEADER_MUTATION_MODE: "update-only",
    # Valid: "reject", "remove-bom":
    CliOpt.POLICY_BOM_BEFORE_SHEBANG: "remove-bom",
    CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES: None,
    CliOpt.POLICY_NO_ALLOW_HEADER_IN_EMPTY_FILES: None,
    # Valid: "bytes-empty", "logical-empty", "whitespace-empty":
    CliOpt.POLICY_EMPTY_INSERT_MODE: "logical-empty",
    CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS: None,
    CliOpt.POLICY_NO_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS: None,
    CliOpt.POLICY_ALLOW_REFLOW: None,
    CliOpt.POLICY_NO_ALLOW_REFLOW: None,
    CliOpt.HEADER_FIELDS: "project,file",
    CliOpt.FIELD_VALUES: "project=TopMark",
    CliOpt.ALIGN_FIELDS: None,
    CliOpt.NO_ALIGN_FIELDS: None,
    CliOpt.RELATIVE_TO: ".",
}


@pytest.mark.parametrize(
    ("option", "value"),
    [(option, _OPTION_VALUES[option]) for option in PROBE_FORBIDDEN_OPTIONS],
)
def test_probe_rejects_inapplicable_path_command_options(
    option: str,
    value: str | None,
) -> None:
    """`probe` leaves inapplicable options to Click parser handling."""
    argv: list[str] = [CliCmd.PROBE, option]
    if value is not None:
        argv.append(value)

    result: Result = run_cli(argv)

    assert_rich_output_no_such_option(result, option_name=option)


def test_probe_rejects_inapplicable_option_assignment_form() -> None:
    """Click rejects `--option=value` spellings for inapplicable options."""
    result: Result = run_cli(
        [
            CliCmd.PROBE,
            f"{CliOpt.WRITE_MODE}=stdout",
        ]
    )

    assert_rich_output_no_such_option(result, option_name=CliOpt.WRITE_MODE)


@pytest.mark.parametrize(
    ("option", "value"),
    [(option, _OPTION_VALUES[option]) for option in STRIP_FORBIDDEN_OPTIONS],
)
def test_strip_rejects_generated_header_options(
    option: str,
    value: str | None,
) -> None:
    """`strip` leaves check-only options to Click parser handling."""
    argv: list[str] = [CliCmd.STRIP, option]
    if value is not None:
        argv.append(value)

    result: Result = run_cli(argv)

    assert_rich_output_no_such_option(result, option_name=option)


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_reject_stdin_flag(command: str) -> None:
    """Path commands reject `--stdin` at Click parser level."""
    result: Result = run_cli(
        [
            command,
            _STDIN_FLAG,
            _STDIN_FILENAME,
            "file.py",
        ]
    )

    assert_rich_output_no_such_option(result, option_name=_STDIN_FLAG)


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_reject_stdin_flag_assignment_form(command: str) -> None:
    """`--stdin=value` is rejected at Click parser level."""
    result: Result = run_cli(
        [
            command,
            f"{_STDIN_FLAG}=true",
            _STDIN_FILENAME,
            "file.py",
        ]
    )

    assert_rich_output_no_such_option(result, option_name=_STDIN_FLAG)


def test_probe_rejects_first_inapplicable_option_when_multiple_are_present() -> None:
    """`probe` should fail deterministically on the first unsupported option."""
    result: Result = run_cli(
        [
            CliCmd.PROBE,
            CliOpt.REPORT,
            ReportScope.ALL,
            CliOpt.RENDER_DIFF,
        ]
    )

    assert_rich_output_no_such_option(result, option_name=CliOpt.REPORT)


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_reject_existing_dash_prefixed_paths_before_delimiter(
    command: str,
    tmp_path: Path,
) -> None:
    """Dash-prefixed paths before `--` are parsed as unsupported options."""
    path: Path = tmp_path / "--foo.py"
    path.write_text("print('hello')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            "--foo.py",
        ],
    )

    assert_rich_output_no_such_option(result, option_name="--foo.py")


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_accept_existing_dash_prefixed_paths_after_delimiter(
    command: str,
    tmp_path: Path,
) -> None:
    """Literal dash-prefixed paths require the standard `--` delimiter."""
    path: Path = tmp_path / "--foo.py"
    path.write_text("print('hello')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            "--",
            "--foo.py",
        ],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)
    assert_rich_output_does_not_contain(
        result.output,
        expected="No such option",
    )


def test_check_accepts_content_stdin_sentinel() -> None:
    """`check` must continue accepting '-' as the content-STDIN sentinel."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            "-",
            _STDIN_FILENAME,
            "file.py",
        ],
        input_text="print('hello')\n",
    )

    assert_WOULD_CHANGE(result)
    assert_rich_output_does_not_contain(
        result.output,
        expected="Usage:",
    )
    assert_rich_output_does_not_contain(
        result.output,
        expected=f"option {_STDIN_FLAG} is not supported.",
    )


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_do_not_reject_literal_stdin_named_path(command: str) -> None:
    """Only the `--stdin` option spelling is forbidden, not similarly named paths."""
    result: Result = run_cli(
        [
            command,
            "./--stdin",
        ]
    )

    assert_FILE_NOT_FOUND(result)
    assert_rich_output_does_not_contain(
        result.output,
        expected=f"option {_STDIN_FLAG} is not supported.",
    )
