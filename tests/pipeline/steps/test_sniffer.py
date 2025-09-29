# topmark:header:start
#
#   project      : TopMark
#   file         : test_sniffer.py
#   file_relpath : tests/pipeline/steps/test_sniffer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the `sniffer` pipeline step.

This suite verifies the lightweight pre-read behaviors that occur between
`resolver.resolve()` and `reader.read()`:
- existence/permission checks and EMPTY_FILE detection
- fast binary sniff (NUL-byte heuristic)
- BOM and shebang ordering, with policy enforcement when BOM precedes shebang
- quick newline histogram and strict mixed-newlines refusal (policy #1)

The sniffer must *not* populate `ctx.file_lines`; it only annotates the
context and can short-circuit with a non-RESOLVED status when policy dictates.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config import Config, MutableConfig
from topmark.pipeline.context import ContentStatus, FsStatus, ProcessingContext
from topmark.pipeline.steps.resolver import resolve
from topmark.pipeline.steps.sniffer import sniff

if TYPE_CHECKING:
    from pathlib import Path


def test_sniff_skips_on_nul_byte_non_text(tmp_path: Path) -> None:
    """Sniffer must set SKIPPED_NOT_TEXT_FILE when a NUL byte is present."""
    # Include a NUL byte to trigger non-text detection.
    content: str = 'print("Hi There\0")'
    f: Path = tmp_path / "x.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)

    # First resolve the file type
    ctx = resolve(ctx)

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None

    ctx = sniff(ctx)
    assert ctx.status.content == ContentStatus.SKIPPED_NOT_TEXT_FILE


def test_sniff_skips_when_bom_precedes_shebang(tmp_path: Path) -> None:
    """Sniffer must skip when a UTF-8 BOM appears before a shebang."""
    content: str = "\ufeff#!/usr/bin/env python3\nprint('hello')\n"
    f: Path = tmp_path / "bom_shebang.py"
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.file_type is not None
    ctx = sniff(ctx)

    assert ctx.status.content == ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG


def test_sniff_marks_empty_file(tmp_path: Path) -> None:
    """Sniffer must mark truly empty files as EMPTY_FILE and avoid further processing."""
    f: Path = tmp_path / "empty.py"
    # Create an empty file
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write("")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.file_type is not None
    ctx = sniff(ctx)
    assert ctx.status.fs == FsStatus.EMPTY


def test_sniff_marks_not_found_when_disappears(tmp_path: Path) -> None:
    """Sniffer should mark SKIPPED_NOT_FOUND when the file disappears before read()."""
    f: Path = tmp_path / "vanishing.py"
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write("print('hi')\n")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.file_type is not None
    # Simulate a race: remove the file before reader executes
    f.unlink()
    ctx = sniff(ctx)
    assert ctx.status.fs == FsStatus.NOT_FOUND


def test_sniff_skips_on_invalid_utf8(tmp_path: Path) -> None:
    """Sniffer must mark non-text when decoding fails (invalid UTF-8)."""
    f: Path = tmp_path / "bad_utf8.py"
    bad = b"print('x')\n" + b"\xc3\x28"  # invalid 2-byte sequence
    with f.open("wb") as fh:
        fh.write(bad)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.file_type is not None
    ctx = sniff(ctx)
    assert ctx.status.content == ContentStatus.SKIPPED_NOT_TEXT_FILE
