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

import pytest

from tests.pipeline.conftest import make_pipeline_context, run_resolver, run_sniffer
from topmark.config import Config, MutableConfig
from topmark.pipeline.status import FsStatus
from topmark.pipeline.steps.sniffer import inspect_bom_shebang

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext


def test_sniff_skips_on_nul_byte_non_text(tmp_path: Path) -> None:
    """Sniffer must set SKIPPED_NOT_TEXT_FILE when a NUL byte is present."""
    # Include a NUL byte to trigger non-text detection.
    content: str = 'print("Hi There\0")'
    file: Path = tmp_path / "x.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # First resolve the file type
    ctx = run_resolver(ctx)

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.BINARY


def test_sniff_skips_when_bom_precedes_shebang(tmp_path: Path) -> None:
    """Sniffer must skip when a UTF-8 BOM appears before a shebang."""
    content: str = "\ufeff#!/usr/bin/env python3\nprint('hello')\n"
    file: Path = tmp_path / "bom_shebang.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG


def test_sniff_marks_empty_file(tmp_path: Path) -> None:
    """Sniffer must mark truly empty files as EMPTY_FILE and avoid further processing."""
    file: Path = tmp_path / "empty.py"
    # Create an empty file
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write("")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.EMPTY


def test_sniff_marks_not_found_when_disappears(tmp_path: Path) -> None:
    """Sniffer should mark SKIPPED_NOT_FOUND when the file disappears before read()."""
    file: Path = tmp_path / "vanishing.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write("print('hi')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    # Simulate a race: remove the file before reader executes
    file.unlink()
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.NOT_FOUND


def test_sniff_skips_on_invalid_utf8(tmp_path: Path) -> None:
    """Sniffer must mark non-text when decoding fails (invalid UTF-8)."""
    file: Path = tmp_path / "bad_utf8.py"
    bad = b"print('x')\n" + b"\xc3\x28"  # invalid 2-byte sequence
    with file.open("wb") as fh:
        fh.write(bad)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.UNICODE_DECODE_ERROR


def test_sniff_strict_mixed_newlines(tmp_path: Path) -> None:
    """Sniffer must report mixed line endings."""
    file: Path = tmp_path / "bad_utf8.py"
    mixed = "# A test file\r\n# with mixed\r# line endings\r\nprint('x')\n"  # mixed line endings
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(mixed)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS


# --- Unit test for _inspect_bom_shebang ---
@pytest.mark.parametrize(
    "payload, expected",
    [
        # Shebang at byte 0, no BOM
        (b"#!/usr/bin/env python\n", (False, True, False)),
        # UTF-8 BOM followed by shebang at offset 3
        (b"\xef\xbb\xbf#!/usr/bin/env python\n", (True, True, True)),
        # BOM present but no shebang
        (b"\xef\xbb\xbfprint('x')\n", (True, False, False)),
        # Shebang not at byte 0 or directly after BOM → not treated as shebang
        (b"  #!/usr/bin/env python\n", (False, False, False)),
    ],
)
def test_inspect_bom_shebang_variants(
    payload: bytes,
    expected: tuple[bool, bool, bool],
) -> None:
    """_inspect_bom_shebang should classify BOM and shebang ordering correctly.

    This focuses on the low-level bytes → flags behavior, independent of any
    `ProcessingContext` mutation or policy decisions in `SnifferStep`.
    """
    assert inspect_bom_shebang(payload) == expected
