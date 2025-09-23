# topmark:header:start
#
#   project      : TopMark
#   file         : test_diff_edge_cases.py
#   file_relpath : tests/cli/test_diff_edge_cases.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""CLI diff edge cases for default and strip commands.

Covers:
- Diff on LF file **without** final newline still yields a non-empty, sensible patch.
- Diff on CRLF-seeded content does not introduce stray `\\r` lines or mixed endings.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.cli.conftest import assert_WOULD_CHANGE, run_cli_in
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_diff_on_no_final_newline_default(tmp_path: Path) -> None:
    """Unified diff is produced for LF file without final newline (default command)."""
    file_name = "a.py"
    f: Path = tmp_path / file_name
    # No final newline on purpose.
    f.write_text("print('x')", "utf-8")

    result: Result = run_cli_in(tmp_path, ["check", "--diff", str(f)])

    # Would insert → exit 2, and a non-empty patch must be shown.
    assert_WOULD_CHANGE(result)

    out: str = result.output
    assert "--- " in out and "+++ " in out and f"+# {TOPMARK_START_MARKER}" in out


def test_diff_preserves_crlf_strip(tmp_path: Path) -> None:
    r"""Strip diff on CRLF file shows consistent lines (no stray bare `\\r`)."""
    file_name = "a.ts"
    f: Path = tmp_path / file_name
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write(f"// {TOPMARK_START_MARKER}\n// h\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n")

    result: Result = run_cli_in(tmp_path, ["strip", "--diff", str(f)])

    assert_WOULD_CHANGE(result)

    # Basic sanity check: headers present and no raw solitary "\r" occurrences.
    out: str = result.output
    assert "--- " in out and "+++ " in out and f"-// {TOPMARK_START_MARKER}" in out

    # Focus assertions on the INFO-rendered patch block which preserves EOL markers
    start: int = out.find("Patch (rendered):")
    rendered: str = out[start:] if start != -1 else out
    # Depending on logger sinks/capture, actual EOLs might be normalized in
    # `res.output`, but the rendered block should retain explicit markers.
    # Accept either literal "\\r\\n" or common glyphs used by renderers (e.g., ␍␊).
    assert ("\\r\\n" in rendered) or ("␍␊" in rendered) or ("CRLF" in rendered.upper())

    # Still ensure no flipped sequence appears anywhere in output.
    assert "\n\r" not in out
