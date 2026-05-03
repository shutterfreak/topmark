# topmark:header:start
#
#   project      : TopMark
#   file         : test_apply_write_guard.py
#   file_relpath : tests/cli/test_apply_write_guard.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Apply/write-guard contract tests.

These tests ensure that files are written **only** when the updater explicitly
marks a mutation (INSERTED / REPLACED / REMOVED). They protect against
regressions where skipped or unsupported files were previously truncated.

Contract covered:
  * Default (`check`): writes only on INSERTED / REPLACED.
  * Strip (`strip`): writes only on REMOVED.
  * Skipped/unsupported inputs: never written.
  * Idempotency: second run after apply is a no-op.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.constants import TOPMARK_END_MARKER
from topmark.constants import TOPMARK_START_MARKER
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

# All tests in this module pin exit-code + write-guard behavior.
pytestmark: pytest.MarkDecorator = pytest.mark.exit_code


# --- Apply pipeline invocation contract ---
def test_default_summary_apply_runs_apply_pipeline(tmp_path: Path) -> None:
    """`--summary --apply` should still perform apply pipeline (not dry-run only)."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    result: Result = run_cli(
        [CliCmd.CHECK, CliOpt.RESULTS_SUMMARY_MODE, CliOpt.APPLY_CHANGES, str(f)],
    )

    assert_SUCCESS(result)

    # File should now contain a header.
    assert TOPMARK_START_MARKER in f.read_text("utf-8")


def test_default_diff_with_apply_emits_patch(tmp_path: Path) -> None:
    """`--diff --apply` should apply changes and still show a patch."""
    f: Path = tmp_path / "x.py"
    f.write_text("print('z')\n", "utf-8")

    result: Result = run_cli(
        [CliCmd.CHECK, CliOpt.RENDER_DIFF, CliOpt.APPLY_CHANGES, str(f)],
    )

    # Apply succeeded; diff should be emitted for changed file.
    assert_SUCCESS(result)

    assert "--- " in result.output and "+++ " in result.output


# --- Write guard: skipped / unsupported inputs ---
def test_apply_does_not_write_skipped_known_no_headers(tmp_path: Path) -> None:
    """`--apply` must not write for known no-header types (e.g., LICENSE).

    Steps:
      1) Create a `LICENSE` file with non-empty content.
      2) Run `topmark --apply LICENSE`.
      3) Verify:
         - Exit code is SUCCESS.
         - Output mentions the file is skipped.
         - File content is unchanged (no truncation).
    """
    # 1) Prepare a known no-headers file type with content
    lic: Path = tmp_path / "LICENSE"
    original = "MIT License\n\nCopyright..."
    lic.write_text(original, "utf-8")

    # 2) Apply: should not write (guarded by WriteStatus != INSERTED/REPLACED/REMOVED)
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.REPORT,
            ReportScope.ALL,  # Ensure compliant files are also reported
            CliOpt.APPLY_CHANGES,
            "LICENSE",
        ],
    )

    # 3) Assertions
    assert_SUCCESS(result)

    # Output should indicate no changes; content must remain intact.
    assert "no changes to apply." in result.output
    assert lic.read_text("utf-8") == original  # content intact


# --- Write guard: insertion and idempotency ---
def test_apply_writes_only_on_insert_and_is_idempotent(tmp_path: Path) -> None:
    """Default command: write only when INSERTED/REPLACED; then no-op.

    Steps:
      1) Create a simple Python file without a header.
      2) Run `topmark --apply x.py` and assert:
         - Exit SUCCESS.
         - File now contains a TopMark header (INSERTED).
      3) Run the same command again:
         - Exit SUCCESS.
         - File is unchanged (no touch-write).
    """
    f: Path = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")

    # First apply: header should be inserted.
    result_1: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "x.py"],
    )

    assert_SUCCESS(result_1)

    after_first: str = f.read_text("utf-8")

    assert TOPMARK_START_MARKER in after_first

    # Second apply: must be a no-op; content identical.
    result_2: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "x.py"],
    )

    assert_SUCCESS(result_2)

    assert f.read_text("utf-8") == after_first


# --- Write guard: strip removal semantics ---
def test_strip_apply_writes_only_on_removed_and_preserves_body(tmp_path: Path) -> None:
    """`strip --apply` should only write when a header was actually removed.

    Steps:
      1) Create a file with a TopMark header followed by code.
      2) Run `topmark strip --apply file`.
      3) Verify:
         - Exit SUCCESS.
         - Header is gone, body remains.
      4) Run again to confirm idempotency (no further write).
    """
    # 1) Prepare a file with a header + body
    p: Path = tmp_path / "h.py"
    p.write_text(
        f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint('body')\n",
        "utf-8",
    )

    # 2) Apply strip
    result_1: Result = run_cli_in(
        tmp_path,
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, "h.py"],
    )

    assert_SUCCESS(result_1)

    after1: str = p.read_text("utf-8")

    assert TOPMARK_START_MARKER not in after1
    assert "print('body')" in after1

    # Second run: must be a no-op
    result_2: Result = run_cli_in(
        tmp_path,
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, "h.py"],
    )

    assert_SUCCESS(result_2)

    assert p.read_text("utf-8") == after1


# --- Write guard: path resolution / patterns ---
def test_apply_write_guard_respects_relative_patterns(tmp_path: Path) -> None:
    """Guard path: ensure relative patterns work and don't cause accidental writes.

    Creates two files:
      * `a.py` → needs insertion (should be written once)
      * `LICENSE` → known no-header (should be skipped)

    Runs with a relative glob to ensure the resolver’s “relative-only” policy is honored.
    """
    (tmp_path / "a.py").write_text("print('a')\n", "utf-8")
    lic: Path = tmp_path / "LICENSE"
    original = "MIT\n"
    lic.write_text(original, "utf-8")

    # Use relative glob; absolute globs are unsupported by the resolver
    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "*.py", "LICENSE"],
    )

    assert_SUCCESS(result)

    # a.py should now have a header
    a_text: str = (tmp_path / "a.py").read_text("utf-8")

    assert TOPMARK_START_MARKER in a_text

    # LICENSE should remain intact (not written)
    assert lic.read_text("utf-8") == original


# --- Write guard: binary / unsupported files ---
def test_apply_does_not_write_binary_like_file(tmp_path: Path) -> None:
    """`--apply` must not write for binary/unsupported files (e.g., favicon.ico)."""
    ico: Path = tmp_path / "favicon.ico"
    data = b"\x00\x01\x02ICO"
    ico.write_bytes(data)

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "favicon.ico"],
    )

    assert_SUCCESS(result)

    assert ico.read_bytes() == data


# --- Mixed scenarios: changed + skipped inputs ---
def test_apply_guard_mixed_changed_and_skipped(tmp_path: Path) -> None:
    """A changed .py and skipped files in one run should only write the .py."""
    (tmp_path / "x.py").write_text("print('a')\n", "utf-8")
    lic: Path = tmp_path / "LICENSE"
    lic.write_text("MIT\n", "utf-8")
    typed: Path = tmp_path / "py.typed"
    typed.write_text("typed\n", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "*.py", "LICENSE", "py.typed"],
    )

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER in (tmp_path / "x.py").read_text("utf-8")
    assert lic.read_text("utf-8") == "MIT\n"
    assert typed.read_text("utf-8") == "typed\n"


# --- Interaction: apply + diff rendering ---
def test_apply_with_diff_respects_write_guard(tmp_path: Path) -> None:
    """`--apply --diff` should write only when updater sets INSERTED/REPLACED."""
    py: Path = tmp_path / "x.py"
    py.write_text("print('a')\n", "utf-8")
    lic: Path = tmp_path / "LICENSE"
    lic.write_text("MIT\n", "utf-8")
    result_1: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, CliOpt.RENDER_DIFF, "x.py"],
    )

    assert_SUCCESS(result_1)

    assert "--- " in result_1.output

    result_2: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, CliOpt.RENDER_DIFF, "LICENSE"],
    )

    assert_SUCCESS(result_2)

    assert "--- " not in result_2.output


# --- Strip no-op semantics ---
def test_strip_apply_no_header_is_noop(tmp_path: Path) -> None:
    """`strip --apply` should not write when no header exists."""
    f: Path = tmp_path / "no_header.py"
    f.write_text("print('ok')\n", "utf-8")
    before: str = f.read_text("utf-8")

    result_1: Result = run_cli_in(
        tmp_path,
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, "no_header.py"],
    )

    assert_SUCCESS(result_1)

    result_2: Result = run_cli_in(
        tmp_path,
        [CliCmd.STRIP, CliOpt.APPLY_CHANGES, "no_header.py"],
    )

    assert_SUCCESS(result_2)

    assert f.read_text("utf-8") == before


# --- STDIN input handling ---
def test_apply_write_guard_with_stdin(tmp_path: Path) -> None:
    """Guard must hold when files are provided via --stdin."""
    (tmp_path / "x.py").write_text("print('x')\n", "utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", "utf-8")
    input_list = "x.py\nLICENSE\n"

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, CliOpt.FILES_FROM, "-"],
        input_text=input_list,
    )

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER in (tmp_path / "x.py").read_text("utf-8")
    assert (tmp_path / "LICENSE").read_text("utf-8") == "MIT\n"
