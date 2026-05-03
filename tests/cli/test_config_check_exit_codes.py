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
- warning-only diagnostics exit FAILURE (1) in strict mode,
- malformed/unusable configuration exits FAILURE (1) as a validation result.

Unlike processing commands, `config check` reports configuration problems as
validation results rather than runtime `CONFIG_ERROR` exits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_FAILURE
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

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
    """Warning-only diagnostics should exit FAILURE in strict mode."""
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
            CliOpt.STRICT_CONFIG_CHECKING,
        ],
    )

    # Strict config checking escalates warning-only diagnostics to validation failure.
    assert_FAILURE(result)


# --- Malformed / unusable configuration ---


def test_config_check_malformed_config_exits_failure(tmp_path: Path) -> None:
    """Malformed config should exit FAILURE as a validation result."""
    (tmp_path / "topmark.toml").write_text("this = [[[[ not_toml", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
        ],
    )

    # `config check` reports TOML parse errors as validation failures.
    assert_FAILURE(result)
