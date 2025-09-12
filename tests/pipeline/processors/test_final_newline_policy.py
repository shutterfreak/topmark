# topmark:header:start
#
#   file         : test_final_newline_policy.py
#   file_relpath : tests/pipeline/processors/test_final_newline_policy.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Final newline preservation across insert and strip paths.

Covers:
- Insert on file without a final newline (preserve: still no final newline).
- Insert on file with a final newline (preserve: still has a final newline).
- Strip on XML/HTML keeps last-line newline parity for both variants.

These tests assert the *end-of-file* newline policy using a minimal content body.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.pipeline.conftest import run_insert
from topmark.config import MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.processors import get_processor_for_file

if TYPE_CHECKING:
    from pathlib import Path


def _ends_with_newline(text: str) -> bool:
    """Return True if text ends with LF or CR/LF."""
    return text.endswith("\n") or text.endswith("\r")


def test_insert_preserves_no_final_newline_pound(tmp_path: Path) -> None:
    """Insert into Python file without final newline → still no final newline."""
    f = tmp_path / "a.py"
    # No final newline on purpose.
    f.write_text("print('x')", encoding="utf-8")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)
    out = "".join(ctx.updated_file_lines or [])
    assert not _ends_with_newline(out), "Output must preserve absence of final newline"


def test_insert_preserves_final_newline_slash(tmp_path: Path) -> None:
    """Insert into C-like file with final newline → still has a final newline."""
    f = tmp_path / "a.ts"
    f.write_text("console.log(1);\n", encoding="utf-8")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)
    out = "".join(ctx.updated_file_lines or [])
    assert _ends_with_newline(out), "Output must preserve final newline"


def test_strip_preserves_final_newline_xml(tmp_path: Path) -> None:
    """Strip on XML preserves final newline parity."""
    f1 = tmp_path / "with_nl.xml"
    f2 = tmp_path / "no_nl.xml"

    with_nl = (
        '<?xml version="1.0"?>\n'
        f"<!-- {TOPMARK_START_MARKER} -->\n"
        "<!-- h -->\n"
        f"<!-- {TOPMARK_END_MARKER} -->\n"
        "<root/>\n"  # final newline
    )
    no_nl = (
        '<?xml version="1.0"?>\n'
        f"<!-- {TOPMARK_START_MARKER} -->\n"
        "<!-- h -->\n"
        f"<!-- {TOPMARK_END_MARKER} -->\n"
        "<root/>"  # no final newline
    )

    f1.write_text(with_nl, encoding="utf-8")
    f2.write_text(no_nl, encoding="utf-8")

    proc1 = get_processor_for_file(f1)
    proc2 = get_processor_for_file(f2)
    assert proc1 and proc2

    lines1 = f1.read_text(encoding="utf-8").splitlines(keepends=True)
    lines2 = f2.read_text(encoding="utf-8").splitlines(keepends=True)

    new1, _ = proc1.strip_header_block(lines=lines1, span=None)
    new2, _ = proc2.strip_header_block(lines=lines2, span=None)

    out1 = "".join(new1)
    out2 = "".join(new2)
    assert _ends_with_newline(out1), "Strip must preserve final newline"
    assert not _ends_with_newline(out2), "Strip must preserve absence of final newline"
