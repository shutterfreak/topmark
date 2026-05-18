# topmark:header:start
#
#   project      : TopMark
#   file         : test_diff_edge_cases.py
#   file_relpath : tests/cli/test_diff_edge_cases.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""CLI diff-rendering edge-case tests.

This module covers diff output for newline-sensitive inputs:
- LF content without a final newline,
- CRLF-seeded content rendered through `strip --diff`.

These tests verify that patches are emitted and that rendered newline markers do
not regress into malformed or mixed-ending output.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- LF input without final newline ---


def test_check_diff_on_lf_input_without_final_newline_emits_patch(tmp_path: Path) -> None:
    """`check --diff` should emit a patch for LF input without final newline."""
    file_name = "a.py"
    f: Path = tmp_path / file_name
    # No final newline on purpose; this exercises diff rendering at EOF.
    f.write_text("print('x')", "utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RENDER_DIFF,
            str(f),
        ],
    )

    # Header insertion would be needed, and a non-empty patch must be shown.
    assert_WOULD_CHANGE(result)

    out: str = result.output
    assert "--- " in out and "+++ " in out and f"+# {TOPMARK_START_MARKER}" in out


# --- CRLF input rendering ---


def test_strip_diff_on_crlf_input_preserves_newline_rendering(tmp_path: Path) -> None:
    r"""`strip --diff` should render CRLF input without flipped newline sequences."""
    file_name = "a.ts"
    f: Path = tmp_path / file_name
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write(
            f"// {TOPMARK_START_MARKER}\n// test:header\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n"
        )

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.STRIP,
            CliOpt.RENDER_DIFF,
            str(f),
        ],
    )

    assert_WOULD_CHANGE(result)

    # Basic sanity check: the rendered patch should include the removed header.
    out: str = result.output
    assert "--- " in out and "+++ " in out and f"-// {TOPMARK_START_MARKER}" in out

    # Focus assertions on the INFO-rendered patch block.
    start: int = out.find("Patch (rendered):")
    rendered: str = out[start:] if start != -1 else out

    # Some sinks normalize CRLF, so accept any of:
    #  - actual CRLF characters,
    #  - visible glyph markers,
    #  - escaped-literal markers,
    #  - or no explicit CRLF markers as long as no flipped "\n\r" appears.
    has_actual_crlf: bool = "\r\n" in rendered
    has_visible_glyphs: bool = "␍␊" in rendered
    # Keep an escaped-literal check for sinks that display escapes.
    has_escaped_literal: bool = "\\r\\n" in rendered

    assert has_actual_crlf or has_visible_glyphs or has_escaped_literal or ("\n\r" not in rendered)

    # Ensure no flipped sequence appears anywhere in output.
    assert "\n\r" not in out
