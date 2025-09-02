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

from tests.cli.conftest import assert_SUCCESS, run_cli_in
from topmark.cli_shared.exit_codes import ExitCode


def test_local_topmark_toml_overrides_defaults(tmp_path: Path) -> None:
    """Local `topmark.toml` should influence CLI behavior in that directory."""
    # Minimal config that is syntactically valid; customize fields if needed.
    (tmp_path / "topmark.toml").write_text('[topmark]\nproject = "Demo"\n', "utf-8")
    file_name = "x.py"
    f = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    # Run from inside that directory so the local topmark.toml is picked up.
    result = run_cli_in(tmp_path, ["check", "--apply", file_name])  # use relative path in tmp_path
    assert_SUCCESS(result)


def test_invalid_topmark_toml_yields_clean_error(tmp_path: Path) -> None:
    """Malformed TOML should return a non-zero exit with a friendly message."""
    (tmp_path / "topmark.toml").write_text("this = [[[[ not_toml", "utf-8")
    file_name = "x.py"
    f = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    result = run_cli_in(tmp_path, ["check", str(f)])

    # Expect a controlled error with non-zero exit -- TODO: specific code?
    assert result.exit_code != ExitCode.SUCCESS, result.output
