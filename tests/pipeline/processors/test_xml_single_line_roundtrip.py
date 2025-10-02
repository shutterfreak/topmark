# topmark:header:start
#
#   project      : TopMark
#   file         : test_xml_single_line_roundtrip.py
#   file_relpath : tests/pipeline/processors/test_xml_single_line_roundtrip.py
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

from pathlib import Path
from typing import TYPE_CHECKING

from tests.pipeline.conftest import run_insert
from topmark.config import Config, MutableConfig
from topmark.pipeline.processors import get_processor_for_file

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor


def test_xml_single_line_insert_then_strip_preserves_layout(tmp_path: Path) -> None:
    """Round-trip keeps declaration intact and preserves no-FNL policy."""
    f: Path = tmp_path / "one.xml"
    original = '<?xml version="1.0"?><root/>'  # no trailing newline
    f.write_text(original, encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)
    after_insert: str = "".join(ctx.updated_file_lines or [])
    assert after_insert.startswith("\ufeff") or after_insert.startswith("<?xml"), (
        "Declaration must remain first logical line"
    )

    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None
    lines: list[str] = after_insert.splitlines(keepends=True)
    stripped_lines: list[str] = []
    _span: tuple[int, int] | None = None
    stripped_lines, _span = proc.strip_header_block(
        lines=lines,
        span=None,
        newline_style=ctx.newline_style,  # from ProcessingContext
        ends_with_newline=False,  # original was single-line without FNL
    )
    roundtrip: str = "".join(stripped_lines)
    assert roundtrip == original, "Round-trip must preserve single-line structure without FNL"
