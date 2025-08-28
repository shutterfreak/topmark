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


def test_dump_config_outputs_valid_toml() -> None:
    """It should emit valid TOML wrapped in BEGIN/END markers and parse successfully."""
    res = CliRunner().invoke(cast(click.Command, _cli), ["dump-config"])
    assert res.exit_code == ExitCode.SUCCESS, res.output
    assert "# === BEGIN ===" in res.output
    # Extract the TOML slice
    start = res.output.find("# === BEGIN ===")
    end = res.output.find("# === END ===")
    toml_text = res.output[start:end].splitlines()[1:]  # drop marker line
    parsed = tomlkit.parse("\n".join(toml_text))
    assert "fields" in parsed
    assert "header" in parsed
