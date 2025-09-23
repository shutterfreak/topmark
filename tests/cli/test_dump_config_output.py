# topmark:header:start
#
#   project      : TopMark
#   file         : test_dump_config_output.py
#   file_relpath : tests/cli/test_dump_config_output.py
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

from __future__ import annotations

from typing import TYPE_CHECKING

import tomlkit

from tests.cli.conftest import assert_SUCCESS, run_cli

if TYPE_CHECKING:
    from click.testing import Result


def test_dump_config_outputs_valid_toml() -> None:
    """It should emit valid TOML wrapped in BEGIN/END markers and parse successfully."""
    result: Result = run_cli(
        [
            "--no-color",  # Strip ANSI formatting to allow parsing the generated TOML
            "-v",  # Render the BEGIN and END markers
            "dump-config",
        ]
    )

    assert_SUCCESS(result)

    assert "# === BEGIN ===" in result.output

    # Extract the TOML slice
    start: int = result.output.find("# === BEGIN ===")
    end: int = result.output.find("# === END ===")
    toml_text: list[str] = result.output[start:end].splitlines()[1:]  # drop marker line
    parsed: tomlkit.TOMLDocument = tomlkit.parse("\n".join(toml_text))
    assert "fields" in parsed

    assert "header" in parsed
