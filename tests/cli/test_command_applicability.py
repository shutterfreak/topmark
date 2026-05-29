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
from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_rich_output_does_not_contain
from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.option_groups import CHECK_ONLY_OPTION_REASON
from topmark.cli.option_groups import CHECK_OR_STRIP_ONLY_OPTION_REASON
from topmark.cli.option_groups import PROBE_FORBIDDEN_OPTIONS
from topmark.cli.option_groups import STRIP_FORBIDDEN_OPTIONS

if TYPE_CHECKING:
    from click.testing import Result

_STDIN_FLAG: str = "--stdin"
_STDIN_FILENAME: str = CliOpt.STDIN_FILENAME
_STDIN_GUIDANCE: str = "Use '-' with '--stdin-filename' to read one file's content from STDIN."


# Values used when exercising option spellings that require an argument. Keep
# these local to the tests: production applicability metadata should describe
# whether an option applies to a command, not how a test should invoke it.
_OPTION_VALUES: dict[str, str | None] = {
    CliOpt.APPLY_CHANGES: None,
    CliOpt.WRITE_MODE: "stdout",
    CliOpt.RENDER_DIFF: None,
    CliOpt.RESULTS_SUMMARY_MODE: "compact",
    CliOpt.REPORT: "all",
    CliOpt.POLICY_HEADER_MUTATION_MODE: "replace",
    CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES: None,
    CliOpt.POLICY_NO_ALLOW_HEADER_IN_EMPTY_FILES: None,
    CliOpt.POLICY_EMPTY_INSERT_MODE: "ignore",
    CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS: None,
    CliOpt.POLICY_NO_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS: None,
    CliOpt.POLICY_ALLOW_REFLOW: None,
    CliOpt.POLICY_NO_ALLOW_REFLOW: None,
    CliOpt.HEADER_FIELDS: "project,file",
    CliOpt.FIELD_VALUES: "project=TopMark",
    CliOpt.ALIGN_FIELDS: None,
    CliOpt.NO_ALIGN_FIELDS: None,
    CliOpt.RELATIVE_TO: "cwd",
}


@pytest.mark.parametrize(
    ("option", "value", "reason"),
    [
        (option, _OPTION_VALUES[option], reason)
        for option, reason in PROBE_FORBIDDEN_OPTIONS.items()
    ],
)
def test_probe_rejects_inapplicable_path_command_options(
    option: str,
    value: str | None,
    reason: str,
) -> None:
    """`probe` rejects every centralized check/strip-only option."""
    argv: list[str] = [CliCmd.PROBE, option]
    if value is not None:
        argv.append(value)

    result: Result = run_cli(argv)

    assert_USAGE_ERROR(result)
    assert_rich_output_contains(
        result.output,
        expected=f"option {option} is not supported.",
    )
    assert_rich_output_contains(
        result.output,
        expected=CliCmd.PROBE,
    )
    assert_rich_output_contains(
        result.output,
        expected=reason,
    )


def test_probe_rejects_inapplicable_option_assignment_form() -> None:
    """Forbidden-option validation must catch `--option=value` spellings."""
    result: Result = run_cli(
        [
            CliCmd.PROBE,
            f"{CliOpt.WRITE_MODE}=stdout",
        ]
    )

    assert_USAGE_ERROR(result)
    assert_rich_output_contains(
        result.output,
        expected=f"option {CliOpt.WRITE_MODE} is not supported.",
    )
    assert_rich_output_contains(
        result.output,
        expected=CliCmd.PROBE,
    )
    assert_rich_output_contains(
        result.output,
        expected=CHECK_OR_STRIP_ONLY_OPTION_REASON,
    )


@pytest.mark.parametrize(
    ("option", "value"),
    [(option, _OPTION_VALUES[option]) for option in STRIP_FORBIDDEN_OPTIONS],
)
def test_strip_rejects_generated_header_options(
    option: str,
    value: str | None,
) -> None:
    """`strip` rejects every centralized check-only generated-header option."""
    argv: list[str] = [CliCmd.STRIP, option]
    if value is not None:
        argv.append(value)

    result: Result = run_cli(argv)

    assert_USAGE_ERROR(result)
    assert_rich_output_contains(
        result.output,
        expected=f"option {option} is not supported.",
    )
    assert_rich_output_contains(
        result.output,
        expected=CliCmd.STRIP,
    )
    assert_rich_output_contains(
        result.output,
        expected=CHECK_ONLY_OPTION_REASON,
    )


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_reject_stdin_flag(command: str) -> None:
    """Path commands must reject `--stdin` and instruct to use '-'."""
    result: Result = run_cli(
        [
            command,
            _STDIN_FLAG,
            _STDIN_FILENAME,
            "file.py",
        ]
    )

    assert_USAGE_ERROR(result)
    assert_rich_output_contains(
        result.output,
        expected=f"option {_STDIN_FLAG} is not supported.",
    )
    assert_rich_output_contains(
        result.output,
        expected=command,
    )
    assert_rich_output_contains(
        result.output,
        expected=_STDIN_GUIDANCE,
    )


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
        CliCmd.PROBE,
    ],
)
def test_path_commands_reject_stdin_flag_assignment_form(command: str) -> None:
    """`--stdin=value` must also be rejected."""
    result: Result = run_cli(
        [
            command,
            f"{_STDIN_FLAG}=true",
            _STDIN_FILENAME,
            "file.py",
        ]
    )

    assert_USAGE_ERROR(result)
    assert_rich_output_contains(
        result.output,
        expected=f"option {_STDIN_FLAG} is not supported.",
    )
    assert_rich_output_contains(
        result.output,
        expected=command,
    )
    assert_rich_output_contains(
        result.output,
        expected=_STDIN_GUIDANCE,
    )


def test_probe_rejects_first_inapplicable_option_when_multiple_are_present() -> None:
    """`probe` should fail deterministically on the first known forbidden option."""
    result: Result = run_cli(
        [
            CliCmd.PROBE,
            CliOpt.REPORT,
            "all",
            CliOpt.RENDER_DIFF,
        ]
    )

    assert_USAGE_ERROR(result)
    assert_rich_output_contains(
        result.output,
        expected=f"option {CliOpt.RENDER_DIFF} is not supported.",
    )
    assert_rich_output_contains(
        result.output,
        expected=CliCmd.PROBE,
    )
    assert_rich_output_contains(
        result.output,
        expected=CHECK_OR_STRIP_ONLY_OPTION_REASON,
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
