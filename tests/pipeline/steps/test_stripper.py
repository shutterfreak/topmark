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

import pathlib

from topmark.config import Config


def test_stripper_uses_span_and_trims_leading_blank(tmp_path: pathlib.Path) -> None:
    """
    Remove a header using a known span and trim a single leading blank.

    Setup:
      * Provide file lines with a TopMark header at indexes 0..2 followed by a
        blank line and then code.
      * Seed `existing_header_range` with (0, 2) as if set by the scanner.
      * Set `HeaderStatus.DETECTED` to simulate scanner output.

    Expectations:
      * `stripper.strip()` populates `updated_file_lines` with only the code.
      * Exactly one leading blank (introduced by removal at top) is trimmed.
      * `StripStatus` becomes READY and `HeaderStatus` reflects presence.

    Args:
      tmp_path: Pytest-provided temporary directory for constructing test files.
    """
    from topmark.pipeline.context import HeaderStatus, ProcessingContext
    from topmark.pipeline.processors.base import HeaderProcessor

    lines = ["# topmark:header:start\n", "# h\n", "# topmark:header:end\n", "\n", "code\n"]
    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=(tmp_path / "x.py"), config=cfg)
    ctx.file_lines = lines
    # Use the base processor; removal relies on span and generic bounds logic.
    ctx.header_processor = HeaderProcessor()
    ctx.existing_header_range = (0, 2)  # as provided by scanner

    # ✅ Simulate scanner result so stripper proceeds
    ctx.status.header = HeaderStatus.DETECTED

    from topmark.pipeline.steps.stripper import strip

    ctx = strip(ctx)
    # After stripping, only the code line should remain; statuses updated accordingly.
    assert ctx.updated_file_lines == ["code\n"]
    assert ctx.status.strip.name == "READY"
    assert ctx.status.header in (HeaderStatus.DETECTED, HeaderStatus.EMPTY)
