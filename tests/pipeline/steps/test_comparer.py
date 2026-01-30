# topmark:header:start
#
#   project      : TopMark
#   file         : test_comparer.py
#   file_relpath : tests/pipeline/steps/test_comparer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the `comparer` pipeline step (fast-path behavior).

These tests validate that when a prior step (e.g., `stripper`) precomputes a full
updated file image in `ctx.updated_file_lines`, the comparer:
  * Compares original vs updated lines directly, and
  * Sets `ComparisonStatus` to CHANGED or UNCHANGED accordingly,
without requiring any header generation/rendering.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.pipeline.conftest import (
    make_pipeline_context,
    run_comparer,
    run_reader,
    run_resolver,
    run_scanner,
)
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.filetypes.base import FileType
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.status import (
    ComparisonStatus,
    GenerationStatus,
    RenderStatus,
    ResolveStatus,
)
from topmark.pipeline.views import BuilderView, ListFileImageView, RenderView, UpdatedView

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext


def test_comparer_precomputed_lines_set_changed(tmp_path: Path) -> None:
    """Mark CHANGED when an updated view differs from the original image."""
    file: Path = tmp_path / "x.py"
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # Provide original image and a precomputed updated image via views

    # Ensure the ComparerStep.may_proceed() gating helper allows processing:
    ctx.views.image = ListFileImageView(lines=["a\n", "b\n"])  # original
    ctx.views.updated = UpdatedView(lines=["a\n"])  # precomputed change
    ctx.file_type = FileType(
        name="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    ctx = run_comparer(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED


def test_comparer_precomputed_lines_set_unchanged(tmp_path: Path) -> None:
    """Mark UNCHANGED when `updated_file_lines` is identical to `file_lines`."""
    file: Path = tmp_path / "y.py"
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    original: list[str] = ["same\n", "lines\n"]

    # Ensure the ComparerStep.may_proceed() gating helper allows processing:
    ctx.views.image = ListFileImageView(lines=original)
    ctx.views.updated = UpdatedView(lines=list(original))  # identical copy
    ctx.file_type = FileType(
        name="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    ctx = run_comparer(ctx)

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
    file: Path = tmp_path / "formatting_only.py"
    # Intentionally put fields in a non-canonical order (license before project)
    file.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "# license: MIT\n"
        "# project: TopMark\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('ok')\n",
        encoding="utf-8",
    )

    cfg: Config = MutableConfig.from_defaults().freeze()

    # Bootstrap a context and run reader+scanner to populate existing header
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # Attach a processor (registry is set up by tests/pipeline/conftest.py)
    ctx = run_resolver(ctx)
    assert ctx.header_processor is not None

    ctx = run_reader(ctx)
    assert ctx.views.image is not None
    # Ensure the file was read
    assert ctx.status.resolve == ResolveStatus.RESOLVED

    ctx = run_scanner(ctx)
    # Scanner should have detected a header
    assert ctx.views.header is not None
    assert ctx.views.header.mapping is not None
    assert ctx.views.header.block is not None

    # Synthesize the expected render using the processor to create canonical formatting.
    # The renderer will place fields in config-defined order and add alignment/blank lines,
    # which differs from our on-disk order. Dicts will match; blocks will differ.
    assert ctx.header_processor is not None, "Header processor must be set by resolver"
    expected_lines: list[str] = ctx.header_processor.render_header_lines(
        header_values=ctx.views.header.mapping,
        config=cfg,
        newline_style=ctx.newline_style,
    )

    ctx.views.render = RenderView(
        lines=expected_lines,
        block="".join(expected_lines),
    )
    ctx.status.render = RenderStatus.RENDERED
    ctx.views.build = BuilderView(builtins=None, selected=ctx.views.header.mapping)
    ctx.status.generation = GenerationStatus.GENERATED

    # Now compare. Dicts are equal, but blocks differ → CHANGED due to formatting fallback.
    ctx = run_comparer(ctx)

    assert (
        ctx.views.header
        and ctx.views.build
        and ctx.views.build.selected == ctx.views.header.mapping
    ), "Field content must match"
    assert ctx.views.render and ctx.views.render.block != ctx.views.header.block, (
        "Rendered block should differ from existing block to exercise formatting fallback",
    )
    assert ctx.status.comparison is ComparisonStatus.CHANGED, (
        "Comparer must flag formatting-only difference as CHANGED"
    )
