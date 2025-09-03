# topmark:header:start
#
#   file         : test_apply_write_guard.py
#   file_relpath : tests/cli/test_apply_write_guard.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Apply-write guard: only write when updater marks INSERTED/REPLACED/REMOVED.

This module protects against regressions where files that should be skipped
(e.g., known no-header formats like LICENSE, binary-ish assets) were previously
truncated because the CLI wrote whenever ``updated_file_lines`` was not ``None``.

Coverage targets:
  * Default command: writes only when ``WriteStatus`` is ``INSERTED`` or ``REPLACED``.
  * Strip command: writes only when ``WriteStatus`` is ``REMOVED``.
  * Skipped/unsupported files: never written, content remains intact.
  * Idempotency: second run after apply should be a no-op with unchanged files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS, run_cli_in
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path


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
    lic = tmp_path / "LICENSE"
    original = "MIT License\n\nCopyright..."
    lic.write_text(original, "utf-8")

    # 2) Apply: should not write (guarded by WriteStatus != INSERTED/REPLACED/REMOVED)
    result = run_cli_in(tmp_path, ["check", "--apply", "LICENSE"])

    # 3) Assertions
    assert_SUCCESS(result)

    # Allow either your standard “file skipped” diagnostic or the JSON paths in other modes.
    assert "No changes to apply." in result.output
    assert lic.read_text("utf-8") == original  # content intact


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
    f = tmp_path / "x.py"
    f.write_text("print('ok')\n", "utf-8")

    # First apply: header should be inserted.
    result_1 = run_cli_in(tmp_path, ["check", "--apply", "x.py"])

    assert_SUCCESS(result_1)

    after_first = f.read_text("utf-8")

    assert TOPMARK_START_MARKER in after_first

    # Second apply: should be a no-op; content identical.
    result_2 = run_cli_in(tmp_path, ["check", "--apply", "x.py"])

    assert_SUCCESS(result_2)

    assert f.read_text("utf-8") == after_first


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
    p = tmp_path / "h.py"
    p.write_text(
        f"# {TOPMARK_START_MARKER}\n# a\n# {TOPMARK_END_MARKER}\nprint('body')\n",
        "utf-8",
    )

    # 2) Apply strip
    result_1 = run_cli_in(tmp_path, ["strip", "--apply", "h.py"])

    assert_SUCCESS(result_1)

    after1 = p.read_text("utf-8")

    assert TOPMARK_START_MARKER not in after1
    assert "print('body')" in after1

    # 4) Second run: should be a no-op
    result_2 = run_cli_in(tmp_path, ["strip", "--apply", "h.py"])

    assert_SUCCESS(result_2)

    assert p.read_text("utf-8") == after1


def test_apply_write_guard_respects_relative_patterns(tmp_path: Path) -> None:
    """Guard path: ensure relative patterns work and don't cause accidental writes.

    Creates two files:
      * `a.py` → needs insertion (should be written once)
      * `LICENSE` → known no-header (should be skipped)

    Runs with a relative glob to ensure the resolver’s “relative-only” policy is honored.
    """
    (tmp_path / "a.py").write_text("print('a')\n", "utf-8")
    lic = tmp_path / "LICENSE"
    original = "MIT\n"
    lic.write_text(original, "utf-8")

    # Use relative glob; absolute globs are unsupported by the resolver
    result = run_cli_in(tmp_path, ["check", "--apply", "*.py", "LICENSE"])

    assert_SUCCESS(result)

    # a.py should now have a header
    a_text = (tmp_path / "a.py").read_text("utf-8")

    assert TOPMARK_START_MARKER in a_text

    # LICENSE should remain intact (not written)
    assert lic.read_text("utf-8") == original


def test_apply_does_not_write_binary_like_file(tmp_path: Path) -> None:
    """`--apply` must not write for binary/unsupported files (e.g., favicon.ico)."""
    ico = tmp_path / "favicon.ico"
    data = b"\x00\x01\x02ICO"
    ico.write_bytes(data)

    result = run_cli_in(tmp_path, ["check", "--apply", "favicon.ico"])

    assert_SUCCESS(result)

    assert ico.read_bytes() == data


def test_apply_guard_mixed_changed_and_skipped(tmp_path: Path) -> None:
    """A changed .py and skipped files in one run should only write the .py."""
    (tmp_path / "x.py").write_text("print('a')\n", "utf-8")
    lic = tmp_path / "LICENSE"
    lic.write_text("MIT\n", "utf-8")
    typed = tmp_path / "py.typed"
    typed.write_text("typed\n", "utf-8")

    result = run_cli_in(tmp_path, ["check", "--apply", "*.py", "LICENSE", "py.typed"])

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER in (tmp_path / "x.py").read_text("utf-8")
    assert lic.read_text("utf-8") == "MIT\n"
    assert typed.read_text("utf-8") == "typed\n"


def test_apply_with_diff_respects_write_guard(tmp_path: Path) -> None:
    """`--apply --diff` should write only when updater sets INSERTED/REPLACED."""
    py = tmp_path / "x.py"
    py.write_text("print('a')\n", "utf-8")
    lic = tmp_path / "LICENSE"
    lic.write_text("MIT\n", "utf-8")
    result_1 = run_cli_in(tmp_path, ["check", "--apply", "--diff", "x.py"])

    assert_SUCCESS(result_1)

    assert "--- " in result_1.output

    result_2 = run_cli_in(tmp_path, ["check", "--apply", "--diff", "LICENSE"])

    assert_SUCCESS(result_2)

    assert "--- " not in result_2.output


def test_strip_apply_no_header_is_noop(tmp_path: Path) -> None:
    """`strip --apply` should not write when no header exists."""
    f = tmp_path / "no_header.py"
    f.write_text("print('ok')\n", "utf-8")
    before = f.read_text("utf-8")

    result_1 = run_cli_in(tmp_path, ["strip", "--apply", "no_header.py"])

    assert_SUCCESS(result_1)

    result_2 = run_cli_in(tmp_path, ["strip", "--apply", "no_header.py"])

    assert_SUCCESS(result_2)

    assert f.read_text("utf-8") == before


def test_apply_write_guard_with_stdin(tmp_path: Path) -> None:
    """Guard must hold when files are provided via --stdin."""
    (tmp_path / "x.py").write_text("print('x')\n", "utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", "utf-8")
    input_list = "x.py\nLICENSE\n"

    result = run_cli_in(tmp_path, ["check", "--apply", "--files-from", "-"], input_text=input_list)

    assert_SUCCESS(result)

    assert TOPMARK_START_MARKER in (tmp_path / "x.py").read_text("utf-8")
    assert (tmp_path / "LICENSE").read_text("utf-8") == "MIT\n"
