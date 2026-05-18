# topmark:header:start
#
#   project      : TopMark
#   file         : test_filters_and_types.py
#   file_relpath : tests/resolver/test_filters_and_types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolver/filter integration tests for CLI target selection.

This module validates that CLI commands honor:
- include/exclude path patterns,
- file-type constraints,
- relative pattern resolution against the invocation working directory.

The tests assert exit codes only where needed to confirm whether selected files
would change; the primary contract is resolver/filter behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- Include / exclude path filters ---


def test_strip_applies_only_to_included_non_excluded_targets(tmp_path: Path) -> None:
    """`strip` should mutate only files selected by include/exclude filters.

    Patterns are intentionally relative because `run_cli_in` invokes the command
    from `tmp_path`.
    """
    a: Path = tmp_path / "a.py"
    b: Path = tmp_path / "b.py"
    a.write_text(f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\n", "utf-8")
    b.write_text(f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\n", "utf-8")

    # Exclude b.py via explicit relative path; only a.py should remain selected.
    result_1: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.INCLUDE_PATTERNS,
            "*.py",
            CliOpt.EXCLUDE_PATTERNS,
            "b.py",
            "a.py",
            "b.py",
        ],
    )

    # Applying should remove the header from a.py while leaving b.py unchanged.
    result_2: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.APPLY_CHANGES,
            CliOpt.INCLUDE_PATTERNS,
            "*.py",
            CliOpt.EXCLUDE_PATTERNS,
            "b.py",
            "a.py",
            "b.py",
        ],
    )

    # Dry-run should report that selected file a.py would be stripped.
    assert_WOULD_CHANGE(result_1)

    assert_SUCCESS(result_2)

    assert TOPMARK_START_MARKER not in a.read_text("utf-8"), "a.py should have been stripped"
    assert TOPMARK_START_MARKER in b.read_text("utf-8"), "b.py should have been filtered out"


# --- File-type filters ---


@pytest.mark.parametrize("file_type_id", ["python", "topmark:python"])
def test_file_type_filter_selects_only_matching_file_types(
    tmp_path: Path,
    file_type_id: str,
) -> None:
    """`--file-type` should limit processing to matching file types.

    Creates `.py` and `.md` files but restricts processing to the selected
    Python file type identifier.
    The relative glob pattern is resolved from `tmp_path` by `run_cli_in`.
    """
    py: Path = tmp_path / "x.py"
    md: Path = tmp_path / "y.md"
    py.write_text("print('ok')\n", "utf-8")
    md.write_text("# Title\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliOpt.INCLUDE_FILE_TYPES, file_type_id, "*.*"],
    )

    # Only x.py should be selected; because it lacks a header, check should report WOULD_CHANGE.
    assert_WOULD_CHANGE(result)


@pytest.mark.parametrize("file_type_id", ["python", "topmark:python"])
def test_file_type_exclude_filter_skips_matching_file_types(
    tmp_path: Path,
    file_type_id: str,
) -> None:
    """`--skip-type` should exclude local and qualified file type identifiers."""
    py: Path = tmp_path / "x.py"
    md: Path = tmp_path / "y.md"
    py.write_text("print('ok')\n", "utf-8")
    md.write_text("# Title\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliOpt.EXCLUDE_FILE_TYPES, file_type_id, "*.*"],
    )

    assert_WOULD_CHANGE(result)

    assert TOPMARK_START_MARKER not in py.read_text("utf-8")
    assert TOPMARK_START_MARKER not in md.read_text("utf-8")
