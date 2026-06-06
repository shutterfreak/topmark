# topmark:header:start
#
#   project      : TopMark
#   file         : test_planner.py
#   file_relpath : tests/pipeline/steps/test_planner.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the `planner` pipeline step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_planner
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import RenderStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import RenderView
from topmark.pipeline.views import UpdatedView
from topmark.processors.base import NO_LINE_ANCHOR
from topmark.processors.base import HeaderProcessor
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.filetypes.model import PreInsertContextView
    from topmark.pipeline.context.model import ProcessingContext


class _NoLineAnchorProcessor(HeaderProcessor):
    """Processor stub that refuses line-based insertion."""

    namespace = "test"
    local_key = "no_line_anchor"

    def compute_insertion_anchor(self, lines: list[str]) -> int:
        """Return no insertion anchor."""
        return NO_LINE_ANCHOR


class _NegativeAnchorProcessor(HeaderProcessor):
    """Processor stub that returns a negative insertion anchor."""

    namespace = "test"
    local_key = "negative_anchor"

    def compute_insertion_anchor(self, lines: list[str]) -> int:
        """Return a negative anchor so PlannerStep clamps to BOF."""
        return -10


def _make_context(path: Path) -> ProcessingContext:
    """Create a minimal context suitable for planner unit tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.render = RenderStatus.RENDERED
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.header_processor = HeaderProcessor()
    ctx.newline_style = "\n"
    return ctx


def _set_image_and_render(
    ctx: ProcessingContext,
    *,
    original_lines: list[str],
    rendered_lines: list[str],
) -> None:
    """Install original image and rendered header views on a context."""
    ctx.views.image = ListFileImageView(original_lines)
    ctx.views.render = RenderView(
        lines=rendered_lines,
        block="".join(rendered_lines),
    )


def test_planner_skips_unchanged_comparison_and_preserves_original_image(
    tmp_path: Path,
) -> None:
    """UNCHANGED comparison should become a skipped plan with original lines preserved."""
    ctx: ProcessingContext = _make_context(tmp_path / "unchanged.py")
    original_lines: list[str] = ["print('ok')\n"]
    rendered_lines: list[str] = ["# rendered\n"]
    _set_image_and_render(ctx, original_lines=original_lines, rendered_lines=rendered_lines)
    ctx.status.comparison = ComparisonStatus.UNCHANGED

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == original_lines
    assert ctx.halt_state is None


def test_planner_replaces_existing_header_as_preview_in_dry_run(tmp_path: Path) -> None:
    """Existing header range plus changed rendered header should preview a replacement."""
    ctx: ProcessingContext = _make_context(tmp_path / "replace.py")
    original_lines: list[str] = ["# old start\n", "# old end\n", "print('body')\n"]
    rendered_lines: list[str] = ["# new start\n", "# new end\n"]
    _set_image_and_render(ctx, original_lines=original_lines, rendered_lines=rendered_lines)
    ctx.status.header = HeaderStatus.DETECTED
    ctx.views.header = HeaderView(
        range=(0, 1),
        lines=original_lines[:2],
        block="".join(original_lines[:2]),
        mapping={},
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == [
        "# new start\n",
        "# new end\n",
        "print('body')\n",
    ]


def test_planner_replaces_existing_header_as_changed_when_apply_enabled(
    tmp_path: Path,
) -> None:
    """Apply mode should record REPLACED rather than PREVIEWED."""
    ctx: ProcessingContext = _make_context(tmp_path / "replace_apply.py")
    ctx.run_options = RunOptions(apply_changes=True)
    original_lines: list[str] = ["# old\n", "print('body')\n"]
    rendered_lines: list[str] = ["# new\n"]
    _set_image_and_render(ctx, original_lines=original_lines, rendered_lines=rendered_lines)
    ctx.status.header = HeaderStatus.DETECTED
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# old\n"],
        block="# old\n",
        mapping={},
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.REPLACED
    assert materialize_updated_lines(ctx) == ["# new\n", "print('body')\n"]


def test_planner_line_inserts_header_when_no_existing_header(tmp_path: Path) -> None:
    """Missing header should be inserted through the line-based fallback."""
    ctx: ProcessingContext = _make_context(tmp_path / "insert.py")
    original_lines: list[str] = ["print('body')\n"]
    rendered_lines: list[str] = ["# header\n", "# end\n"]
    _set_image_and_render(ctx, original_lines=original_lines, rendered_lines=rendered_lines)

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == [
        "# header\n",
        "# end\n",
        "print('body')\n",
    ]


def test_planner_clamps_negative_line_anchor_to_start(tmp_path: Path) -> None:
    """A negative processor-provided anchor should be clamped to BOF."""
    ctx: ProcessingContext = _make_context(tmp_path / "negative_anchor.py")
    ctx.header_processor = _NegativeAnchorProcessor()
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["# header\n", "body\n"]


def test_planner_fails_when_no_line_anchor_is_available(tmp_path: Path) -> None:
    """Planner should fail cleanly when text and line insertion are unavailable."""
    ctx: ProcessingContext = _make_context(tmp_path / "no_anchor.py")
    ctx.header_processor = _NoLineAnchorProcessor()
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert "No line-based insertion anchor" in ctx.halt_state.reason_code


def test_planner_strip_fast_path_accepts_empty_updated_image(tmp_path: Path) -> None:
    """An empty updated image is valid when stripping removes the whole file body."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip_empty.py")
    ctx.status.strip = StripStatus.READY
    ctx.views.image = ListFileImageView(["# header\n"])
    ctx.views.updated = UpdatedView(lines=[])

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == []
    assert ctx.halt_state is None


def test_planner_strip_fast_path_fails_without_updated_view(tmp_path: Path) -> None:
    """Strip fast-path should fail if StripperStep did not provide updated lines."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip_missing_view.py")
    ctx.status.strip = StripStatus.READY
    ctx.views.image = ListFileImageView(["# header\n"])
    ctx.views.updated = None

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.FAILED
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "No updated file lines available for stripping."


def test_planner_skips_malformed_header_without_modifying_image(tmp_path: Path) -> None:
    """Malformed header fields remain frozen behavior: planner skips and halts."""
    ctx: ProcessingContext = _make_context(tmp_path / "malformed.py")
    original_lines: list[str] = ["# malformed\n", "body\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=["# replacement\n"],
    )
    ctx.status.header = HeaderStatus.MALFORMED_SOME_FIELDS

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == original_lines
    assert ctx.halt_state is not None
    assert (
        ctx.halt_state.reason_code
        == "Existing header has malformed fields; TopMark will not update it."
    )


def test_planner_skips_when_content_status_blocks_update(tmp_path: Path) -> None:
    """Non-OK content should block planner mutation unless empty-insert policy permits it."""
    ctx: ProcessingContext = _make_context(tmp_path / "blocked.py")
    ctx.status.content = ContentStatus.UNSUPPORTED
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.SKIPPED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Could not update file (status: unsupported)."


def test_planner_fails_without_render_view(tmp_path: Path) -> None:
    """Changed content cannot be planned when the renderer produced no header."""
    ctx: ProcessingContext = _make_context(tmp_path / "missing_render.py")
    ctx.views.image = ListFileImageView(["body\n"])
    ctx.views.render = None

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Cannot update header: no rendered header available"


def test_planner_fails_without_header_processor(tmp_path: Path) -> None:
    """Rendered headers still require an assigned processor for insertion policy."""
    ctx: ProcessingContext = _make_context(tmp_path / "missing_processor.py")
    ctx.header_processor = None
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Cannot update header: no header processor assigned"


def test_planner_identical_replacement_is_skipped(tmp_path: Path) -> None:
    """Replacing a detected header with identical rendered lines is a no-op."""
    ctx: ProcessingContext = _make_context(tmp_path / "identical_replace.py")
    original_lines: list[str] = ["# header\n", "body\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=["# header\n"],
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# header\n"],
        block="# header\n",
        mapping={},
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == original_lines
    assert ctx.halt_state is None


def test_planner_enforces_authoritative_pre_insert_checker_skip(tmp_path: Path) -> None:
    """A file-type pre-insert checker can authoritatively skip insertion."""
    from tests.helpers.registry import make_file_type
    from topmark.filetypes.model import InsertCapability
    from topmark.filetypes.model import InsertCheckResult

    def _skip_checker(ctx: PreInsertContextView) -> InsertCheckResult:
        _: PreInsertContextView = ctx
        return InsertCheckResult(
            capability=InsertCapability.SKIP_POLICY,
            reason="test policy refused insertion",
            origin="tests.planner",
        )

    ctx: ProcessingContext = _make_context(tmp_path / "checker_skip.py")
    ctx.file_type = make_file_type(
        local_key="checker_skip",
        extensions=[".py"],
        pre_insert_checker=_skip_checker,
    )
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == ["body\n"]
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "test policy refused insertion (origin: tests.planner)"
