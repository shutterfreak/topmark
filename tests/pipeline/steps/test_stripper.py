# topmark:header:start
#
#   project      : TopMark
#   file         : test_stripper.py
#   file_relpath : tests/pipeline/steps/test_stripper.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the `stripper` pipeline step.

These tests validate that the step removes the TopMark header using the
scanner-provided header span and that it trims exactly one leading blank
line when the header starts at the top of the file. The tests bootstrap a
minimal `ProcessingContext` without running the full pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.pipeline.conftest import materialize_updated_lines, run_stripper
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.status import ContentStatus, HeaderStatus, ResolveStatus
from topmark.pipeline.views import HeaderView, ListFileImageView

if TYPE_CHECKING:
    from pathlib import Path


def test_stripper_uses_span_and_trims_leading_blank(tmp_path: Path) -> None:
    """When span is provided, stripper should remove exactly that region and trim."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "\n",
        "code\n",
    ]
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=(tmp_path / "x.py"), config=cfg)
    ctx.views.image = ListFileImageView(lines)

    # Use the base processor; removal relies on span and generic bounds logic.
    ctx.header_processor = HeaderProcessor()

    ctx.views.header = HeaderView(
        range=(0, 2),  # as provided by scanner
        lines=None,
        block=None,
        mapping=None,
    )

    # Simulate resolver result so stripper proceeds
    ctx.status.resolve = ResolveStatus.RESOLVED

    # Simulate reader result so stripper proceeds
    ctx.status.content = ContentStatus.OK

    # Simulate scanner result so stripper proceeds
    ctx.status.header = HeaderStatus.DETECTED

    ctx = run_stripper(ctx)
    updated_lines: list[str] = materialize_updated_lines(ctx)
    # After stripping, only the code line should remain; statuses updated accordingly.
    assert updated_lines == ["code\n"]
    assert ctx.status.strip.name == "READY"
    assert ctx.status.header is HeaderStatus.DETECTED
