# topmark:header:start
#
#   project      : TopMark
#   file         : test_idempotency.py
#   file_relpath : tests/pipeline/processors/test_idempotency.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Golden behavior guards: idempotency and whitespace policy invariants."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.pipeline.conftest import run_insert
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context import ProcessingContext


# Reuse the helper from an existing test module to execute the insert pipeline.
# This avoids duplicating runner setup logic.


@pytest.mark.parametrize(
    "filename, content",
    [
        ("idem.py", "print('hello')\n"),
        ("script.py", "#!/usr/bin/env python3\n# coding: utf-8\nprint(1)\n"),  # Pound/line-comment
        ("app.js", "console.log('hi');\n"),  # Slash/line-comment
        ("main.c", "int main(){return 0;}\n"),  # C-block
        ("doc.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<root/>\n'),  # XML char-offset
        ("idem.html", "<html><body>hi</body></html>\n"),
        ("idem.scss", "$x: 1;\nbody{margin:$x}\n"),
    ],
)
def test_idempotent_double_insert(tmp_path: Path, filename: str, content: str) -> None:
    """Running the insert pipeline twice should produce identical output."""
    f: Path = tmp_path / filename
    f.write_text(content)

    cfg: Config = MutableConfig.from_defaults().freeze()

    # First run inserts a header (if not present yet)
    ctx1: ProcessingContext = run_insert(f, cfg)
    lines1: list[str] = ctx1.updated_file_lines or []

    # Write updates to file
    with f.open("w", encoding="utf-8", newline="") as fp:
        fp.write("".join(lines1))

    # Second run should be a no-op (idempotent)
    ctx2: ProcessingContext = run_insert(f, cfg)
    lines2: list[str] = ctx2.updated_file_lines or []

    assert lines2 == lines1, "Second run must be a no-op (idempotent)"
    # Header should exist after first insert; guard it lightly
    assert ctx1.existing_header_range is not None or ctx2.existing_header_range is not None


@pytest.mark.parametrize(
    "filename, content",
    [
        ("script.py", "print(1)\n"),  # Pound/line-comment
        ("app.js", "console.log('hi');\n"),  # Slash/line-comment
        ("main.c", "int main(){return 0;}\n"),  # C-block
    ],
)
def test_blank_line_after_header_for_line_and_block(
    tmp_path: Path, filename: str, content: str
) -> None:
    """There is exactly one blank line after the inserted header block."""
    f: Path = tmp_path / filename
    f.write_text(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = ctx.updated_file_lines or []

    # Find the line index of the end-of-header marker (comment-wrapped).
    end_idx = -1
    for i, line in enumerate(lines):
        if TOPMARK_END_MARKER in line:
            end_idx: int = i
            break

    assert end_idx >= 0, "inserted header must contain an end marker"

    # Next line should be blank, and the following should be non-blank (if any)
    if end_idx + 1 < len(lines):
        assert lines[end_idx + 1].strip() == ""
    if end_idx + 2 < len(lines):
        assert lines[end_idx + 2].strip() != ""
