# topmark:header:start
#
#   project      : TopMark
#   file         : test_policy_options.py
#   file_relpath : tests/cli/test_policy_options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for policy option exposure and behavior.

These tests focus on the command-line policy surface rather than lower-level
config or API policy resolution helpers. They verify that:

- `check` exposes check-only and shared policy options
- `strip` exposes only the shared policy option surface
- kebab-case enum values are accepted by the CLI
- selected policy options affect observable command behavior
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def _read_text(path: Path) -> str:
    """Return file contents as UTF-8 text."""
    return path.read_text("utf-8")


def _has_topmark_header(path: Path) -> bool:
    """Return whether the file contains a TopMark header sentinel."""
    return "topmark:header:start" in _read_text(path)


def test_check_help_lists_check_only_and_shared_policy_options() -> None:
    """`topmark check --help` should list both check-only and shared policy options."""
    result: Result = run_cli([CliCmd.CHECK, "--help"])
    assert_SUCCESS(result)

    assert CliOpt.POLICY_HEADER_MUTATION_MODE in result.output
    assert CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES in result.output
    assert CliOpt.POLICY_EMPTY_INSERT_MODE in result.output
    assert CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS in result.output
    assert CliOpt.POLICY_ALLOW_REFLOW in result.output
    assert CliOpt.POLICY_ALLOW_CONTENT_PROBE in result.output


def test_strip_help_lists_only_shared_policy_options() -> None:
    """`topmark strip --help` should not expose check-only policy options."""
    result: Result = run_cli([CliCmd.STRIP, "--help"])
    assert_SUCCESS(result)

    assert CliOpt.POLICY_ALLOW_CONTENT_PROBE in result.output
    assert CliOpt.POLICY_HEADER_MUTATION_MODE not in result.output
    assert CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES not in result.output
    assert CliOpt.POLICY_EMPTY_INSERT_MODE not in result.output
    assert CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS not in result.output
    assert CliOpt.POLICY_ALLOW_REFLOW not in result.output


def test_check_header_mutation_mode_add_only_inserts_missing_header(tmp_path: Path) -> None:
    """`--header-mutation-mode add-only` should still insert a missing header."""
    target: Path = tmp_path / "missing.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            CliOpt.POLICY_HEADER_MUTATION_MODE,
            "add-only",
            target.name,
        ],
    )
    assert_SUCCESS(result)
    assert _has_topmark_header(target)


def test_check_header_mutation_mode_update_only_skips_missing_header(tmp_path: Path) -> None:
    """`--header-mutation-mode update-only` should not insert a missing header."""
    target: Path = tmp_path / "missing.py"
    original: str = "print('hi')\n"
    target.write_text(original, encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            CliOpt.POLICY_HEADER_MUTATION_MODE,
            "update-only",
            target.name,
        ],
    )
    assert_SUCCESS(result)
    assert _read_text(target) == original
    assert not _has_topmark_header(target)


def test_check_allow_header_in_empty_files_enables_empty_file_insertion(tmp_path: Path) -> None:
    """`--allow-header-in-empty-files` should allow insertion into an empty file."""
    target: Path = tmp_path / "empty.py"
    target.write_text("", encoding="utf-8")

    # Default policy should leave a truly empty file untouched.
    result_default: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, target.name],
    )
    assert_SUCCESS(result_default)
    assert _read_text(target) == ""

    # Reset and explicitly allow insertion into empty files.
    target.write_text("", encoding="utf-8")
    result_allowed: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES,
            target.name,
        ],
    )
    assert_SUCCESS(result_allowed)
    assert _has_topmark_header(target)


def test_check_empty_insert_mode_whitespace_empty_affects_whitespace_only_input(
    tmp_path: Path,
) -> None:
    """`--empty-insert-mode whitespace-empty` should be accepted and affect behavior."""
    target: Path = tmp_path / "whitespace_only.py"
    whitespace_only: str = " \n \n"

    # Under the default empty-insert mode, this input should not be treated as an
    # empty file, so normal insertion may proceed.
    target.write_text(whitespace_only, encoding="utf-8")
    result_default: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, target.name],
    )
    assert_SUCCESS(result_default)
    assert _has_topmark_header(target)

    # Under whitespace-empty mode, the same input is classified as empty and the
    # default policy still forbids insertion into empty files.
    target.write_text(whitespace_only, encoding="utf-8")
    result_whitespace_empty: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            CliOpt.POLICY_EMPTY_INSERT_MODE,
            "whitespace-empty",
            target.name,
        ],
    )
    assert_SUCCESS(result_whitespace_empty)
    assert _read_text(target) == whitespace_only
    assert not _has_topmark_header(target)


def test_strip_rejects_check_only_policy_option(tmp_path: Path) -> None:
    """`strip` should reject check-only policy options at the CLI layer."""
    target: Path = tmp_path / "x.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.POLICY_HEADER_MUTATION_MODE,
            "add-only",
            target.name,
        ],
    )
    assert_USAGE_ERROR(result)
