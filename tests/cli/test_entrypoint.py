# topmark:header:start
#
#   project      : TopMark
#   file         : test_entrypoint.py
#   file_relpath : tests/cli/test_entrypoint.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI entry-point contract tests for TopMark.

These tests provide minimal coverage that the CLI entry point is callable and
that basic informational commands succeed:
- `--help` renders usage information,
- `version` prints the project version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_VERSION

if TYPE_CHECKING:
    from click.testing import Result


@pytest.mark.smoke
def test_cli_help_outputs_usage_and_exits_success() -> None:
    """`--help` should render usage information and exit SUCCESS."""
    result: Result = run_cli([CliOpt.HELP])

    assert_SUCCESS(result)

    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="Usage",
    )


@pytest.mark.smoke
def test_cli_version_outputs_project_version() -> None:
    """`version` should print the project version and exit SUCCESS."""
    result: Result = run_cli([CliCmd.VERSION])

    assert_SUCCESS(result)

    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected=TOPMARK_VERSION,
    )
