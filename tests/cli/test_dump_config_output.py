# topmark:header:start
#
#   file         : test_dump_config_output.py
#   file_relpath : tests/cli/test_dump_config_output.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: `dump-config` command output validity.

Ensures that running `topmark dump-config`:

- Exits successfully (exit code 0).
- Prints markers `# === BEGIN ===` and `# === END ===`.
- Produces a valid TOML snippet between markers that can be parsed by `tomllib`.
"""

from typing import cast

import click
import tomlkit
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_dump_config_outputs_valid_toml() -> None:
    """It should emit valid TOML wrapped in BEGIN/END markers and parse successfully."""
    result = CliRunner().invoke(cli, ["dump-config"])

    assert result.exit_code == ExitCode.SUCCESS, result.output

    assert "# === BEGIN ===" in result.output

    # Extract the TOML slice
    start = result.output.find("# === BEGIN ===")
    end = result.output.find("# === END ===")
    toml_text = result.output[start:end].splitlines()[1:]  # drop marker line
    parsed = tomlkit.parse("\n".join(toml_text))
    assert "fields" in parsed

    assert "header" in parsed
