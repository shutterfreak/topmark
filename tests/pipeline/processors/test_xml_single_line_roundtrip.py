# topmark:header:start
#
#   file         : test_xml_single_line_roundtrip.py
#   file_relpath : tests/pipeline/processors/test_xml_single_line_roundtrip.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""XML char-offset insert/strip round-trip without trailing newline.

Covers the tricky single-line XML case:
- XML declaration + root element on the same physical line (no trailing newline).
- Insert via default command (char-offset policy).
- Strip via processor fast-path.
- Round-trip preserves structure and absence of final newline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.pipeline.conftest import run_insert
from topmark.config import Config
from topmark.pipeline.processors import get_processor_for_file

if TYPE_CHECKING:
    from pathlib import Path


def test_xml_single_line_insert_then_strip_preserves_layout(tmp_path: Path) -> None:
    """Round-trip keeps declaration intact and preserves no-FNL policy."""
    f = tmp_path / "one.xml"
    original = '<?xml version="1.0"?><root/>'  # no trailing newline
    f.write_text(original, encoding="utf-8")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)
    after_insert = "".join(ctx.updated_file_lines or [])
    assert after_insert.startswith("\ufeff") or after_insert.startswith("<?xml"), (
        "Declaration must remain first logical line"
    )

    proc = get_processor_for_file(f)
    assert proc is not None
    lines = after_insert.splitlines(keepends=True)
    stripped_lines, _ = proc.strip_header_block(lines=lines, span=None)
    roundtrip = "".join(stripped_lines)
    assert roundtrip == original, "Round-trip must preserve single-line structure without FNL"
