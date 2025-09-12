# topmark:header:start
#
#   file         : test_slash.py
#   file_relpath : tests/pipeline/processors/test_slash.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the SlashHeaderProcessor (C-style ``//`` line comments).

Covers basic detection, insertion at top with proper trailing blank, detection
of existing headers, tolerance for malformed blocks, CRLF newline preservation,
idempotent re-application, and `strip_header_block` behavior with and without
explicit spans.
"""

from pathlib import Path

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import expected_block_lines_for, find_line, run_insert
from topmark.config import MutableConfig
from topmark.config.logging import get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline import runner
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.pipelines import get_pipeline

logger = get_logger(__name__)


@mark_pipeline
def test_slash_processor_basics(tmp_path: Path) -> None:
    """Basics: detect file type and confirm no pre-existing header.

    Given a ``.js`` source without a TopMark block, the processor resolution should
    map to a Slash-based type and the scanner should report no existing header.
    """
    f = tmp_path / "app.js"
    f.write_text("console.log('hi');\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)
    assert ctx.file_type and ctx.file_type.name in {"javascript", "js"}  # adjust to your registry
    assert ctx.existing_header_range is None


@mark_pipeline
def test_slash_insert_top_and_trailing_blank(tmp_path: Path) -> None:
    """Insert a header at the top and ensure a trailing blank line follows.

    Verifies that the rendered block begins at index ``0`` and that the line after
    the block's end is blank, preserving readability in C-style sources.
    """
    f = tmp_path / "main.ts"
    f.write_text("export const x = 1;\n")
    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    assert find_line(lines, sig["start_line"]) == 0
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_slash_detect_existing_header(tmp_path: Path) -> None:
    """Detect an existing header and parse fields.

    Asserts inclusive header bounds (0-based) and that the parsed ``file`` field
    contains the expected value from the pre-seeded block.
    """
    f = tmp_path / "lib.h"
    f.write_text(
        f"// {TOPMARK_START_MARKER}\n"
        "//\n"
        "//   file: lib.h\n"
        "//   license: MIT\n"
        "//\n"
        f"// {TOPMARK_END_MARKER}\n"
        "\n"
        "#pragma once\n"
    )
    cfg = MutableConfig.from_defaults().freeze()
    ctx = ProcessingContext.bootstrap(path=f, config=cfg)
    steps = get_pipeline("check")
    ctx = runner.run(ctx, steps)

    assert ctx.existing_header_range == (0, 5)
    assert ctx.existing_header_dict and ctx.existing_header_dict.get("file") == "lib.h"


@mark_pipeline
def test_slash_malformed_header(tmp_path: Path) -> None:
    """Tolerate malformed field lines without crashing.

    Ensures the scanner records the header span but yields an empty/invalid field
    map and sets a non-OK header status (``MALFORMED`` or ``EMPTY``).
    """
    f = tmp_path / "bad.ts"
    f.write_text(
        f"// {TOPMARK_START_MARKER}\n"
        "//   file bad.ts\n"  # missing ':'
        f"// {TOPMARK_END_MARKER}\n"
        "export {}\n"
    )
    cfg = MutableConfig.from_defaults().freeze()
    ctx = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = runner.run(ctx, get_pipeline("check"))

    from topmark.pipeline.context import HeaderStatus

    assert ctx.existing_header_range == (0, 2)
    assert ctx.existing_header_dict in ({}, None)
    assert ctx.status.header in {HeaderStatus.MALFORMED, HeaderStatus.EMPTY}


@mark_pipeline
def test_slash_idempotent_reapply_no_diff(tmp_path: Path) -> None:
    """Re-applying insertion is a no-op (idempotent).

    After writing the first run's output back to disk, a second run must produce
    identical lines, yielding no further modifications.
    """
    f = tmp_path / "idem.ts"
    f.write_text('{\n  // comment\n  "a": 1\n}\n')
    cfg = MutableConfig.from_defaults().freeze()

    ctx1 = run_insert(f, cfg)
    with f.open("w", encoding="utf-8", newline="") as fp:
        fp.write("".join(ctx1.updated_file_lines or []))
    ctx2 = run_insert(f, cfg)

    assert (ctx2.updated_file_lines or []) == (ctx1.updated_file_lines or [])


@mark_pipeline
def test_slash_crlf_preserves_newlines(tmp_path: Path) -> None:
    """Preserve CRLF newlines on Windows-style inputs.

    Confirms that every output line retains ``CRLF`` when the file was written
    with ``CRLF`` line endings.
    """
    f = tmp_path / "win.cpp"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("int main(){return 0;}\n")
    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    for i, ln in enumerate(ctx.updated_file_lines or []):
        assert ln.endswith("\r\n"), f"line {i} not CRLF: {ln!r}"


@mark_pipeline
def test_slash_strip_header_block_with_and_without_span(tmp_path: Path) -> None:
    """`strip_header_block` removes the block with or without explicit bounds.

    Validates both the explicit-span path and the auto-detection fallback and
    ensures the resulting content is identical across both paths.
    """
    from topmark.pipeline.processors import get_processor_for_file

    f = tmp_path / "strip_me.js"
    f.write_text(
        f"// {TOPMARK_START_MARKER}\n// f\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n",
        encoding="utf-8",
    )
    proc = get_processor_for_file(f)
    assert proc is not None
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)

    new1, span1 = proc.strip_header_block(lines=lines, span=(0, 2))
    assert TOPMARK_START_MARKER not in "".join(new1)
    assert span1 == (0, 2)

    new2, span2 = proc.strip_header_block(lines=lines)
    assert new2 == new1 and span2 == (0, 2)


@mark_pipeline
def test_slash_replace_preserves_crlf(tmp_path: Path) -> None:
    """Ensure replace path preserves CRLF newlines for C++ sources.

    Given a C++ file with an existing TopMark header written using CRLF endings,
    the replacement header should maintain CRLF endings across all lines.

    Args:
        tmp_path (Path): Pytest fixture temporary directory.
    """
    f = tmp_path / "r.cpp"
    with f.open("w", newline="\r\n") as fp:
        # Note: every "\n" will be replaced with the `newline` value specified: "\r\n"
        fp.write(f"// {TOPMARK_START_MARKER}\n// x\n// {TOPMARK_END_MARKER}\nint main(){{}}\n")
    ctx = run_insert(f, MutableConfig.from_defaults().freeze())
    for i, ln in enumerate(ctx.updated_file_lines or []):
        if i < len(ctx.updated_file_lines or []) - 1:
            assert ln.endswith("\r\n"), f"line {i} lost CRLF"
