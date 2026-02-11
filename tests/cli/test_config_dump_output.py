# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_dump_output.py
#   file_relpath : tests/cli/test_config_dump_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: `dump-config` command output validity.

Ensures that running `topmark dump-config`:

- Exits successfully (exit code 0).
- Prints markers `TOML_BLOCK_START` and `TOML_BLOCK_END`.
- Produces a valid TOML snippet between markers that can be parsed by `tomllib`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError

from tests.cli.conftest import assert_SUCCESS, run_cli
from topmark.cli.keys import CliCmd, CliOpt
from topmark.constants import TOML_BLOCK_END, TOML_BLOCK_START

if TYPE_CHECKING:
    from click.testing import Result


def test_dump_config_outputs_valid_toml() -> None:
    """It should emit valid TOML wrapped in BEGIN/END markers and parse successfully."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_COLOR_MODE,  # Strip ANSI formatting to allow parsing the generated TOML
            CliOpt.VERBOSE,  # Render the BEGIN and END markers
        ]
    )

    assert_SUCCESS(result)

    assert TOML_BLOCK_START in result.output
    assert TOML_BLOCK_END in result.output

    # Extract the TOML slice
    start: int = result.output.find(TOML_BLOCK_START)
    end: int = result.output.find(TOML_BLOCK_END)
    toml_text: list[str] = result.output[start:end].splitlines()[1:]  # drop marker line
    try:
        parsed: tomlkit.TOMLDocument = tomlkit.loads("\n".join(toml_text))
        assert "fields" in parsed
        assert "header" in parsed
    except TypeError as e:
        # If an exception is caught, use pytest.fail() to fail the test explicitly.
        # You can include the exception details in the message for better debugging.
        pytest.fail(f"TypeError during TOML parsing: {e}")
    except TomlkitParseError as e:
        # Fail the test if the TOML decoding fails.
        pytest.fail(f"TomlDecodeError: {e}")
