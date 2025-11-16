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

import re
from pathlib import Path
from typing import TYPE_CHECKING

from tests.pipeline.conftest import materialize_updated_lines, run_insert
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_START_MARKER
from topmark.pipeline.processors import get_processor_for_file
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic
from topmark.pipeline.status import (
    ComparisonStatus,
    ContentStatus,
    GenerationStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor


def test_xml_prolog_and_body_on_same_line_blocked_by_policy(tmp_path: Path) -> None:
    """XML prolog and body on same line would reflow, blocked by policy."""
    f: Path = tmp_path / "one.xml"
    original = '<?xml version="1.0"?><root/>'  # no trailing newline
    f.write_text(original, encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    assert ctx.status.content == ContentStatus.SKIPPED_REFLOW
    assert ctx.flow.halt is True


def test_xml_prolog_and_body_on_same_line_alllowed_by_policy(tmp_path: Path) -> None:
    """XML prolog and body on same line would reflow, allowed by policy."""
    f: Path = tmp_path / "one.xml"
    original = '<?xml version="1.0"?><root/>'  # no trailing newline
    f.write_text(original, encoding="utf-8")

    draft: MutableConfig = MutableConfig.from_defaults()
    draft.policy.allow_reflow = True
    cfg: Config = draft.freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    after_insert: str = "".join(lines)

    assert ctx.status.generation == GenerationStatus.GENERATED
    assert ctx.status.comparison == ComparisonStatus.CHANGED
    assert any(TOPMARK_START_MARKER in line for line in lines)

    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None
    lines: list[str] = after_insert.splitlines(keepends=True)
    stripped_lines: list[str] = []
    _span: tuple[int, int] | None = None
    diag: StripDiagnostic
    stripped_lines, _span, diag = proc.strip_header_block(
        lines=lines,
        span=None,
        newline_style=ctx.newline_style,  # from ProcessingContext
        ends_with_newline=False,  # original was single-line without FNL
    )
    assert diag.kind == StripDiagKind.REMOVED
    roundtrip: str = "".join(stripped_lines)

    # Assert that original and roundtrip only differ in white space
    # The re.sub(r'\s+', '', ...) function removes all whitespace characters
    # (space, tab, newline, etc.) from both strings before comparison.
    assert re.sub(r"\s+", "", original) == re.sub(r"\s+", "", roundtrip)
