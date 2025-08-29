# topmark:header:start
#
#   file         : test_stripper.py
#   file_relpath : tests/pipeline/steps/test_stripper.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""
Unit tests for the `stripper` pipeline step.

These tests validate that the step removes the TopMark header using the
scanner-provided header span and that it trims exactly one leading blank
line when the header starts at the top of the file. The tests bootstrap a
minimal `ProcessingContext` without running the full pipeline.
"""

from pathlib import Path

from topmark.config import Config
from topmark.pipeline.context import HeaderStatus, ProcessingContext
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.steps.stripper import strip


def test_stripper_uses_span_and_trims_leading_blank(tmp_path: Path) -> None:
    """When span is provided, stripper should remove exactly that region and trim."""
    lines = [
        "# topmark:header:start\n",
        "# h\n",
        "# topmark:header:end\n",
        "\n",
        "code\n",
    ]
    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=(tmp_path / "x.py"), config=cfg)
    ctx.file_lines = lines
    # Use the base processor; removal relies on span and generic bounds logic.
    ctx.header_processor = HeaderProcessor()
    ctx.existing_header_range = (0, 2)  # as provided by scanner

    # ✅ Simulate scanner result so stripper proceeds
    ctx.status.header = HeaderStatus.DETECTED

    ctx = strip(ctx)
    # After stripping, only the code line should remain; statuses updated accordingly.
    assert ctx.updated_file_lines == ["code\n"]
    assert ctx.status.strip.name == "READY"
    assert ctx.status.header is HeaderStatus.DETECTED
