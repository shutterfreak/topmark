# topmark:header:start
#
#   project      : TopMark
#   file         : test_final_newline_policy.py
#   file_relpath : tests/pipeline/processors/test_final_newline_policy.py
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

from tests.pipeline.conftest import materialize_updated_lines, run_insert
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.processors import get_processor_for_file
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor


def _ends_with_newline(text: str) -> bool:
    """Return True if text ends with LF or CR/LF."""
    return text.endswith("\n") or text.endswith("\r")


def test_insert_preserves_no_final_newline_pound(tmp_path: Path) -> None:
    """Insert into Python file without final newline → still no final newline."""
    f: Path = tmp_path / "a.py"
    # No final newline on purpose.
    f.write_text("print('x')", encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    out: str = "".join(lines)
    assert not _ends_with_newline(out), "Output must preserve absence of final newline"


def test_insert_preserves_final_newline_slash(tmp_path: Path) -> None:
    """Insert into C-like file with final newline → still has a final newline."""
    f: Path = tmp_path / "a.ts"
    f.write_text("console.log(1);\n", encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    out: str = "".join(lines)
    assert _ends_with_newline(out), "Output must preserve final newline"


def test_strip_preserves_final_newline_xml(tmp_path: Path) -> None:
    """Strip on XML preserves final newline parity."""
    f1: Path = tmp_path / "with_nl.xml"
    f2: Path = tmp_path / "no_nl.xml"

    with_nl: str = (
        '<?xml version="1.0"?>\n'
        f"<!-- {TOPMARK_START_MARKER} -->\n"
        "<!-- test:header -->\n"
        f"<!-- {TOPMARK_END_MARKER} -->\n"
        "<root/>\n"  # final newline
    )
    no_nl: str = (
        '<?xml version="1.0"?>\n'
        f"<!-- {TOPMARK_START_MARKER} -->\n"
        "<!-- test:header -->\n"
        f"<!-- {TOPMARK_END_MARKER} -->\n"
        "<root/>"  # no final newline
    )

    f1.write_text(with_nl, encoding="utf-8")
    f2.write_text(no_nl, encoding="utf-8")

    proc1: HeaderProcessor | None = get_processor_for_file(f1)
    proc2: HeaderProcessor | None = get_processor_for_file(f2)
    assert proc1 and proc2

    lines1: list[str] = f1.read_text(encoding="utf-8").splitlines(keepends=True)
    lines2: list[str] = f2.read_text(encoding="utf-8").splitlines(keepends=True)

    new1: list[str] = []
    _span1: tuple[int, int] | None = None
    diag1: StripDiagnostic
    new1, _span1, diag1 = proc1.strip_header_block(
        lines=lines1,
        span=None,
        newline_style="\n",  # the fixture uses LF
        ends_with_newline=True,  # with_nl: ends with "\n"
    )
    new2: list[str] = []
    _span2: tuple[int, int] | None = None
    diag2: StripDiagnostic
    new2, _span2, diag2 = proc2.strip_header_block(
        lines=lines2,
        span=None,
        newline_style="\n",  # the fixture uses LF
        ends_with_newline=False,  # no_nl: no trailing newline
    )

    out1: str = "".join(new1)
    out2: str = "".join(new2)
    assert diag1.kind == StripDiagKind.REMOVED
    assert diag2.kind == StripDiagKind.REMOVED
    assert _ends_with_newline(out1), "Strip must preserve final newline"
    assert not _ends_with_newline(out2), "Strip must preserve absence of final newline"
