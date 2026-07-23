# topmark:header:start
#
#   project      : TopMark
#   file         : test_finite_choice_options.py
#   file_relpath : tests/cli/test_finite_choice_options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""End-to-end contracts for finite-choice CLI option spelling."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import pytest
from click.testing import CliRunner

from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_rich_output_does_not_contain
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from topmark.cli.cli_types import CliWriteMode
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import common_apply_and_write_options

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_finite_choice_help_lists_lowercase_canonical_values(
    tmp_path: Path,
) -> None:
    """Help should display the accepted lowercase vocabulary."""
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert_rich_output_contains(
        result.output,
        expected="Accepted values: 'auto' (default), 'always', 'never'.",
    )
    assert_rich_output_contains(
        result.output,
        expected="Accepted values: 'text' (default), 'markdown', 'json', 'ndjson'.",
    )
    assert_rich_output_contains(
        result.output,
        expected="Accepted values: 'actionable' (default), 'noncompliant', 'all'.",
    )
    assert_rich_output_contains(result.output, expected="Select write strategy:")
    for write_mode in ("'atomic'", "'inplace'", "'stdout'"):
        assert write_mode in result.output
    assert_rich_output_contains(
        result.output,
        expected="--header-mutation-mode=add-only",
    )
    assert_rich_output_does_not_contain(
        result.output,
        expected="--header-mutation-mode=add_only",
    )


def test_write_mode_callback_receives_private_cli_enum() -> None:
    """The shared production decorator should expose a typed callback value."""
    observed: list[CliWriteMode | None] = []

    @click.command()
    @common_apply_and_write_options
    def command(apply_changes: bool, write_mode: CliWriteMode | None) -> None:
        _ = apply_changes
        observed.append(write_mode)

    result: Result = CliRunner().invoke(
        command,
        [
            CliOpt.WRITE_MODE,
            "inplace",
        ],
    )

    assert result.exit_code == 0
    assert observed == [CliWriteMode.INPLACE]


@pytest.mark.parametrize(
    ("option", "value"),
    [
        pytest.param(CliOpt.COLOR_MODE, "auto", id="color-auto"),
        pytest.param(CliOpt.COLOR_MODE, "always", id="color-always"),
        pytest.param(CliOpt.COLOR_MODE, "never", id="color-never"),
        pytest.param(CliOpt.OUTPUT_FORMAT, "text", id="format-text"),
        pytest.param(CliOpt.OUTPUT_FORMAT, "markdown", id="format-markdown"),
        pytest.param(CliOpt.OUTPUT_FORMAT, "json", id="format-json"),
        pytest.param(CliOpt.OUTPUT_FORMAT, "ndjson", id="format-ndjson"),
        pytest.param(CliOpt.REPORT, "actionable", id="report-actionable"),
        pytest.param(CliOpt.REPORT, "noncompliant", id="report-noncompliant"),
        pytest.param(CliOpt.REPORT, "all", id="report-all"),
        pytest.param(CliOpt.WRITE_MODE, "atomic", id="write-atomic"),
        pytest.param(CliOpt.WRITE_MODE, "inplace", id="write-inplace"),
        pytest.param(CliOpt.WRITE_MODE, "stdout", id="write-stdout"),
    ],
)
def test_single_word_finite_choices_accept_exact_lowercase(
    tmp_path: Path,
    option: str,
    value: str,
) -> None:
    """Every single-word production choice should accept its documented spelling."""
    target: Path = tmp_path / "MixedCaseFilename.py"
    target.write_text("print('ok')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            option,
            value,
            target.name,
        ],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)


@pytest.mark.parametrize(
    "assignment_form",
    [False, True],
    ids=["spaced", "assignment"],
)
@pytest.mark.parametrize(
    ("option", "invalid_value", "canonical_value", "choice_listing"),
    [
        pytest.param(
            CliOpt.COLOR_MODE,
            "ALWAYS",
            "always",
            "auto, always, never",
            id="color-uppercase",
        ),
        pytest.param(
            CliOpt.COLOR_MODE,
            "Always",
            "always",
            "auto, always, never",
            id="color-mixed-case",
        ),
        pytest.param(
            CliOpt.OUTPUT_FORMAT,
            "JSON",
            "json",
            "text, markdown, json, ndjson",
            id="format-uppercase",
        ),
        pytest.param(
            CliOpt.OUTPUT_FORMAT,
            "Json",
            "json",
            "text, markdown, json, ndjson",
            id="format-mixed-case",
        ),
        pytest.param(
            CliOpt.REPORT,
            "ACTIONABLE",
            "actionable",
            "actionable, noncompliant, all",
            id="report-uppercase",
        ),
        pytest.param(
            CliOpt.REPORT,
            "Actionable",
            "actionable",
            "actionable, noncompliant, all",
            id="report-mixed-case",
        ),
        pytest.param(
            CliOpt.WRITE_MODE,
            "INPLACE",
            "inplace",
            "atomic, inplace, stdout",
            id="write-uppercase",
        ),
        pytest.param(
            CliOpt.WRITE_MODE,
            "Inplace",
            "inplace",
            "atomic, inplace, stdout",
            id="write-mixed-case",
        ),
    ],
)
def test_single_word_finite_choices_reject_non_lowercase(
    tmp_path: Path,
    option: str,
    invalid_value: str,
    canonical_value: str,
    choice_listing: str,
    *,
    assignment_form: bool,
) -> None:
    """Case variants should fail through Click with lowercase canonical choices."""
    target: Path = tmp_path / "MixedCaseFilename.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    option_args: list[str] = (
        [f"{option}={invalid_value}"] if assignment_form else [option, invalid_value]
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            *option_args,
            target.name,
        ],
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    assert_rich_output_contains(result.stderr, expected="Usage: cli check")
    assert_rich_output_contains(result.stderr, expected=f"Invalid value for '{option}'")
    assert_rich_output_contains(result.stderr, expected=f"Invalid value '{invalid_value}'")
    assert_rich_output_contains(result.stderr, expected=f"Did you mean '{canonical_value}'?")
    assert_rich_output_contains(result.stderr, expected=f"Must be one of: {choice_listing}")
