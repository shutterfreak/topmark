# topmark:header:start
#
#   file         : test_diff_edge_cases.py
#   file_relpath : tests/cli/test_diff_edge_cases.py
#   project      : TopMark
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
from typing import cast

import click
from click.testing import CliRunner

from topmark.cli.exit_codes import ExitCode
from topmark.cli.main import cli as _cli

# Type hint for the CLI command object
cli = cast(click.Command, _cli)


def test_diff_on_no_final_newline_default(tmp_path: Path) -> None:
    """Unified diff is produced for LF file without final newline (default command)."""
    f = tmp_path / "a.py"
    # No final newline on purpose.
    f.write_text("print('x')", "utf-8")

    result = CliRunner().invoke(cli, ["-vv", "--diff", str(f)])

    # Would insert → exit 2, and a non-empty patch must be shown.
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output

    out = result.output
    assert "--- " in out and "+++ " in out and "+# topmark:header:start" in out


def test_diff_preserves_crlf_strip(tmp_path: Path) -> None:
    r"""Strip diff on CRLF file shows consistent lines (no stray bare `\\r`)."""
    f = tmp_path / "a.ts"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("// topmark:header:start\n// h\n// topmark:header:end\nconsole.log(1)\n")

    result = CliRunner().invoke(cli, ["-vv", "strip", "--diff", str(f)])

    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output

    # Basic sanity check: headers present and no raw solitary "\r" occurrences.
    out = result.output
    assert "--- " in out and "+++ " in out and "-// topmark:header:start" in out

    # Focus assertions on the INFO-rendered patch block which preserves EOL markers
    start = out.find("Patch (rendered):")
    rendered = out[start:] if start != -1 else out
    # Depending on logger sinks/capture, actual EOLs might be normalized in
    # `res.output`, but the rendered block should retain explicit markers.
    # Accept either literal "\\r\\n" or common glyphs used by renderers (e.g., ␍␊).
    assert ("\\r\\n" in rendered) or ("␍␊" in rendered) or ("CRLF" in rendered.upper())

    # Still ensure no flipped sequence appears anywhere in output.
    assert "\n\r" not in out
