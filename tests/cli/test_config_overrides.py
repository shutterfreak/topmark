# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_overrides.py
#   file_relpath : tests/cli/test_config_overrides.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Configuration override and error exit-code contract tests.

This module covers:
- local configuration discovery and override behavior,
- configuration parsing failures.

It pins the CLI contract that:
  * valid configuration → SUCCESS (0)
  * malformed discovered configuration → CONFIG_ERROR (78), even in non-strict mode
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.config.types import FileWriteStrategy
from topmark.runtime.writer_options import WriterOptions
from topmark.runtime.writer_options import apply_resolved_writer_options

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

    from topmark.runtime.model import RunOptions

# All tests in this module pin configuration-related exit-code behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


_WRITER_INPLACE_CONFIG: str = textwrap.dedent(
    """
    [fields]
    project = "Demo"
    [header]
    fields = ["project"]
    [writer]
    strategy = "inplace"
    """
).lstrip("\n")


# --- Valid configuration override ---


def test_local_topmark_toml_overrides_defaults(
    tmp_path: Path,
) -> None:
    """Local configuration should be discovered and applied successfully."""
    # Minimal config that is syntactically valid; customize fields if needed.
    (tmp_path / "topmark.toml").write_text('[topmark]\nproject = "Demo"\n', "utf-8")
    file_name = "x.py"
    f: Path = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    # Run from inside that directory so the local topmark.toml is picked up.
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            file_name,
        ],
    )  # use relative path in tmp_path
    assert_SUCCESS(result)


# --- Writer option precedence ---


def test_local_writer_option_is_applied_to_cli_run_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovered TOML writer options should reach CLI runtime options."""
    (tmp_path / "topmark.toml").write_text(_WRITER_INPLACE_CONFIG, "utf-8")
    file_name = "x.py"
    f: Path = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    captured: list[FileWriteStrategy | None] = []

    def capture_writer_options(
        run_options: RunOptions,
        writer_options: WriterOptions | None,
    ) -> RunOptions:
        captured.append(None if writer_options is None else writer_options.file_write_strategy)
        return apply_resolved_writer_options(run_options, writer_options)

    monkeypatch.setattr(
        "topmark.cli.cmd_common.apply_resolved_writer_options",
        capture_writer_options,
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            file_name,
        ],
    )

    assert_SUCCESS(result)
    assert captured == [FileWriteStrategy.INPLACE]


def test_cli_write_mode_overrides_local_writer_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit CLI write mode should override discovered TOML writer options."""
    (tmp_path / "topmark.toml").write_text(_WRITER_INPLACE_CONFIG, "utf-8")
    file_name = "x.py"
    f: Path = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    captured_resolved: list[FileWriteStrategy | None] = []
    captured_effective: list[FileWriteStrategy | None] = []

    def capture_writer_options(
        run_options: RunOptions,
        writer_options: WriterOptions | None,
    ) -> RunOptions:
        captured_resolved.append(
            None if writer_options is None else writer_options.file_write_strategy
        )
        effective: RunOptions = apply_resolved_writer_options(run_options, writer_options)
        captured_effective.append(effective.file_write_strategy)
        return effective

    monkeypatch.setattr(
        "topmark.cli.cmd_common.apply_resolved_writer_options",
        capture_writer_options,
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            "--write-mode=atomic",
            file_name,
        ],
    )

    assert_SUCCESS(result)
    assert captured_resolved == [FileWriteStrategy.INPLACE]
    assert captured_effective == [FileWriteStrategy.ATOMIC]


# --- Invalid configuration handling ---


def test_invalid_topmark_toml_exits_config_error_in_non_strict_mode(
    tmp_path: Path,
) -> None:
    """Malformed discovered config should exit CONFIG_ERROR even in non-strict mode."""
    (tmp_path / "topmark.toml").write_text("this = [[[[ not_toml", "utf-8")
    file_name = "x.py"
    f: Path = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            str(f),
        ],
    )

    # TOML parse failures are errors, not warnings; non-strict mode only allows warnings through.
    assert_CONFIG_ERROR(result)


def test_invalid_topmark_toml_exits_config_error_in_strict_mode(
    tmp_path: Path,
) -> None:
    """Malformed discovered config should exit CONFIG_ERROR under `--strict`."""
    (tmp_path / "topmark.toml").write_text("this = [[[[ not_toml", "utf-8")
    file_name = "x.py"
    f: Path = tmp_path / file_name
    f.write_text("print('ok')\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.STRICT,
            str(f),
        ],
    )

    # Strict config checking escalates config-resolution diagnostics to CONFIG_ERROR.
    assert_CONFIG_ERROR(result)
