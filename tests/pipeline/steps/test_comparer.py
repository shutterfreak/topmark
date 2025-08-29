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

from pathlib import Path

from topmark.config import Config
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.context import (
    ComparisonStatus,
    FileStatus,
    GenerationStatus,
    ProcessingContext,
)
from topmark.pipeline.steps import comparer, reader, resolver, scanner


def test_comparer_precomputed_lines_set_changed(tmp_path: Path) -> None:
    """Mark CHANGED when `updated_file_lines` differs from `file_lines`."""
    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=(tmp_path / "x.py"), config=cfg)
    ctx.file_lines = ["a\n", "b\n"]
    ctx.updated_file_lines = ["a\n"]  # precomputed change (e.g., header removal or edit)

    ctx = comparer.compare(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED


def test_comparer_precomputed_lines_set_unchanged(tmp_path: Path) -> None:
    """Mark UNCHANGED when `updated_file_lines` is identical to `file_lines`."""
    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=(tmp_path / "y.py"), config=cfg)
    ctx.file_lines = ["same\n", "lines\n"]
    ctx.updated_file_lines = ["same\n", "lines\n"]  # no effective change

    ctx = comparer.compare(ctx)

    assert ctx.status.comparison is ComparisonStatus.UNCHANGED


def test_formatting_only_changes_are_detected(tmp_path: Path) -> None:
    """Comparer flags formatting-only drift as CHANGED.

    We author a Python file with a TopMark header whose fields match the
    expected content but whose on-disk **ordering** differs from what the
    renderer would emit. The comparer should report `ComparisonStatus.CHANGED`.

    NOTE: This test is designed to exercise the comparer’s *formatting-fallback*
    branch. We deliberately avoid calling builder.build() or renderer.render()
    here, because those steps would generate `expected_header_dict` values from
    config (e.g. `file`, `file_relpath`) that differ from the hand-authored
    header in this test. That would cause a dict mismatch and trigger the
    content-difference path, never reaching the formatting-only branch.

    Instead, we synthesize `expected_header_lines` directly from the processor
    but keep `expected_header_dict` equal to `existing_header_dict`. This makes
    the dicts equal while the rendered block text differs, so the comparer
    correctly flags the change as `CHANGED` for formatting reasons only.
    """
    f = tmp_path / "formatting_only.py"
    # Intentionally put fields in a non-canonical order (license before project)
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "# license: MIT\n"
        "# project: TopMark\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('ok')\n",
        encoding="utf-8",
    )

    cfg = Config.from_defaults()

    # Bootstrap a context and run reader+scanner to populate existing header
    ctx = ProcessingContext.bootstrap(path=f, config=cfg)

    # Attach a processor (registry is set up by tests/pipeline/conftest.py)
    ctx = resolver.resolve(ctx)
    assert ctx.header_processor is not None

    ctx = reader.read(ctx)
    # Ensure the file was read
    assert ctx.status.file in (FileStatus.RESOLVED, FileStatus.EMPTY_FILE)

    ctx = scanner.scan(ctx)
    # Scanner should have detected a header
    assert ctx.existing_header_dict is not None
    assert ctx.existing_header_block is not None

    # Synthesize the expected render using the processor to create canonical formatting.
    # The renderer will place fields in config-defined order and add alignment/blank lines,
    # which differs from our on-disk order. Dicts will match; blocks will differ.
    assert ctx.header_processor is not None, "Header processor must be set by resolver"
    expected_lines = ctx.header_processor.render_header_lines(
        header_values=ctx.existing_header_dict,
        config=cfg,
        newline_style=ctx.newline_style,
    )

    ctx.expected_header_lines = expected_lines
    ctx.expected_header_dict = dict(ctx.existing_header_dict)
    ctx.status.generation = GenerationStatus.GENERATED

    # Now compare. Dicts are equal, but blocks differ → CHANGED due to formatting fallback.
    ctx = comparer.compare(ctx)

    assert ctx.expected_header_dict == ctx.existing_header_dict, "Field content must match"
    assert "".join(ctx.expected_header_lines or []) != (ctx.existing_header_block or ""), (
        "Rendered block should differ from existing block to exercise formatting fallback",
    )
    assert ctx.status.comparison is ComparisonStatus.CHANGED, (
        "Comparer must flag formatting-only difference as CHANGED"
    )
