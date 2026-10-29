# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_check_exit_codes.py
#   file_relpath : tests/cli/test_config_check_exit_codes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit-code contract tests for `topmark config check`.

This module pins the command-level validation contract:
- valid configuration exits SUCCESS (0),
- warning-only diagnostics exit SUCCESS (0) in non-strict mode,
- warning-only diagnostics exit CONFIG_ERROR (78) in strict mode,
- malformed/unusable configuration exits CONFIG_ERROR (78) as a validation result.

Unlike processing commands, `config check` reports configuration problems as
validation results rather than runtime `CONFIG_ERROR` exits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from topmark.cli.commands.config_check import config_check_command
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import as_object_dict

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

# All tests in this module pin configuration-check exit-code behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Valid configuration ---


def test_config_check_valid_config_exits_success() -> None:
    """`config check` should exit SUCCESS for the default effective config."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
        ]
    )

    assert_SUCCESS(result)


def test_config_check_context_invocation_without_argument_parsing() -> None:
    """Programmatic Click invocation validates config without argument parsing."""

    @click.command()
    @click.pass_context
    def invoke_config_check(ctx: click.Context) -> None:
        ctx.invoke(
            config_check_command,
            no_config=True,
            output_format=OutputFormat.JSON,
        )

    result: Result = CliRunner().invoke(invoke_config_check)

    assert_SUCCESS(result)
    payload: dict[str, object] = parse_json_object(result.stdout)
    assert as_object_dict(payload["config_check"])["ok"] is True
    assert as_object_dict(payload["config_diagnostics"])["diagnostics"] == []


# --- Warning-only diagnostics ---


def test_config_check_warning_only_config_exits_success_in_non_strict_mode(tmp_path: Path) -> None:
    """Warning-only diagnostics should exit SUCCESS in non-strict mode."""
    (tmp_path / "topmark.toml").write_text(
        "\n".join(
            [
                "[topmark]",
                "unknown_config_key = true",
                "",
            ]
        ),
        "utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
        ],
    )

    # Unknown keys are warning-only diagnostics and do not fail non-strict checks.
    assert_SUCCESS(result)


def test_config_check_warning_only_config_exits_failure_in_strict_mode(tmp_path: Path) -> None:
    """Warning-only diagnostics should exit CONFIG_ERROR in strict mode."""
    (tmp_path / "topmark.toml").write_text(
        "\n".join(
            [
                "[topmark]",
                "unknown_config_key = true",
                "",
            ]
        ),
        "utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.STRICT,
        ],
    )

    # Strict config checking escalates warning-only diagnostics to validation failure.
    assert_CONFIG_ERROR(result)


# --- Malformed / unusable configuration ---


def test_config_check_malformed_config_exits_failure(tmp_path: Path) -> None:
    """Malformed config should exit CONFIG_ERROR as a validation result."""
    (tmp_path / "topmark.toml").write_text("this = [[[[ not_toml", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
        ],
    )

    # `config check` reports TOML parse errors as validation failures.
    assert_CONFIG_ERROR(result)
