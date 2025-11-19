# topmark:header:start
#
#   project      : TopMark
#   file         : test_slash_indent.py
#   file_relpath : tests/pipeline/processors/test_slash_indent.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Indentation behavior for `SlashHeaderProcessor` (JSONC).

This module focuses on **pre-prefix** indentation preservation ("header_indent",
spaces before ``//``) and **after-prefix** indentation (``line_indent``, spaces
after ``//`` before the field text) for JSON-with-comments inputs.

Scenarios covered:
  * Insertion at the top: header should be inserted at column 0 by default
    (no pre-prefix indentation) and should be followed by exactly one blank line.
  * Replacement: if an existing TopMark header is indented (pre-prefix spaces
    before ``//``), the replacement should preserve that indentation while
    keeping the processor's standard after-prefix spacing for fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import (
    BlockSignatures,
    expected_block_lines_for,
    find_line,
    materialize_updated_lines,
    run_insert,
)
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline import runner
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.pipelines import Pipeline

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.pipeline.protocols import Step


@mark_pipeline
def test_jsonc_insert_at_top_with_no_pre_prefix_indent(tmp_path: Path) -> None:
    """JSONC insertion starts at column 0 and adds one blank line after the block.

    The file is recognized as JSONC via a user comment line (``// note``).
    The header must be inserted before that line, starting at index 0, and
    header lines must begin with ``//`` (no leading spaces).
    """
    f: Path = tmp_path / "settings.json"
    f.write_text('// user note\n{\n  "a": 1\n}\n', encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(f)

    # Header starts at the very top
    assert find_line(lines, sig["start_line"]) == 0

    # The header's start line has no pre-prefix indent (must start with //)
    start_line: str = lines[0].rstrip("\r\n")
    assert start_line.startswith("// ") or start_line == "//"  # allow minimal forms

    # Exactly one blank line after the block
    end_idx: int = find_line(lines, sig["end_line"])  # inclusive end marker
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_jsonc_replace_preserves_pre_prefix_indent(tmp_path: Path) -> None:
    """Replacement preserves pre-prefix indentation of an existing TopMark header.

    We seed a TopMark header indented by four spaces before the ``//`` prefix and
    verify the replacement retains those four spaces, while using the processor's
    standard after-prefix spacing for the field lines.
    """
    f: Path = tmp_path / "indented.json"
    indent = "    "  # four spaces before prefix
    seeded: str = (
        f"{indent}// {TOPMARK_START_MARKER}\n"
        f"{indent}//\n"
        f"{indent}//   file        : indented.json\n"
        f"{indent}//   license     : MIT\n"
        f"{indent}//\n"
        f"{indent}// {TOPMARK_END_MARKER}\n"
        '{\n  "k": 1\n}\n'
    )
    f.write_text(seeded, encoding="utf-8")

    cfg: Config = MutableConfig.from_defaults().freeze()
    # Run the full check pipeline to exercise scan + replace
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    pipeline: Sequence[Step] = Pipeline.CHECK_APPLY.steps
    ctx = runner.run(ctx, pipeline, prune=False)

    out: list[str] = materialize_updated_lines(ctx)
    # Start marker line should still carry the same pre-prefix indent
    start_line: str = out[0].rstrip("\r\n")
    assert start_line.startswith(indent + "//"), start_line

    # A representative field line should show after-prefix spacing of two spaces
    # (processor default), e.g. "//   file: value" where exactly two spaces follow
    # the prefix before the field text alignment logic runs.
    # Grab the first non-marker, non-blank header line.
    # Preamble layout: START, blank; then fields...
    i: int = 0
    while i < len(out) and not out[i].lstrip().startswith("//"):
        i += 1
    # Move to first field line after the blank line following START
    # Find the blank after start
    while i < len(out) and TOPMARK_START_MARKER not in out[i]:
        i += 1
    # next is blank
    i += 2
    field_line: str = out[i].rstrip("\r\n")
    # It must still have the pre-prefix indent
    assert field_line.startswith(indent + "//"), field_line
    # And there should be at least two spaces after the prefix before the field name
    after_prefix: str = field_line[len(indent + "//") :]
    assert after_prefix.startswith("  "), after_prefix


@mark_pipeline
def test_jsonc_replace_keeps_crlf_and_indent(tmp_path: Path) -> None:
    """Replacement keeps CRLF line endings and preserved pre-prefix indent."""
    f: Path = tmp_path / "crlf_indented.json"
    indent = "\t\t"  # tabs are allowed as pre-prefix indent
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write(
            f"{indent}// {TOPMARK_START_MARKER}\n"
            f"{indent}//\n"
            f"{indent}//   file: crlf_indented.json\n"
            f"{indent}//\n"
            f"{indent}// {TOPMARK_END_MARKER}\n"
            '{\n  "x": 2\n}\n'
        )

    ctx: ProcessingContext = run_insert(f, MutableConfig.from_defaults().freeze())
    out: list[str] = materialize_updated_lines(ctx)

    # Preserve CRLF
    for i, ln in enumerate(out):
        assert ln.endswith("\r\n"), f"line {i} not CRLF: {ln!r}"

    # Preserve pre-prefix indent
    assert out[0].startswith(indent + "//"), out[0]
