# topmark:header:start
#
#   project      : TopMark
#   file         : test_filetypes.py
#   file_relpath : tests/cli/test_filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI registry filetypes command tests.

This module verifies that the `topmark registry filetypes` command:
- executes successfully,
- produces non-empty output,
- exposes supported file-type information.

This is a behavior/output test rather than a strict exit-code contract test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd

if TYPE_CHECKING:
    from click.testing import Result


# --- Registry filetypes listing ---


def test_registry_filetypes_lists_supported_types() -> None:
    """`registry filetypes` should list supported file types and exit successfully."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
        ]
    )

    assert_SUCCESS(result)

    # Default TEXT output is compact and does not include the verbose heading.
    assert result.output.strip() != ""
    assert "topmark:" in result.output
