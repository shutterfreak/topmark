# topmark:header:start
#
#   file         : test_bom_newline_matrix.py
#   file_relpath : tests/pipeline/processors/test_bom_newline_matrix.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Newline/BOM preservation matrix for insert and strip paths.

This module validates that TopMark preserves a file's newline style (LF or CRLF)
when **inserting** a header and when **stripping** an existing header. The tests
cover multiple processors (Pound `*.py`, Slash `*.ts`, and XML/HTML) and assert
that every emitted line (except the last) retains the original newline sequence.

Notes:
* The insert tests seed a minimal file and run the insert path via the test
  helper `run_insert`.
* The strip tests build a header+body fixture with the requested newline style
  and exercise `strip_header_block`, asserting preserved newlines in the result.

These tests are marked with `@pytest.mark.pipeline` and are parameterized across
extensions and newline styles for broad coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.pipeline.conftest import run_insert
from topmark.config import Config
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

mark_pipeline = pytest.mark.pipeline


@pytest.mark.parametrize(
    "ext, pre, post",
    [
        (".py", "# ", "\n"),
        (".ts", "// ", "\n"),
        (".html", "<!-- ", " -->\n"),
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])  # LF and CRLF
@mark_pipeline
def test_insert_preserves_newline_style(
    tmp_path: Path, ext: str, pre: str, post: str, newline: str
) -> None:
    r"""Header insertion should preserve the file's newline style.

    Creates an empty-ish file for each processor type, runs insertion, and
    verifies every output line (except possibly the last) ends with the
    original newline sequence.

    Args:
        tmp_path: Temporary directory.
        ext: File extension mapping to processor.
        pre: Comment prefix used inside the test for clarity.
        post: Comment suffix for block comments (HTML), or ``\n`` otherwise.
        newline: The intended newline sequence for the file under test.
    """
    f = tmp_path / f"nstyle{ext}"
    with f.open("w", encoding="utf-8", newline=newline) as fp:
        fp.write(f"{pre}seed{post}")

    ctx = run_insert(f, Config.from_defaults())
    lines = ctx.updated_file_lines or []
    for i, ln in enumerate(lines):
        if i < len(lines) - 1:
            assert ln.endswith(newline), f"line {i} lost newline style"


@pytest.mark.parametrize(
    "ext, header_open, header_line, header_close, body",
    [
        (
            ".py",
            f"# {TOPMARK_START_MARKER}\n",
            "# f\n",
            f"# {TOPMARK_END_MARKER}\n",
            "print('x')\n",
        ),
        (
            ".ts",
            f"// {TOPMARK_START_MARKER}\n",
            "// f\n",
            f"// {TOPMARK_END_MARKER}\n",
            "export {}\n",
        ),
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])  # LF and CRLF
@mark_pipeline
def test_strip_preserves_newline_style(
    tmp_path: Path,
    ext: str,
    header_open: str,
    header_line: str,
    header_close: str,
    body: str,
    newline: str,
) -> None:
    r"""Stripping a header should preserve newline style of the remaining file.

    Seeds a file with a header block and a single body line using the requested
    newline style, runs the strip pipeline (`topmark strip` behavior), and
    verifies the remaining lines still use the same newline sequence.

    Args:
        tmp_path: Temporary directory.
        ext: Processor extension.
        header_open: Start marker line (with ``\n``).
        header_line: Payload line (with ``\n``).
        header_close: End marker line (with ``\n``).
        body: Body line (with ``\n``).
        newline: Newline sequence to enforce on disk.
    """
    # Build the content replacing internal newlines by the chosen style
    content = (header_open + header_line + header_close + body).replace("\n", newline)
    f = tmp_path / f"strip{ext}"
    with f.open("w", encoding="utf-8", newline="") as fp:
        fp.write(content)

    # Emulate strip pipeline: scanner -> stripper -> updater fast-path
    from topmark.pipeline.processors import get_processor_for_file

    proc = get_processor_for_file(f)
    assert proc is not None
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)

    new_lines, span = proc.strip_header_block(lines=lines)
    assert span is not None

    # Simulate updater fast-path BOM/newline handling via the context defaults
    # (here we don't feed through the full pipeline; just assert newline style).
    for i, ln in enumerate(new_lines):
        if i < len(new_lines) - 1:
            assert ln.endswith(newline), f"line {i} lost newline style"
