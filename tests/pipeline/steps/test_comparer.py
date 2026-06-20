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

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_comparer
from tests.helpers.pipeline import run_reader
from tests.helpers.pipeline import run_resolver
from tests.helpers.pipeline import run_scanner
from tests.helpers.registry import make_file_type
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import RenderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.views import BuilderView
from topmark.pipeline.views import EditView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import PlanEditKind
from topmark.pipeline.views import PlannedEdit
from topmark.pipeline.views import RenderView
from topmark.pipeline.views import UpdatedView
from topmark.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import FileImageView


def test_comparer_precomputed_lines_set_changed(tmp_path: Path) -> None:
    """Mark CHANGED when an updated view differs from the original image."""
    file: Path = tmp_path / "x.py"
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # Provide original image and a precomputed updated image via views

    # Ensure the ComparerStep.may_proceed() gating helper allows processing:
    ctx.views.image = ListFileImageView(lines=["a\n", "b\n"])  # original
    ctx.views.updated = UpdatedView(lines=["a\n"])  # precomputed change
    ctx.file_type = make_file_type(
        local_key="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    ctx = run_comparer(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert ctx.status.generation is GenerationStatus.PENDING


def test_comparer_precomputed_lines_set_unchanged(tmp_path: Path) -> None:
    """Mark UNCHANGED when `updated_file_lines` is identical to `file_lines`."""
    file: Path = tmp_path / "y.py"
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    original: list[str] = ["same\n", "lines\n"]

    # Ensure the ComparerStep.may_proceed() gating helper allows processing:
    ctx.views.image = ListFileImageView(lines=original)
    ctx.views.updated = UpdatedView(lines=list(original))  # identical copy
    ctx.file_type = make_file_type(
        local_key="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    ctx = run_comparer(ctx)

    assert ctx.status.comparison is ComparisonStatus.UNCHANGED
    assert ctx.status.generation is GenerationStatus.PENDING


def test_comparer_uses_single_edit_metadata_without_materializing_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-edit metadata should classify changes without full image equality checks."""
    file: Path = tmp_path / "edit.py"
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx.views.image = ListFileImageView(lines=["old\n", "body\n"])
    ctx.views.updated = UpdatedView(lines=["new\n", "body\n"])
    ctx.views.edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=1,
                new_lines=("new\n",),
            ),
        )
    )
    ctx.file_type = make_file_type(
        local_key="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    def fail_materialize_image_lines(self: ProcessingContext) -> list[str]:
        del self
        raise AssertionError("original image should not be materialized for edit comparison")

    def fail_materialize_updated_lines(self: ProcessingContext) -> list[str]:
        del self
        raise AssertionError("updated image should not be materialized for edit comparison")

    monkeypatch.setattr(type(ctx), "materialize_image_lines", fail_materialize_image_lines)
    monkeypatch.setattr(type(ctx), "materialize_updated_lines", fail_materialize_updated_lines)

    ctx = run_comparer(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert ctx.views.edit is not None
    assert len(ctx.views.edit.edits) == 1


def test_comparer_invalid_single_edit_metadata_falls_back_to_full_image_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid single-edit metadata should not bypass full-image comparison."""
    file: Path = tmp_path / "invalid-edit.py"
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx.views.image = ListFileImageView(lines=["old\n", "body\n"])
    ctx.views.updated = UpdatedView(lines=["new\n", "body\n"])
    ctx.views.edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=3,
                new_lines=("new\n",),
            ),
        )
    )
    ctx.file_type = make_file_type(
        local_key="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    materialized: dict[str, bool] = {"image": False, "updated": False}

    def materialize_image_lines(self: ProcessingContext) -> list[str]:
        materialized["image"] = True
        image_view: FileImageView | None = self.views.image
        assert image_view is not None
        return list(image_view.iter_lines())

    def materialize_updated_lines(self: ProcessingContext) -> list[str]:
        materialized["updated"] = True
        updated_view: UpdatedView | None = self.views.updated
        assert updated_view is not None
        assert updated_view.lines is not None
        return list(updated_view.lines)

    monkeypatch.setattr(type(ctx), "materialize_image_lines", materialize_image_lines)
    monkeypatch.setattr(type(ctx), "materialize_updated_lines", materialize_updated_lines)

    ctx = run_comparer(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert materialized == {"image": True, "updated": True}


def test_comparer_generation_pending_without_updated_view_is_unchanged(tmp_path: Path) -> None:
    """Mark UNCHANGED when no rendered or updated image is available in non-rendering flow."""
    file: Path = tmp_path / "pending.py"
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx.views.render = RenderView(lines=[], block="")
    ctx.status.render = RenderStatus.RENDERED
    ctx.status.generation = GenerationStatus.PENDING
    ctx.file_type = make_file_type(
        local_key="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    ctx = run_comparer(ctx)

    assert ctx.status.comparison is ComparisonStatus.UNCHANGED


@pytest.mark.parametrize(
    "header_status",
    [
        HeaderStatus.MALFORMED_ALL_FIELDS,
        HeaderStatus.MALFORMED_SOME_FIELDS,
    ],
)
def test_comparer_skips_and_halts_for_malformed_headers(
    tmp_path: Path,
    header_status: HeaderStatus,
) -> None:
    """Skip comparison and halt when scanner found malformed header fields."""
    file: Path = tmp_path / "malformed.py"
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx.views.render = RenderView(lines=[], block="")
    ctx.status.render = RenderStatus.RENDERED
    ctx.status.header = header_status
    ctx.file_type = make_file_type(
        local_key="test",
        description="Test File Type",
        extensions=[],
        filenames=[],
        patterns=[],
    )
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED

    ctx = run_comparer(ctx)

    reason: str = f"Skipped: {header_status.value}"
    assert ctx.status.comparison is ComparisonStatus.SKIPPED
    assert ctx.is_halted
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ComparerStep"
    assert ctx.halt_state.reason_code == reason
    assert any(reason in d.message for d in ctx.diagnostics.items)


def test_formatting_only_changes_are_detected(tmp_path: Path) -> None:
    """Comparer flags formatting-only drift as CHANGED.

    We author a Python file with a TopMark header whose fields match the
    expected content but whose on-disk **ordering** differs from what the
    renderer would emit. The comparer should report `ComparisonStatus.CHANGED`.

    NOTE: This test is designed to exercise the comparer's *formatting-fallback*
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

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()

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
