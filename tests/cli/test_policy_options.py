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

import pytest

from tests.cli.conftest import assert_rich_output_contains
from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import assert_WOULD_CHANGE
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
    assert CliOpt.POLICY_BOM_BEFORE_SHEBANG in option_names
    assert_rich_output_contains(
        result.output,
        expected="Accepted values: 'all', 'add-only', 'update-only'.",
    )
    assert_rich_output_contains(
        result.output,
        expected="Accepted values: 'bytes-empty', 'logical-empty', 'whitespace-empty'.",
    )
    assert_rich_output_contains(
        result.output,
        expected="Accepted values: 'reject', 'remove-bom'.",
    )
    assert_rich_output_contains(
        result.output,
        expected="Multiword CLI values require hyphens",
    )


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
    assert CliOpt.POLICY_BOM_BEFORE_SHEBANG in option_names
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
    assert_rich_output_no_such_option(
        result,
        option_name=CliOpt.POLICY_HEADER_MUTATION_MODE,
    )


def test_check_remove_bom_cli_token_applies_with_inplace_writer(tmp_path: Path) -> None:
    """The kebab-case CLI token should apply exact BOM removal in-place."""
    target: Path = tmp_path / "bom.py"
    target.write_bytes(b"\xef\xbb\xbf#!/usr/bin/env python\nprint('ok')\n")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            CliOpt.WRITE_MODE,
            "inplace",
            CliOpt.POLICY_BOM_BEFORE_SHEBANG,
            "remove-bom",
            target.name,
        ],
    )

    assert_SUCCESS(result)
    assert target.read_bytes().startswith(b"#!")
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")


def test_strip_remove_bom_cli_dry_run_shows_diff_and_would_change(tmp_path: Path) -> None:
    """Strip dry-run should expose standalone BOM removal and exit WOULD_CHANGE."""
    target: Path = tmp_path / "bom.py"
    original: bytes = b"\xef\xbb\xbf#!/usr/bin/env python\rprint('ok')"
    target.write_bytes(original)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.RENDER_DIFF,
            CliOpt.POLICY_BOM_BEFORE_SHEBANG,
            "remove-bom",
            target.name,
        ],
    )

    assert_WOULD_CHANGE(result)
    assert "-\ufeff#!" in result.output
    assert "+#!" in result.output
    assert target.read_bytes() == original


def test_check_rejects_invalid_bom_before_shebang_cli_token(tmp_path: Path) -> None:
    """Invalid BOM policy tokens should fail through Click enum validation."""
    target: Path = tmp_path / "x.py"
    target.write_text("print('ok')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.POLICY_BOM_BEFORE_SHEBANG,
            "repair",
            target.name,
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value" in result.output


@pytest.mark.parametrize(
    ("option", "value"),
    [
        pytest.param(CliOpt.POLICY_HEADER_MUTATION_MODE, "add-only", id="add-only"),
        pytest.param(CliOpt.POLICY_HEADER_MUTATION_MODE, "update-only", id="update-only"),
        pytest.param(CliOpt.POLICY_EMPTY_INSERT_MODE, "bytes-empty", id="bytes-empty"),
        pytest.param(CliOpt.POLICY_EMPTY_INSERT_MODE, "logical-empty", id="logical-empty"),
        pytest.param(
            CliOpt.POLICY_EMPTY_INSERT_MODE,
            "whitespace-empty",
            id="whitespace-empty",
        ),
        pytest.param(CliOpt.POLICY_BOM_BEFORE_SHEBANG, "remove-bom", id="remove-bom"),
    ],
)
def test_check_accepts_canonical_multiword_policy_tokens(
    tmp_path: Path,
    option: str,
    value: str,
) -> None:
    """Every multiword policy value should parse in canonical kebab-case."""
    target: Path = tmp_path / "x.py"
    target.write_text("print('ok')\n", encoding="utf-8")

    result: Result = run_cli_in(tmp_path, [CliCmd.CHECK, option, value, target.name])

    assert_SUCCESS_or_WOULD_CHANGE(result)


@pytest.mark.parametrize("assignment_form", [False, True], ids=["spaced", "assignment"])
@pytest.mark.parametrize(
    ("option", "snake_value", "canonical_value", "choice_listing"),
    [
        pytest.param(
            CliOpt.POLICY_HEADER_MUTATION_MODE,
            "update_only",
            "update-only",
            "all, add-only, update-only",
            id="header-mutation",
        ),
        pytest.param(
            CliOpt.POLICY_EMPTY_INSERT_MODE,
            "logical_empty",
            "logical-empty",
            "bytes-empty, logical-empty, whitespace-empty",
            id="empty-insert",
        ),
        pytest.param(
            CliOpt.POLICY_BOM_BEFORE_SHEBANG,
            "remove_bom",
            "remove-bom",
            "reject, remove-bom",
            id="bom-before-shebang",
        ),
    ],
)
def test_check_rejects_snake_case_policy_tokens_with_canonical_suggestion(
    tmp_path: Path,
    option: str,
    snake_value: str,
    canonical_value: str,
    choice_listing: str,
    *,
    assignment_form: bool,
) -> None:
    """Snake-case policy values should be Click errors with a narrow suggestion."""
    target: Path = tmp_path / "x.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    option_args: list[str] = (
        [f"{option}={snake_value}"] if assignment_form else [option, snake_value]
    )

    result: Result = run_cli_in(tmp_path, [CliCmd.CHECK, *option_args, target.name])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert_rich_output_contains(result.stderr, expected="Usage: cli check")
    assert_rich_output_contains(result.stderr, expected=f"Invalid value for '{option}'")
    assert_rich_output_contains(result.stderr, expected=f"Invalid value '{snake_value}'")
    assert_rich_output_contains(result.stderr, expected=f"Did you mean '{canonical_value}'?")
    assert_rich_output_contains(result.stderr, expected=f"Must be one of: {choice_listing}")
