# topmark:header:start
#
#   file         : test_comparer.py
#   file_relpath : tests/pipeline/steps/test_comparer.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# tests/pipeline/steps/test_comparer.py
"""
Unit tests for the `comparer` pipeline step (fast-path behavior).

These tests validate that when a prior step (e.g., `stripper`) precomputes a full
updated file image in `ctx.updated_file_lines`, the comparer:
  * Compares original vs updated lines directly, and
  * Sets `ComparisonStatus` to CHANGED or UNCHANGED accordingly,
without requiring any header generation/rendering.
"""

from __future__ import annotations

import pathlib

from topmark.config import Config
from topmark.pipeline.context import ComparisonStatus, ProcessingContext
from topmark.pipeline.steps.comparer import compare


def test_comparer_precomputed_lines_set_changed(tmp_path: pathlib.Path) -> None:
    """Mark CHANGED when `updated_file_lines` differs from `file_lines`."""
    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=(tmp_path / "x.py"), config=cfg)
    ctx.file_lines = ["a\n", "b\n"]
    ctx.updated_file_lines = ["a\n"]  # precomputed change (e.g., header removal or edit)

    ctx = compare(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED


def test_comparer_precomputed_lines_set_unchanged(tmp_path: pathlib.Path) -> None:
    """Mark UNCHANGED when `updated_file_lines` is identical to `file_lines`."""
    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=(tmp_path / "y.py"), config=cfg)
    ctx.file_lines = ["same\n", "lines\n"]
    ctx.updated_file_lines = ["same\n", "lines\n"]  # no effective change

    ctx = compare(ctx)

    assert ctx.status.comparison is ComparisonStatus.UNCHANGED
