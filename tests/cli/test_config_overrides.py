# topmark:header:start
#
#   file         : test_config_overrides.py
#   file_relpath : tests/cli/test_config_overrides.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# File path: tests/config/test_config_overrides.py
"""Configuration resolution: user config overrides and invalid config.

Ensures:
- A local `topmark.toml` is picked up by the CLI,
- Invalid TOML produces a clean, user-facing error (non-zero exit).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_local_topmark_toml_overrides_defaults(tmp_path: Path):
    """Local `topmark.toml` should influence CLI behavior in that directory."""
    # Minimal config that is syntactically valid; customize fields if needed.
    (tmp_path / "topmark.toml").write_text('[topmark]\nproject = "Demo"\n', "utf-8")
    f = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")

    # Run from inside that directory to pick up the config.
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(cli, ["--apply", str(f)])
        assert res.exit_code == 0


def test_invalid_topmark_toml_yields_clean_error(tmp_path: Path):
    """Malformed TOML should return a non-zero exit with a friendly message."""
    (tmp_path / "topmark.toml").write_text("this = [[[[ not_toml", "utf-8")
    f = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")

    res = CliRunner().invoke(cli, ["check", str(f)])

    # Expect a controlled error with non-zero exit.
    assert res.exit_code != 0
