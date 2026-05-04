# topmark:header:start
#
#   project      : TopMark
#   file         : test_command_applicability.py
#   file_relpath : tests/cli/test_command_applicability.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI command-specific option applicability tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result

_STDIN_FLAG: str = "--stdin"
_STDIN_FILENAME: str = CliOpt.STDIN_FILENAME
_STDIN_GUIDANCE: str = "Use '-' with '--stdin-filename' to read one file's content from STDIN."
_CHECK_ONLY_REASON: str = "Use this only with `topmark check`."
_CHECK_STRIP_REASON: str = "Use this only with `topmark check` or `topmark strip`."


@pytest.mark.parametrize(
    ("option", "value", "reason"),
    [
        (CliOpt.APPLY_CHANGES, None, _CHECK_STRIP_REASON),
        (CliOpt.WRITE_MODE, "stdout", _CHECK_STRIP_REASON),
        (CliOpt.RENDER_DIFF, None, _CHECK_STRIP_REASON),
        (CliOpt.RESULTS_SUMMARY_MODE, "compact", _CHECK_STRIP_REASON),
        (CliOpt.REPORT, "all", _CHECK_STRIP_REASON),
        (CliOpt.POLICY_HEADER_MUTATION_MODE, "replace", _CHECK_ONLY_REASON),
        (CliOpt.HEADER_FIELDS, "project,file", _CHECK_ONLY_REASON),
        (CliOpt.FIELD_VALUES, "project=TopMark", _CHECK_ONLY_REASON),
        (CliOpt.ALIGN_FIELDS, None, _CHECK_ONLY_REASON),
        (CliOpt.NO_ALIGN_FIELDS, None, _CHECK_ONLY_REASON),
        (CliOpt.RELATIVE_TO, "cwd", _CHECK_ONLY_REASON),
    ],
)
def test_probe_rejects_inapplicable_path_command_options(
    option: str,
    value: str | None,
    reason: str,
) -> None:
    """`probe` must reject known check/strip options before input planning."""
    argv: list[str] = [CliCmd.PROBE, option]
    if value is not None:
        argv.append(value)

    result: Result = run_cli(argv)

    assert_USAGE_ERROR(result)
    assert f"Option '{option}' is not supported for" in result.output
    assert CliCmd.PROBE in result.output
    assert reason in result.output


def test_probe_rejects_inapplicable_option_assignment_form() -> None:
    """Forbidden-option validation must catch `--option=value` spellings."""
    result: Result = run_cli(
        [
            CliCmd.PROBE,
            f"{CliOpt.WRITE_MODE}=stdout",
        ]
    )

    assert_USAGE_ERROR(result)
    assert f"Option '{CliOpt.WRITE_MODE}' is not supported for" in result.output
    assert CliCmd.PROBE in result.output
    assert _CHECK_STRIP_REASON in result.output


@pytest.mark.parametrize(
    ("option", "value"),
    [
        (CliOpt.POLICY_HEADER_MUTATION_MODE, "replace"),
        (CliOpt.HEADER_FIELDS, "project,file"),
        (CliOpt.FIELD_VALUES, "project=TopMark"),
        (CliOpt.ALIGN_FIELDS, None),
        (CliOpt.NO_ALIGN_FIELDS, None),
        (CliOpt.RELATIVE_TO, "cwd"),
    ],
)
def test_strip_rejects_generated_header_options(
    option: str,
    value: str | None,
) -> None:
    """`strip` must reject check-only generated-header controls."""
    argv: list[str] = [CliCmd.STRIP, option]
    if value is not None:
        argv.append(value)

    result: Result = run_cli(argv)

    assert_USAGE_ERROR(result)
    assert f"Option '{option}' is not supported for" in result.output
    assert CliCmd.STRIP in result.output
    assert _CHECK_ONLY_REASON in result.output


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
    assert f"Option '{_STDIN_FLAG}' is not supported for" in result.output
    assert command in result.output
    assert _STDIN_GUIDANCE in result.output


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
    assert f"Option '{_STDIN_FLAG}' is not supported for" in result.output
    assert command in result.output
    assert _STDIN_GUIDANCE in result.output


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
    assert f"Option '{CliOpt.RENDER_DIFF}' is not supported for" in result.output
    assert CliCmd.PROBE in result.output
    assert _CHECK_STRIP_REASON in result.output


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

    assert "Usage:" not in result.output
    assert f"Option '{_STDIN_FLAG}' is not supported" not in result.output


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

    assert f"Option '{_STDIN_FLAG}' is not supported" not in result.output
