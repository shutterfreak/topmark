# topmark:header:start
#
#   project      : TopMark
#   file         : test_cblock.py
#   file_relpath : tests/pipeline/processors/test_cblock.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the CBlockHeaderProcessor (C-style ``/* ... */`` block comments).

Covers:
- basic detection and processor resolution for CSS-like files,
- insertion at top with proper trailing blank,
- detection of existing headers (with and without the per-line ``*`` on directives),
- idempotent re-application (no-op on second run),
- CRLF newline preservation,
- strip behavior with and without explicit spans,
- placement when a pre-existing banner block comment exists (TopMark header should precede it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import BlockSignatures, expected_block_lines_for, find_line, run_insert
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline import runner
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.pipelines import get_pipeline
from topmark.pipeline.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.pipeline.contracts import Step
    from topmark.pipeline.processors.base import HeaderProcessor


@mark_pipeline
def test_cblock_processor_basics(tmp_path: Path) -> None:
    """Basics: resolve to a C-block style processor and no pre-existing header."""
    f: Path = tmp_path / "styles.css"
    f.write_text("body { margin: 0; }\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    # Use the short insert helper which runs resolver+reader+scanner, but we only
    # need to assert the basics exposed by the scan results.
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    steps: Sequence[Step] = get_pipeline("check")
    ctx = runner.run(ctx, steps)

    assert ctx.file_type is not None
    # Depending on registry naming you might use "css"
    assert ctx.file_type.name in {"css"}
    assert ctx.existing_header_range is None


@mark_pipeline
@pytest.mark.parametrize(
    "ext,body",
    [
        (".css", "body{margin:0}\n"),
        (".scss", "$x: 1;\nbody{margin:$x}\n"),
        (".less", "@c: #abc;\n"),
        (".styl", "body\n  margin 0\n"),
        (".sql", "SELECT 1;\n"),
        (".sol", "pragma solidity ^0.8.0;\n"),
    ],
)
def test_cblock_all_registrations_insert_and_trailing_blank(
    tmp_path: Path, ext: str, body: str
) -> None:
    """Insert a header at the top and ensure a trailing blank line follows."""
    f: Path = tmp_path / f"sample{ext}"
    f.write_text(body, encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = ctx.updated_file_lines or []
    sig: BlockSignatures = expected_block_lines_for(f)

    # Block-open should be first, start line second
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    # Ensure the line after the block close is blank
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_cblock_detect_existing_header_with_star_prefix(tmp_path: Path) -> None:
    """Detect an existing C-block header that was produced by TopMark itself."""
    f: Path = tmp_path / "existing.css"
    f.write_text(
        "body{color:#333}\n",
        encoding="utf-8",
    )  # No header yet

    cfg: Config = MutableConfig.from_defaults().freeze()

    # 1) Insert a canonical header using the updater path
    ctx_insert: ProcessingContext = run_insert(f, cfg)

    with f.open("w", encoding="utf-8", newline="") as fp:
        fp.write("".join(ctx_insert.updated_file_lines or []))

    # 2) Re-run the 'check' pipeline to ensure the scanner detects the header
    ctx_check: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    steps: Sequence[Step] = get_pipeline("check")
    ctx_check = runner.run(ctx_check, steps)

    assert ctx_check.existing_header_range is not None
    assert ctx_check.existing_header_dict is not None
    # The file field is empty by default in tests, so just assert dict presence


@mark_pipeline
def test_cblock_detect_existing_header_without_star_on_directives(tmp_path: Path) -> None:
    """Scanner tolerates directives without '*' inside the block."""
    f: Path = tmp_path / "nostar.css"
    f.write_text(
        "p{margin:0}\n",
        encoding="utf-8",
    )

    cfg: Config = MutableConfig.from_defaults().freeze()

    # Generate a canonical header
    ctx: ProcessingContext = run_insert(f, cfg)
    lines: list[str] = ctx.updated_file_lines or []

    # Find directive lines and strip the leading '*' just on start/end lines
    new_lines: list[str] = []
    ln: str
    for ln in lines:
        s: str = ln.lstrip()
        if s.startswith("*"):
            core: str = s[1:].lstrip()
            if core.startswith(TOPMARK_START_MARKER) or core.startswith(TOPMARK_END_MARKER):
                # Rebuild the line without the '*' (preserve original leading whitespace)
                prefix: str = ln[: len(ln) - len(s)]
                ln = prefix + core
        new_lines.append(ln)

    f.write_text("".join(new_lines), encoding="utf-8")

    # Now the scanner should still detect it
    ctx2: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    steps: Sequence[Step] = get_pipeline("check")
    ctx2 = runner.run(ctx2, steps)
    assert ctx2.existing_header_range is not None


@mark_pipeline
def test_cblock_crlf_preserves_newlines(tmp_path: Path) -> None:
    """Preserve CRLF newlines on Windows-style CSS inputs."""
    f: Path = tmp_path / "win.less"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("/* palette */\n")
        fp.write("@c: #abc;\n")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    for i, ln in enumerate(ctx.updated_file_lines or []):
        assert ln.endswith("\r\n"), f"line {i} not CRLF: {ln!r}"


@mark_pipeline
def test_cblock_strip_header_block_with_and_without_span(tmp_path: Path) -> None:
    """`strip_header_block` removes the block with or without explicit bounds."""
    from topmark.pipeline.processors import get_processor_for_file

    f: Path = tmp_path / "strip_me.css"
    f.write_text(
        f"/*\n * {TOPMARK_START_MARKER}\n * h\n * {TOPMARK_END_MARKER}\n */\nbody{{margin:0}}\n",
        encoding="utf-8",
    )

    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None

    lines: list[str] = f.read_text(encoding="utf-8").splitlines(keepends=True)

    # Explicit span (block occupies lines 0..4)
    new1: list[str] = []
    span1: tuple[int, int] | None = None
    new1, span1 = proc.strip_header_block(lines=lines, span=(0, 4))
    assert TOPMARK_START_MARKER not in "".join(new1)
    assert span1 == (0, 4)

    # Auto-detect span
    new2: list[str] = []
    span2: tuple[int, int] | None = None
    new2, span2 = proc.strip_header_block(lines=lines)
    assert new2 == new1 and span2 == (0, 4)


@mark_pipeline
def test_cblock_banner_comment_after_header(tmp_path: Path) -> None:
    """Header must precede any pre-existing banner comment."""
    f = tmp_path / "banner.css"
    f.write_text("/* existing:license banner */\nhtml{font-size:16px}\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = ctx.updated_file_lines or []
    sig: BlockSignatures = expected_block_lines_for(f)

    # Header must start at very top
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1

    # The pre-existing banner should appear after the TopMark header block
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        banner_idx: int = find_line(lines, "/* existing:license banner */")
        assert banner_idx > close_idx


@mark_pipeline
def test_cblock_strip_header_block_generated(tmp_path: Path) -> None:
    """strip_header_block removes a canonical TopMark C-block header."""
    from topmark.pipeline.processors import get_processor_for_file

    f: Path = tmp_path / "strip_me.css"
    f.write_text("html{font-size:16px}\n")
    cfg: Config = MutableConfig.from_defaults().freeze()

    # Generate a canonical header
    ctx: ProcessingContext = run_insert(f, cfg)
    lines: list[str] = ctx.updated_file_lines or []
    f.write_text("".join(lines), encoding="utf-8")

    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None

    # Let processor auto-detect the span and strip
    new_lines: list[str]
    span: tuple[int, int] | None = None
    new_lines, span = proc.strip_header_block(lines=f.read_text().splitlines(keepends=True))
    assert span is not None
    assert "topmark:start" not in "".join(new_lines)


@mark_pipeline
def test_cblock_not_at_top_insertion_single_leading_blank(tmp_path: Path) -> None:
    """When inserting *not* at the top, ensure exactly one leading blank is added.

    We simulate a case where some pre-existing line (e.g., a tool banner) must
    remain *before* the TopMark header block. The processor should inject one
    blank line between that line and the header preamble.
    """
    from topmark.pipeline.processors import get_processor_for_file

    # Use a non-CSS extension that still maps to the CBlockHeaderProcessor
    f: Path = tmp_path / "not_top.sql"
    original: list[str] = [
        "/* PRELUDE: keep before header */\n",
        "SELECT 1;\n",
    ]
    f.write_text("".join(original), encoding="utf-8")

    # Resolve processor & basics
    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None, "Processor must resolve for .sql"
    cfg: Config = MutableConfig.from_defaults().freeze()

    # Render canonical header lines (no fields needed for structure check)
    header_values: dict[str, str] = {field: "" for field in cfg.header_fields}
    newline = "\n"
    rendered_header: list[str] = proc.render_header_lines(
        header_values, cfg, newline, header_indent_override=None
    )

    # Ask the processor to prepare insertion at index 1 (i.e., after prelude line)
    prepared: list[str] = proc.prepare_header_for_insertion(
        original_lines=original, insert_index=1, rendered_header_lines=rendered_header
    )

    # Build the final output to check exact placement
    out: list[str] = original[:1] + prepared + original[1:]

    # Expect: line 0 = prelude, line 1 = blank, line 2 = block_open, line 3 = start marker
    sig: BlockSignatures = expected_block_lines_for(f, newline=newline)

    # 0) Prelude preserved
    assert out[0] == original[0]

    # 1) Exactly one blank line directly before the header preamble
    assert out[1].strip() == "", "must insert a single leading blank before the header"
    # and the next line is the header's block-open (no double blank)
    assert "block_open" in sig
    assert out[2].rstrip("\r\n") == sig["block_open"]

    # 2) Start marker immediately follows block_open
    assert out[3].rstrip("\r\n") == sig["start_line"]

    # 3) After the header closes, we still keep a trailing blank (per policy)
    assert "block_close" in sig
    close_idx: int = find_line(out, sig["block_close"])
    assert close_idx + 1 < len(out) and out[close_idx + 1].strip() == ""

    # 4) Original content that was after insert_index must still follow
    #    (accounting for: prelude(0), blank(1), header block(~N lines), blank)
    assert out[-1].rstrip("\r\n") == "SELECT 1;"
