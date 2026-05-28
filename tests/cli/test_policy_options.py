# topmark:header:start
#
#   project      : TopMark
#   file         : test_policy_options.py
#   file_relpath : tests/cli/test_policy_options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI policy-option exposure and behavior tests.

This module verifies the command-line policy surface:
- `check` exposes check-only and shared policy options,
- `strip` exposes only shared policy options,
- kebab-case enum values are accepted by the CLI,
- selected policy options affect observable `check` behavior,
- check-only policy options are rejected by `strip`.

These are CLI applicability and behavior tests, not pure exit-code contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_USAGE_ERROR
from tests.cli.conftest import command_option_names
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


# --- Help output: exposed policy surface ---


def test_check_help_lists_check_only_and_shared_policy_options() -> None:
    """`check --help` should list both check-only and shared policy options."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            "--help",
        ]
    )
    assert_SUCCESS(result)

    option_names: set[str] = command_option_names(CliCmd.CHECK)

    assert CliOpt.POLICY_HEADER_MUTATION_MODE in option_names
    assert CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES in option_names
    assert CliOpt.POLICY_EMPTY_INSERT_MODE in option_names
    assert CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS in option_names
    assert CliOpt.POLICY_ALLOW_REFLOW in option_names
    assert CliOpt.POLICY_ALLOW_CONTENT_PROBE in option_names


def test_strip_help_lists_only_shared_policy_options() -> None:
    """`strip --help` should expose shared policy options only."""
    result: Result = run_cli(
        [
            CliCmd.STRIP,
            "--help",
        ]
    )
    assert_SUCCESS(result)

    option_names: set[str] = command_option_names(CliCmd.STRIP)

    assert CliOpt.POLICY_ALLOW_CONTENT_PROBE in option_names
    assert CliOpt.POLICY_HEADER_MUTATION_MODE not in option_names
    assert CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES not in option_names
    assert CliOpt.POLICY_EMPTY_INSERT_MODE not in option_names
    assert CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS not in option_names
    assert CliOpt.POLICY_ALLOW_REFLOW not in option_names


# --- Check behavior: header mutation mode ---


def test_check_header_mutation_mode_add_only_inserts_missing_headers(tmp_path: Path) -> None:
    """`check --header-mutation-mode add-only` should insert missing headers."""
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


def test_check_header_mutation_mode_update_only_skips_missing_headers(tmp_path: Path) -> None:
    """`check --header-mutation-mode update-only` should not insert missing headers."""
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


# --- Check behavior: empty-file insertion policy ---


def test_check_allow_header_in_empty_files_enables_insertion_into_empty_files(
    tmp_path: Path,
) -> None:
    """`check --allow-header-in-empty-files` should allow empty-file insertion."""
    target: Path = tmp_path / "empty.py"
    target.write_text("", encoding="utf-8")

    # Default policy leaves a truly empty file untouched.
    result_default: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            target.name,
        ],
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


def test_check_empty_insert_mode_whitespace_empty_treats_whitespace_as_empty(
    tmp_path: Path,
) -> None:
    """`check --empty-insert-mode whitespace-empty` should treat whitespace as empty."""
    target: Path = tmp_path / "whitespace_only.py"
    whitespace_only: str = " \n \n"

    # Default empty-insert mode does not treat whitespace-only input as empty,
    # so normal insertion may proceed.
    target.write_text(whitespace_only, encoding="utf-8")
    result_default: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            target.name,
        ],
    )
    assert_SUCCESS(result_default)
    assert _has_topmark_header(target)

    # Whitespace-empty mode classifies the same input as empty; the default
    # policy still forbids insertion into empty files.
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


# --- Strip applicability: rejected check-only options ---


def test_strip_rejects_header_mutation_mode_option(tmp_path: Path) -> None:
    """`strip` should reject the check-only header-mutation option."""
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
