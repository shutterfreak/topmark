# topmark:header:start
#
#   project      : TopMark
#   file         : test_filetypes.py
#   file_relpath : tests/cli/test_filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: `filetypes` command output.

Ensures that invoking `topmark filetypes` exits successfully and produces
non-empty output, typically including the phrase "Supported file types".
"""

from tests.cli.conftest import assert_SUCCESS, run_cli


def test_filetypes_lists_known_types() -> None:
    """It should list supported file types and exit with code 0."""
    result = run_cli(["filetypes"])

    assert_SUCCESS(result)

    assert "Supported file types" in result.output or result.output.strip() != ""
