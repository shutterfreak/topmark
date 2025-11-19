# topmark:header:start
#
#   project      : TopMark
#   file         : test_slash.py
#   file_relpath : tests/pipeline/processors/test_slash.py
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

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import (
    BlockSignatures,
    expected_block_lines_for,
    find_line,
    materialize_updated_lines,
    run_insert,
    run_writer,
)
from topmark.config import Config, MutableConfig
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline import runner
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic
from topmark.pipeline.status import HeaderStatus

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.pipeline.protocols import Step

logger: TopmarkLogger = get_logger(__name__)


@mark_pipeline
def test_slash_processor_basics(tmp_path: Path) -> None:
    """Basics: detect file type and confirm no pre-existing header.

    Given a ``.js`` source without a TopMark block, the processor resolution should
    map to a Slash-based type and the scanner should report no existing header.
    """
    f: Path = tmp_path / "app.js"
    f.write_text("console.log('hi');\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)
    assert ctx.file_type and ctx.file_type.name == "javascript"
    assert ctx.views.header is None


@mark_pipeline
def test_slash_processor_with_content_matcher_detects_jsonc_in_json(tmp_path: Path) -> None:
    """Detect JSON file is JSONC and confirm no pre-existing header.

    Given a ``.json`` source without a TopMark block, the processor resolution should
    map to a JSON with comments (via content matcher) and the scanner should report
    no existing header.
    """
    f: Path = tmp_path / "test.json"
    cfg: Config = MutableConfig.from_defaults().freeze()
    f.write_text("// JSON with comments\n" + json.dumps({"test": "Value", "try": True}))

    ctx: ProcessingContext = run_insert(f, cfg)
    assert ctx.file_type and ctx.file_type.name == "jsonc"
    assert ctx.views.header is None


@mark_pipeline
def test_slash_insert_top_and_trailing_blank(tmp_path: Path) -> None:
    """Insert a header at the top and ensure a trailing blank line follows.

    Verifies that the rendered block begins at index ``0`` and that the line after
    the block's end is blank, preserving readability in C-style sources.
    """
    f: Path = tmp_path / "main.ts"
    f.write_text("export const x = 1;\n")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(f)
    assert find_line(lines, sig["start_line"]) == 0
    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_slash_detect_existing_header(tmp_path: Path) -> None:
    """Detect an existing header and parse fields.

    Asserts inclusive header bounds (0-based) and that the parsed ``file`` field
    contains the expected value from the pre-seeded block.
    """
    f: Path = tmp_path / "lib.h"
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
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    pipeline: Sequence[Step] = Pipeline.CHECK.steps
    ctx = runner.run(
        ctx,
        pipeline,
        prune=False,  # We must inspect ctx_check.views.header
    )

    assert ctx.views.header is not None
    assert ctx.views.header.range == (0, 5)
    assert ctx.views.header.mapping and ctx.views.header.mapping.get("file") == "lib.h"
    ctx.views.release_all()  # Release the views


@mark_pipeline
@pytest.mark.parametrize(
    "header_fields, expected_status",
    [
        (
            "// bad header\n",  # Missing colon
            HeaderStatus.MALFORMED_ALL_FIELDS,
        ),
        (
            "// valid: header\n# bad header\n",  # Missing colon
            HeaderStatus.MALFORMED_SOME_FIELDS,
        ),
        (
            "// valid: header\n",  # Header OK
            HeaderStatus.DETECTED,
        ),
    ],
)
def test_slash_malformed_header_fields(
    tmp_path: Path,
    header_fields: str,
    expected_status: HeaderStatus,
) -> None:
    """Tolerate malformed field lines without crashing.

    Ensures the scanner records the header span but yields an empty/invalid field
    map and sets a non-OK header status (``MALFORMED`` or ``EMPTY``).

    Args:
        tmp_path (Path): Temporary path provided by pytest for test file creation.
        header_fields (str): Header fields for the test
        expected_status (HeaderStatus): expected HeaderStatus value for the test
    """
    f: Path = tmp_path / "bad.ts"
    f.write_text(
        f"// {TOPMARK_START_MARKER}\n// {header_fields}// {TOPMARK_END_MARKER}\nexport {{}}\n"
    )
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    pipeline: Sequence[Step] = Pipeline.CHECK.steps
    ctx = runner.run(ctx, pipeline)

    assert ctx.views.header is not None
    assert ctx.status.header == expected_status


@mark_pipeline
def test_slash_idempotent_reapply_no_diff(tmp_path: Path) -> None:
    """Re-applying insertion is a no-op (idempotent).

    After writing the first run's output back to disk, a second run must produce
    identical lines, yielding no further modifications.
    """
    f: Path = tmp_path / "idem.ts"
    f.write_text('{\n  // comment\n  "a": 1\n}\n')
    cfg: Config = MutableConfig.from_defaults().freeze()

    ctx1: ProcessingContext = run_insert(f, cfg)

    lines1: list[str] = materialize_updated_lines(ctx1)
    # Write results of first run to disk
    ctx1 = run_writer(ctx1)

    ctx2: ProcessingContext = run_insert(f, cfg)
    lines2: list[str] = materialize_updated_lines(ctx2)

    assert lines1 == lines2


@mark_pipeline
def test_slash_crlf_preserves_newlines(tmp_path: Path) -> None:
    """Preserve CRLF newlines on Windows-style inputs.

    Confirms that every output line retains ``CRLF`` when the file was written
    with ``CRLF`` line endings.
    """
    f: Path = tmp_path / "win.cpp"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("int main(){return 0;}\n")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} not CRLF: {ln!r}"


@mark_pipeline
def test_slash_strip_header_block_with_and_without_span(tmp_path: Path) -> None:
    """`strip_header_block` removes the block with or without explicit bounds.

    Validates both the explicit-span path and the auto-detection fallback and
    ensures the resulting content is identical across both paths.
    """
    from topmark.pipeline.processors import get_processor_for_file

    f: Path = tmp_path / "strip_me.js"
    f.write_text(
        f"// {TOPMARK_START_MARKER}\n// f\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n",
        encoding="utf-8",
    )
    proc: HeaderProcessor | None = get_processor_for_file(f)
    assert proc is not None
    lines: list[str] = f.read_text(encoding="utf-8").splitlines(keepends=True)

    new1: list[str] = []
    span1: tuple[int, int] | None = None
    diag1: StripDiagnostic
    new1, span1, diag1 = proc.strip_header_block(lines=lines, span=(0, 2))

    assert diag1.kind == StripDiagKind.REMOVED
    assert TOPMARK_START_MARKER not in "".join(new1)
    assert span1 == (0, 2)

    new2: list[str] = []
    span2: tuple[int, int] | None = None
    diag2: StripDiagnostic
    new2, span2, diag2 = proc.strip_header_block(lines=lines)

    assert diag2.kind == StripDiagKind.REMOVED
    assert new2 == new1 and span2 == (0, 2)


@mark_pipeline
def test_slash_replace_preserves_crlf(tmp_path: Path) -> None:
    """Ensure replace path preserves CRLF newlines for C++ sources.

    Given a C++ file with an existing TopMark header written using CRLF endings,
    the replacement header should maintain CRLF endings across all lines.

    Args:
        tmp_path (Path): Pytest fixture temporary directory.
    """
    f: Path = tmp_path / "r.cpp"
    with f.open("w", newline="\r\n") as fp:
        # Note: every "\n" will be replaced with the `newline` value specified: "\r\n"
        fp.write(f"// {TOPMARK_START_MARKER}\n// x\n// {TOPMARK_END_MARKER}\nint main(){{}}\n")
    ctx: ProcessingContext = run_insert(f, MutableConfig.from_defaults().freeze())
    lines: list[str] = materialize_updated_lines(ctx)

    for i, ln in enumerate(lines):
        if i < len(lines) - 1:
            assert ln.endswith("\r\n"), f"line {i} lost CRLF"
