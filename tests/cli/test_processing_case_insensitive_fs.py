# topmark:header:start
#
#   project      : TopMark
#   file         : test_processing_case_insensitive_fs.py
#   file_relpath : tests/cli/test_processing_case_insensitive_fs.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI regression tests for case-insensitive filesystem path handling.

These tests cover issue #75 at the command boundary. They intentionally rely on
real filesystem behavior instead of mocking because the bug depends on whether
lookup of differently cased path components resolves to the same file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_human_output_does_not_contain
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


pytestmark: list[pytest.MarkDecorator] = [
    pytest.mark.cli,
    pytest.mark.case_insensitive_fs,
]


def _write_readme_without_header(root: Path) -> Path:
    """Create a Markdown file whose path uses canonical mixed casing.

    Args:
        root: Temporary project root used as the CLI working directory.

    Returns:
        The canonical path to the created README file.
    """
    docs_dir: Path = root / "Docs"
    docs_dir.mkdir()

    readme_path: Path = docs_dir / "README.md"
    readme_path.write_text("# README\n", encoding="utf-8")
    return readme_path


def _apply_header_with_canonical_path(root: Path) -> Path:
    """Create a canonical README file and apply a matching TopMark header.

    Args:
        root: Temporary project root used as the CLI working directory.

    Returns:
        The canonical path to the header-managed README file.
    """
    readme_path: Path = _write_readme_without_header(root)

    result: Result = run_cli_in(
        root,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            "Docs/README.md",
        ],
    )

    assert_SUCCESS(result)
    return readme_path


def test_check_uses_canonical_path_fields_for_mismatched_invocation_casing(
    case_insensitive_fs: Path,
) -> None:
    """A casing-only invocation mismatch should not produce a false diff.

    The header is first generated using the canonical filesystem spelling. The
    follow-up check then uses different casing for both the directory and file
    components. On a case-insensitive filesystem this should still be unchanged.
    """
    readme_path: Path = _apply_header_with_canonical_path(case_insensitive_fs)

    before: str = readme_path.read_text(encoding="utf-8")

    result: Result = run_cli_in(
        case_insensitive_fs,
        [
            CliCmd.CHECK,
            "docs/REadme.md",
        ],
    )

    assert_SUCCESS(result)
    assert readme_path.read_text(encoding="utf-8") == before
    assert_human_output_does_not_contain(
        output_format=None,
        output=result.output,
        expected="would update",
    )
    assert_human_output_does_not_contain(
        output_format=None,
        output=result.output,
        expected="changes found",
    )


def test_check_apply_preserves_file_for_mismatched_invocation_casing_when_unchanged(
    case_insensitive_fs: Path,
) -> None:
    """`check --apply` should not rewrite solely due to path casing drift."""
    readme_path: Path = _apply_header_with_canonical_path(case_insensitive_fs)

    before: str = readme_path.read_text(encoding="utf-8")
    assert "file         : README.md" in before
    assert "file_relpath : Docs/README.md" in before

    result: Result = run_cli_in(
        case_insensitive_fs,
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            "docs/REadme.md",
        ],
    )

    assert_SUCCESS(result)
    assert readme_path.read_text(encoding="utf-8") == before


def test_check_uses_canonical_path_fields_for_absolute_mismatched_invocation_casing(
    case_insensitive_fs: Path,
) -> None:
    """Absolute casing-only invocation mismatches should not produce false diffs."""
    readme_path: Path = _apply_header_with_canonical_path(case_insensitive_fs)

    before: str = readme_path.read_text(encoding="utf-8")
    invocation_path: Path = case_insensitive_fs / "docs" / "REadme.md"
    assert invocation_path.is_absolute()
    assert invocation_path.exists()

    result: Result = run_cli_in(
        case_insensitive_fs,
        [
            CliCmd.CHECK,
            invocation_path.as_posix(),
        ],
    )

    assert_SUCCESS(result)
    assert readme_path.read_text(encoding="utf-8") == before
    assert_human_output_does_not_contain(
        output_format=None,
        output=result.output,
        expected="would update",
    )
    assert_human_output_does_not_contain(
        output_format=None,
        output=result.output,
        expected="changes found",
    )
