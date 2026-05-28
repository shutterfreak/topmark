# topmark:header:start
#
#   project      : TopMark
#   file         : test_logging_flags.py
#   file_relpath : tests/cli/test_logging_flags.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI logging/output-control flag tests.

This module verifies parsing and applicability of TEXT output-control flags:
- supported verbosity and quiet levels are accepted by commands that support them,
- verbosity and quiet flags are mutually exclusive.

These are CLI applicability tests rather than output rendering tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result


# --- Supported verbosity / quiet levels ---


@pytest.mark.parametrize("verbosity", ["-v", "-vv", "-vvv", "-q", "-qq", "-qqq"])
def test_config_check_accepts_supported_verbose_and_quiet_levels(verbosity: str) -> None:
    """`config check` should accept supported TEXT verbosity and quiet levels."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.NO_CONFIG,
            verbosity,
        ]
    )

    assert_SUCCESS(result)


# --- Mutually exclusive output controls ---


def test_config_check_rejects_combined_verbose_and_quiet_flags() -> None:
    """`config check` should reject combined verbose and quiet flags."""
    conflicting_invocations: tuple[list[str], ...] = (
        [CliCmd.CONFIG, CliCmd.CONFIG_CHECK, CliOpt.NO_CONFIG, "-v", "-q"],
        [CliCmd.CONFIG, CliCmd.CONFIG_CHECK, CliOpt.NO_CONFIG, "-q", "-v"],
    )
    for args in conflicting_invocations:
        result: Result = run_cli(args)
        assert_USAGE_ERROR(result)
        assert_rich_output_contains(
            result.output,
            expected="--verbose and --quiet are mutually exclusive",
        )
