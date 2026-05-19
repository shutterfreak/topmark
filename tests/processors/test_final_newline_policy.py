# topmark:header:start
#
#   project      : TopMark
#   file         : test_final_newline_policy.py
#   file_relpath : tests/processors/test_final_newline_policy.py
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

from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_insert
from tests.helpers.registry import resolve_processor_for_path
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.processors.types import StripDiagKind

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.processors.base import HeaderProcessor
    from topmark.processors.types import StripHeaderResult


def _ends_with_newline(text: str) -> bool:
    """Return True if text ends with LF or CR/LF."""
    return text.endswith("\n") or text.endswith("\r")


def test_insert_preserves_no_final_newline_pound(tmp_path: Path) -> None:
    """Insert into Python file without final newline → still no final newline."""
    f: Path = tmp_path / "a.py"
    # No final newline on purpose.
    f.write_text("print('x')", encoding="utf-8")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    out: str = "".join(lines)
    assert not _ends_with_newline(out), "Output must preserve absence of final newline"


def test_insert_preserves_final_newline_slash(tmp_path: Path) -> None:
    """Insert into C-like file with final newline → still has a final newline."""
    f: Path = tmp_path / "a.ts"
    f.write_text("console.log(1);\n", encoding="utf-8")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
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

    proc1: HeaderProcessor | None = resolve_processor_for_path(path=f1)
    proc2: HeaderProcessor | None = resolve_processor_for_path(path=f2)
    assert proc1 and proc2

    lines1: list[str] = f1.read_text(encoding="utf-8").splitlines(keepends=True)
    lines2: list[str] = f2.read_text(encoding="utf-8").splitlines(keepends=True)

    strip_result_1: StripHeaderResult = proc1.strip_header_block(
        lines=lines1,
        span=None,
        newline_style="\n",  # the fixture uses LF
        ends_with_newline=True,  # with_nl: ends with "\n"
    )
    strip_result_2: StripHeaderResult = proc2.strip_header_block(
        lines=lines2,
        span=None,
        newline_style="\n",  # the fixture uses LF
        ends_with_newline=False,  # no_nl: no trailing newline
    )

    out1: str = "".join(strip_result_1.lines)
    out2: str = "".join(strip_result_2.lines)
    assert strip_result_1.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result_2.diagnostic.kind == StripDiagKind.REMOVED
    assert _ends_with_newline(out1), "Strip must preserve final newline"
    assert not _ends_with_newline(out2), "Strip must preserve absence of final newline"
