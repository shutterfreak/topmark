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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_planner
from tests.helpers.registry import make_file_type
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.diagnostic.model import DiagnosticLevel
from topmark.filetypes.model import InsertCapability
from topmark.filetypes.model import InsertCheckResult
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import RenderStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.views import EditView
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import PlanEditKind
from topmark.pipeline.views import PlannedEdit
from topmark.pipeline.views import RenderView
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import ViewSlot
from topmark.processors.base import NO_LINE_ANCHOR
from topmark.processors.base import HeaderProcessor
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.filetypes.model import PreInsertContextView
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint


@dataclass(frozen=True, kw_only=True, slots=True)
class TextPreparationCall:
    """Arguments passed to text insertion preparation."""

    original_text: str
    insert_offset: int
    rendered_header_text: str
    newline_style: str


@dataclass(frozen=True, kw_only=True, slots=True)
class LinePreparationCall:
    """Arguments passed to line insertion preparation."""

    original_lines: tuple[str, ...]
    insert_index: int
    rendered_header_lines: tuple[str, ...]
    newline_style: str


class _NoLineAnchorProcessor(HeaderProcessor):
    """Processor stub that refuses line-based insertion."""

    namespace = "test"
    local_key = "no_line_anchor"

    def compute_insertion_anchor(
        self,
        lines: list[str],
    ) -> int:
        """Return no insertion anchor."""
        return NO_LINE_ANCHOR


class _NegativeAnchorProcessor(HeaderProcessor):
    """Processor stub that returns a negative insertion anchor."""

    namespace = "test"
    local_key = "negative_anchor"

    def compute_insertion_anchor(
        self,
        lines: list[str],
    ) -> int:
        """Return a negative anchor so PlannerStep clamps to BOF."""
        return -10


class _FailingTextInsertionProcessor(HeaderProcessor):
    """Processor stub whose text insertion path fails."""

    namespace = "test"
    local_key = "failing_text_insertion"

    def get_header_insertion_char_offset(
        self,
        original_text: str,
    ) -> int:
        """Raise a value error to exercise PlannerStep text-path failure."""
        _: str = original_text
        raise ValueError("cannot compute text insertion point")

    def compute_insertion_anchor(
        self,
        lines: list[str],
    ) -> int:
        """Return a fallback anchor that must not hide text-path errors."""
        _: list[str] = lines
        return 0


class _RecordingTextInsertionProcessor(HeaderProcessor):
    """Deterministic text processor that records every planner handoff."""

    namespace = "test"
    local_key = "recording_text_insertion"

    def __init__(
        self,
        *,
        offset: int,
        prepared_header: str | None = None,
    ) -> None:
        super().__init__()
        self.offset: int = offset
        self.prepared_header: str | None = prepared_header
        self.offset_calls: list[str] = []
        self.preparation_calls: list[TextPreparationCall] = []
        self.line_calls: list[tuple[str, ...]] = []

    def get_header_insertion_char_offset(
        self,
        original_text: str,
    ) -> int:
        """Record the full reader image and return the configured offset."""
        self.offset_calls.append(original_text)
        return self.offset

    def prepare_header_for_insertion_text(
        self,
        *,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
        newline_style: str,
    ) -> str:
        """Record preparation inputs and return the configured header text."""
        self.preparation_calls.append(
            TextPreparationCall(
                original_text=original_text,
                insert_offset=insert_offset,
                rendered_header_text=rendered_header_text,
                newline_style=newline_style,
            )
        )
        if self.prepared_header is not None:
            return self.prepared_header

        return super().prepare_header_for_insertion_text(
            original_text=original_text,
            insert_offset=insert_offset,
            rendered_header_text=rendered_header_text,
            newline_style=newline_style,
        )

    def compute_insertion_anchor(
        self,
        lines: list[str],
    ) -> int:
        """Record an erroneous fallback call and refuse line insertion."""
        self.line_calls.append(tuple(lines))
        return NO_LINE_ANCHOR


class _FailingTextPreparationProcessor(_RecordingTextInsertionProcessor):
    """Text processor whose optional preparation hook rejects its input."""

    local_key = "failing_text_preparation"

    def prepare_header_for_insertion_text(
        self,
        *,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
        newline_style: str,
    ) -> str:
        """Record preparation inputs and raise a supported extension error."""
        self.preparation_calls.append(
            TextPreparationCall(
                original_text=original_text,
                insert_offset=insert_offset,
                rendered_header_text=rendered_header_text,
                newline_style=newline_style,
            )
        )
        raise ValueError("cannot prepare text header")


class _RecordingLineInsertionProcessor(HeaderProcessor):
    """Deterministic line processor that records anchor and preparation calls."""

    namespace = "test"
    local_key = "recording_line_insertion"

    def __init__(
        self,
        *,
        anchor: int,
        prepared_lines: list[str] | None = None,
        fail_preparation: bool = False,
    ) -> None:
        super().__init__()
        self.anchor: int = anchor
        self.prepared_lines: list[str] | None = prepared_lines
        self.fail_preparation: bool = fail_preparation
        self.text_calls: list[str] = []
        self.anchor_calls: list[tuple[str, ...]] = []
        self.preparation_calls: list[LinePreparationCall] = []

    def get_header_insertion_char_offset(
        self,
        original_text: str,
    ) -> None:
        """Record the preferred text probe and request the line path."""
        self.text_calls.append(original_text)
        return None

    def compute_insertion_anchor(
        self,
        lines: list[str],
    ) -> int:
        """Record the unchanged reader lines and return the configured anchor."""
        self.anchor_calls.append(tuple(lines))
        return self.anchor

    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        """Record preparation arguments, then return or reject deterministically."""
        self.preparation_calls.append(
            LinePreparationCall(
                original_lines=tuple(original_lines),
                insert_index=insert_index,
                rendered_header_lines=tuple(rendered_header_lines),
                newline_style=newline_style,
            )
        )
        if self.fail_preparation:
            raise ValueError("cannot prepare line header")
        return self.prepared_lines or rendered_header_lines


class _RaisingChecker:
    """File-type checker double that fails at the extension boundary."""

    def __call__(
        self,
        ctx: PreInsertContextView,
    ) -> InsertCheckResult:
        """Reject the call with a deterministic extension error."""
        _: PreInsertContextView = ctx
        raise RuntimeError("boom")


class _UnexpectedChecker:
    """Checker double used to prove reader advisory state bypasses reevaluation."""

    def __init__(self) -> None:
        self.calls: int = 0

    def __call__(
        self,
        ctx: PreInsertContextView,
    ) -> InsertCheckResult:
        """Record an unexpected authoritative invocation."""
        _: PreInsertContextView = ctx
        self.calls += 1
        return InsertCheckResult(capability=InsertCapability.OK)


def _make_context(
    path: Path,
    *,
    allow_reflow: bool = False,
) -> ProcessingContext:
    """Create a minimal context suitable for planner unit tests."""
    draft: MutableConfig = mutable_config_from_defaults()
    if allow_reflow:
        draft.policy.allow_reflow = True
    cfg: FrozenConfig = draft.freeze()
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


def _only_hint(
    ctx: ProcessingContext,
) -> Hint:
    """Return the context's sole planner hint."""
    assert len(ctx.diagnostic_hints.items) == 1
    return ctx.diagnostic_hints.items[0]


def _assert_hint(
    ctx: ProcessingContext,
    *,
    code: KnownCode | str,
    cluster: Cluster | str,
    message: str,
    terminal: bool,
) -> None:
    """Assert the exact sole planner hint payload."""
    hint: Hint = _only_hint(ctx)
    assert hint.axis is Axis.PLAN
    assert hint.code == (code.value if isinstance(code, KnownCode) else code)
    assert hint.cluster == (cluster.value if isinstance(cluster, Cluster) else cluster)
    assert hint.message == message
    assert hint.terminal is terminal


def test_planner_declares_plan_axis_and_consumed_views() -> None:
    """Planner writes only plan state and declares every view it consumes."""
    from topmark.pipeline.steps.planner import PlannerStep

    step = PlannerStep()

    assert step.primary_axis is Axis.PLAN
    assert step.axes_written == (Axis.PLAN,)
    assert step.consumes_views == frozenset(
        {
            ViewSlot.IMAGE,
            ViewSlot.HEADER,
            ViewSlot.RENDER,
            ViewSlot.UPDATED,
            ViewSlot.EDIT,
        }
    )


def test_planner_skips_unchanged_comparison_and_preserves_original_image(
    tmp_path: Path,
) -> None:
    """UNCHANGED comparison should become a skipped plan with original lines preserved."""
    ctx: ProcessingContext = _make_context(tmp_path / "unchanged.py")
    original_lines: list[str] = ["print('ok')\n"]
    rendered_lines: list[str] = ["# rendered\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=rendered_lines,
    )
    ctx.status.comparison = ComparisonStatus.UNCHANGED

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == original_lines
    assert ctx.views.edit is None
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_SKIP,
        cluster=Cluster.SKIPPED,
        message="no update needed",
        terminal=True,
    )


def test_planner_replaces_existing_header_as_preview_in_dry_run(
    tmp_path: Path,
) -> None:
    """Existing header range plus changed rendered header should preview a replacement."""
    ctx: ProcessingContext = _make_context(tmp_path / "replace.py")
    original_lines: list[str] = ["# old start\n", "# old end\n", "print('body')\n"]
    rendered_lines: list[str] = ["# new start\n", "# new end\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=rendered_lines,
    )
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
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REPLACE
    assert edit.old_start == 0
    assert edit.old_end == 2
    assert edit.new_lines == tuple(rendered_lines)
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_PREVIEW,
        cluster=Cluster.WOULD_CHANGE,
        message="previewed changes",
        terminal=True,
    )


def test_planner_replaces_existing_header_as_changed_when_apply_enabled(
    tmp_path: Path,
) -> None:
    """Apply mode should record REPLACED rather than PREVIEWED."""
    ctx: ProcessingContext = _make_context(tmp_path / "replace_apply.py")
    ctx.run_options = RunOptions(apply_changes=True)
    original_lines: list[str] = ["# old\n", "print('body')\n"]
    rendered_lines: list[str] = ["# new\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=rendered_lines,
    )
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
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_UPDATE,
        cluster=Cluster.CHANGED,
        message="header will be replaced",
        terminal=False,
    )


def test_planner_line_inserts_header_when_no_existing_header(
    tmp_path: Path,
) -> None:
    """Missing header should be inserted through the line-based fallback."""
    ctx: ProcessingContext = _make_context(tmp_path / "insert.py")
    original_lines: list[str] = ["print('body')\n"]
    rendered_lines: list[str] = ["# header\n", "# end\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=rendered_lines,
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == [
        "# header\n",
        "# end\n",
        "print('body')\n",
    ]
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.INSERT
    assert edit.old_start == 0
    assert edit.old_end == 0
    assert edit.new_lines == tuple(rendered_lines)


def test_planner_text_inserts_header_and_records_edit_view(
    tmp_path: Path,
) -> None:
    """Text-based insertion should populate updated content and edit metadata."""
    ctx: ProcessingContext = _make_context(tmp_path / "text_insert.xml")
    original_lines: list[str] = ["<root>\n", "</root>\n"]
    rendered_lines: list[str] = ["<!-- header -->\n"]
    processor = _RecordingTextInsertionProcessor(offset=len(original_lines[0]))
    ctx.header_processor = processor
    _set_image_and_render(ctx, original_lines=original_lines, rendered_lines=rendered_lines)

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == [
        "<root>\n",
        "<!-- header -->\n",
        "</root>\n",
    ]
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.INSERT
    assert edit.old_start == 1
    assert edit.old_end == 1
    assert edit.new_lines == tuple(rendered_lines)
    assert processor.offset_calls == ["<root>\n</root>\n"]
    assert processor.preparation_calls == [
        TextPreparationCall(
            original_text="<root>\n</root>\n",
            insert_offset=7,
            rendered_header_text="<!-- header -->\n",
            newline_style="\n",
        )
    ]
    assert processor.line_calls == []


def test_planner_uses_unprepared_text_when_text_preparation_fails(
    tmp_path: Path,
) -> None:
    """Supported text-preparation errors retain the rendered header and text path."""
    ctx: ProcessingContext = _make_context(tmp_path / "text_prepare_error.xml")
    processor = _FailingTextPreparationProcessor(offset=0)
    ctx.header_processor = processor
    _set_image_and_render(
        ctx,
        original_lines=["<root/>\n"],
        rendered_lines=["<!-- header -->\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["<!-- header -->\n", "<root/>\n"]
    assert processor.preparation_calls == [
        TextPreparationCall(
            original_text="<root/>\n",
            insert_offset=0,
            rendered_header_text="<!-- header -->\n",
            newline_style="\n",
        )
    ]
    assert processor.line_calls == []
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("<!-- header -->\n",),
        ),
    )


def test_planner_normalizes_text_insertion_for_bom_only_logical_empty_input(
    tmp_path: Path,
) -> None:
    """Text insertion trims EOF separators and restores one reader-owned BOM."""
    ctx: ProcessingContext = _make_context(tmp_path / "bom_only.xml")
    ctx.leading_bom = True
    ctx.is_logically_empty = True
    ctx.newline_style = "\r\n"
    processor = _RecordingTextInsertionProcessor(
        offset=0,
        prepared_header="<!-- header -->\r\n\r\n",
    )
    ctx.header_processor = processor
    _set_image_and_render(
        ctx,
        original_lines=[],
        rendered_lines=["<!-- header -->\r\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["\ufeff<!-- header -->\r\n"]
    assert processor.preparation_calls == [
        TextPreparationCall(
            original_text="",
            insert_offset=0,
            rendered_header_text="<!-- header -->\r\n",
            newline_style="\r\n",
        )
    ]
    assert processor.line_calls == []
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("\ufeff<!-- header -->\r\n",),
        ),
    )


def test_planner_falls_back_to_line_insertion_when_text_path_fails(
    tmp_path: Path,
) -> None:
    """Text insertion errors should fall back to line-based insertion."""
    ctx: ProcessingContext = _make_context(tmp_path / "text_insert_error.xml")
    ctx.header_processor = _FailingTextInsertionProcessor()
    _set_image_and_render(
        ctx,
        original_lines=["<root>\n", "</root>\n"],
        rendered_lines=["<!-- header -->\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == [
        "<!-- header -->\n",
        "<root>\n",
        "</root>\n",
    ]
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.INSERT
    assert edit.old_start == 0
    assert edit.old_end == 0
    assert edit.new_lines == ("<!-- header -->\n",)


def test_planner_passes_line_inputs_and_uses_prepared_header(tmp_path: Path) -> None:
    """Line insertion receives reader/renderer facts and composes processor output."""
    ctx: ProcessingContext = _make_context(tmp_path / "line_handoff.py")
    ctx.run_options = RunOptions(apply_changes=True)
    processor = _RecordingLineInsertionProcessor(
        anchor=1,
        prepared_lines=["# prepared\r\n", "\r\n"],
    )
    ctx.header_processor = processor
    ctx.newline_style = "\r\n"
    original_lines: list[str] = ["#!/usr/bin/env python\r\n", "body\r\n"]
    rendered_lines: list[str] = ["# rendered\r\n"]
    _set_image_and_render(
        ctx,
        original_lines=original_lines,
        rendered_lines=rendered_lines,
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.INSERTED
    assert materialize_updated_lines(ctx) == [
        "#!/usr/bin/env python\r\n",
        "# prepared\r\n",
        "\r\n",
        "body\r\n",
    ]
    assert processor.text_calls == ["#!/usr/bin/env python\r\nbody\r\n"]
    assert processor.anchor_calls == [("#!/usr/bin/env python\r\n", "body\r\n")]
    assert processor.preparation_calls == [
        LinePreparationCall(
            original_lines=("#!/usr/bin/env python\r\n", "body\r\n"),
            insert_index=1,
            rendered_header_lines=("# rendered\r\n",),
            newline_style="\r\n",
        )
    ]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=1,
            old_end=1,
            new_lines=("# prepared\r\n", "\r\n"),
        ),
    )
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_INSERT,
        cluster=Cluster.CHANGED,
        message="header will be inserted",
        terminal=False,
    )


def test_planner_uses_rendered_lines_when_line_preparation_fails(
    tmp_path: Path,
) -> None:
    """Supported line-preparation errors fall back to renderer-owned lines."""
    ctx: ProcessingContext = _make_context(tmp_path / "line_prepare_error.py")
    processor = _RecordingLineInsertionProcessor(
        anchor=0,
        fail_preparation=True,
    )
    ctx.header_processor = processor
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# rendered\n"],
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["# rendered\n", "body\n"]
    assert processor.preparation_calls == [
        LinePreparationCall(
            original_lines=("body\n",),
            insert_index=0,
            rendered_header_lines=("# rendered\n",),
            newline_style="\n",
        )
    ]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("# rendered\n",),
        ),
    )


def test_planner_clamps_negative_line_anchor_to_start(
    tmp_path: Path,
) -> None:
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
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    reason = f"No line-based insertion anchor for file: {tmp_path / 'no_anchor.py'}"
    assert ctx.halt_state.reason_code == reason
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == reason
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_FAILED,
        cluster=Cluster.SKIPPED,
        message="failed to compute update",
        terminal=True,
    )


def test_planner_strip_fast_path_accepts_empty_updated_image(
    tmp_path: Path,
) -> None:
    """An empty updated image is valid when stripping removes the whole file body."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip_empty.py")
    ctx.status.strip = StripStatus.READY
    ctx.views.image = ListFileImageView(["# header\n"])
    ctx.views.updated = UpdatedView(lines=[])

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == []
    assert ctx.views.edit is None
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_PREVIEW,
        cluster=Cluster.WOULD_CHANGE,
        message="previewed changes",
        terminal=True,
    )


def test_planner_strip_apply_preserves_bom_and_stripper_edit(
    tmp_path: Path,
) -> None:
    """Strip planning keeps the stripper image and edit without duplicating its BOM."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip_bom.py")
    ctx.run_options = RunOptions(apply_changes=True)
    ctx.status.strip = StripStatus.READY
    ctx.leading_bom = True
    ctx.views.image = ListFileImageView(["# header\n", "body\n"])
    ctx.views.updated = UpdatedView(lines=["\ufeffbody\n"])
    stripper_edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REMOVE,
                old_start=0,
                old_end=1,
                new_lines=(),
            ),
        )
    )
    ctx.views.edit = stripper_edit

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.REMOVED
    assert materialize_updated_lines(ctx) == ["\ufeffbody\n"]
    assert ctx.views.edit is stripper_edit
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_REMOVE,
        cluster=Cluster.CHANGED,
        message="header will be removed",
        terminal=False,
    )


def test_planner_replacement_reattaches_reader_owned_bom_once(
    tmp_path: Path,
) -> None:
    """Replacement restores one BOM to the BOM-free reader image and edit."""
    ctx: ProcessingContext = _make_context(tmp_path / "replace_bom.py")
    ctx.run_options = RunOptions(apply_changes=True)
    ctx.leading_bom = True
    original_lines = ["# old\n", "body\n"]
    _set_image_and_render(ctx, original_lines=original_lines, rendered_lines=["# new\n"])
    ctx.status.header = HeaderStatus.DETECTED
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# old\n"],
        block="# old\n",
        mapping={},
    )

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.REPLACED
    assert materialize_updated_lines(ctx) == ["\ufeff# new\n", "body\n"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.REPLACE,
            old_start=0,
            old_end=1,
            new_lines=("\ufeff# new\n",),
        ),
    )


def test_planner_canonicalizes_logically_empty_line_insertion(
    tmp_path: Path,
) -> None:
    """A newline placeholder becomes one newline-terminated header image."""
    ctx: ProcessingContext = _make_context(tmp_path / "logical_empty.py")
    ctx.is_logically_empty = True
    processor = _RecordingLineInsertionProcessor(anchor=0)
    ctx.header_processor = processor
    _set_image_and_render(ctx, original_lines=["\n"], rendered_lines=["# header"])

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["# header\n"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=1,
            new_lines=("# header\n",),
        ),
    )


def test_planner_drops_processor_separator_blanks_after_header_at_eof(
    tmp_path: Path,
) -> None:
    """Line preparation may add body separators that are removed when no body follows."""
    ctx: ProcessingContext = _make_context(tmp_path / "header_at_eof.py")
    processor = _RecordingLineInsertionProcessor(
        anchor=0,
        prepared_lines=["# header\n", "\n", "\n"],
    )
    ctx.header_processor = processor
    _set_image_and_render(ctx, original_lines=[], rendered_lines=["# header\n"])

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["# header\n"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("# header\n",),
        ),
    )


def test_planner_strip_fast_path_fails_without_updated_view(
    tmp_path: Path,
) -> None:
    """Strip fast-path should fail if StripperStep did not provide updated lines."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip_missing_view.py")
    ctx.status.strip = StripStatus.READY
    ctx.views.image = ListFileImageView(["# header\n"])
    ctx.views.updated = None

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "No updated file lines available for stripping."
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_FAILED,
        cluster=Cluster.SKIPPED,
        message="failed to compute update",
        terminal=True,
    )


def test_planner_skips_malformed_header_without_modifying_image(
    tmp_path: Path,
) -> None:
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
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert (
        ctx.halt_state.reason_code
        == "Existing header has malformed fields; TopMark will not update it."
    )
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.WARNING
    assert ctx.diagnostics.items[0].message == ctx.halt_state.reason_code


def test_planner_skips_when_content_status_blocks_update(
    tmp_path: Path,
) -> None:
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
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Could not update file (status: unsupported)."
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.INFO
    assert ctx.diagnostics.items[0].message == ctx.halt_state.reason_code


def test_planner_fails_without_render_view(
    tmp_path: Path,
) -> None:
    """Changed content cannot be planned when the renderer produced no header."""
    ctx: ProcessingContext = _make_context(tmp_path / "missing_render.py")
    ctx.views.image = ListFileImageView(["body\n"])
    ctx.views.render = None

    ctx = run_planner(ctx)

    assert ctx.status.plan is PlanStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Cannot update header: no rendered header available"
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == ctx.halt_state.reason_code


def test_planner_fails_without_header_processor(
    tmp_path: Path,
) -> None:
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
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Cannot update header: no header processor assigned"
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == ctx.halt_state.reason_code


def test_planner_identical_replacement_is_skipped(
    tmp_path: Path,
) -> None:
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
    assert ctx.views.edit is None
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None


def test_planner_enforces_authoritative_pre_insert_checker_skip(
    tmp_path: Path,
) -> None:
    """A file-type pre-insert checker can authoritatively skip insertion."""
    calls: list[PreInsertContextView] = []

    def _skip_checker(ctx: PreInsertContextView) -> InsertCheckResult:
        calls.append(ctx)
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

    assert len(calls) == 1
    view: PreInsertContextView = calls[0]
    assert tuple(view.lines) == ("body\n",)
    assert view.newline_style == "\n"
    assert view.header_processor is ctx.header_processor
    assert view.file_type is ctx.file_type
    assert ctx.pre_insert_capability is InsertCapability.SKIP_POLICY
    assert ctx.pre_insert_reason == "test policy refused insertion"
    assert ctx.pre_insert_origin == "tests.planner"
    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == ["body\n"]
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "test policy refused insertion (origin: tests.planner)"
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.WARNING
    assert ctx.diagnostics.items[0].message == ctx.halt_state.reason_code
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_SKIP,
        cluster=Cluster.SKIPPED,
        message="test policy refused insertion (origin: tests.planner)",
        terminal=True,
    )


def test_planner_defaults_empty_authoritative_checker_result_to_ok(
    tmp_path: Path,
) -> None:
    """An empty checker result means OK and persists the planner origin default."""
    calls: list[PreInsertContextView] = []

    def _empty_checker(ctx: PreInsertContextView) -> InsertCheckResult:
        calls.append(ctx)
        return InsertCheckResult()

    ctx: ProcessingContext = _make_context(tmp_path / "checker_defaults.py")
    ctx.file_type = make_file_type(
        local_key="checker_defaults",
        extensions=[".py"],
        pre_insert_checker=_empty_checker,
    )
    processor = _RecordingLineInsertionProcessor(anchor=0)
    ctx.header_processor = processor
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert len(calls) == 1
    assert ctx.pre_insert_capability is InsertCapability.OK
    assert ctx.pre_insert_reason is None
    assert ctx.pre_insert_origin == "topmark.pipeline.steps.planner"
    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["# header\n", "body\n"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("# header\n",),
        ),
    )
    assert ctx.halt_state is None


def test_planner_normalizes_pre_insert_checker_exception(
    tmp_path: Path,
) -> None:
    """Checker exceptions become deterministic advisory state and a terminal skip."""
    ctx: ProcessingContext = _make_context(tmp_path / "checker_error.py")
    ctx.file_type = make_file_type(
        local_key="checker_error",
        extensions=[".py"],
        pre_insert_checker=_RaisingChecker(),
    )
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    reason = "checker error: _RaisingChecker, boom (origin: topmark.pipeline.steps.planner)"
    assert ctx.pre_insert_capability is InsertCapability.SKIP_OTHER
    assert ctx.pre_insert_reason == "checker error: _RaisingChecker, boom"
    assert ctx.pre_insert_origin == "topmark.pipeline.steps.planner"
    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == ["body\n"]
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == reason
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.WARNING
    assert ctx.diagnostics.items[0].message == reason
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_SKIP,
        cluster=Cluster.SKIPPED,
        message=reason,
        terminal=True,
    )


def test_planner_enforces_reader_idempotence_advisory_without_rechecking(
    tmp_path: Path,
) -> None:
    """A reader advisory blocks planning under the default no-reflow policy."""
    checker = _UnexpectedChecker()
    ctx: ProcessingContext = _make_context(tmp_path / "reader_advisory.py")
    ctx.file_type = make_file_type(
        local_key="reader_advisory",
        extensions=[".py"],
        pre_insert_checker=checker,
    )
    ctx.pre_insert_capability = InsertCapability.SKIP_IDEMPOTENCE_RISK
    ctx.pre_insert_reason = "reader detected reflow risk"
    ctx.pre_insert_origin = "topmark.pipeline.steps.reader"
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    reason = "reader detected reflow risk (origin: topmark.pipeline.steps.reader)"
    assert checker.calls == 0
    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == ["body\n"]
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == reason
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.WARNING
    assert ctx.diagnostics.items[0].message == reason
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_SKIP,
        cluster=Cluster.SKIPPED,
        message=reason,
        terminal=True,
    )


def test_planner_allows_reader_idempotence_advisory_when_reflow_is_enabled(
    tmp_path: Path,
) -> None:
    """Effective reflow policy permits planning past an idempotence advisory."""
    checker = _UnexpectedChecker()
    ctx: ProcessingContext = _make_context(
        tmp_path / "reader_advisory_reflow.py",
        allow_reflow=True,
    )
    ctx.file_type = make_file_type(
        local_key="reader_advisory_reflow",
        extensions=[".py"],
        pre_insert_checker=checker,
    )
    ctx.pre_insert_capability = InsertCapability.SKIP_IDEMPOTENCE_RISK
    ctx.pre_insert_reason = "reader detected permitted reflow risk"
    ctx.pre_insert_origin = "topmark.pipeline.steps.reader"
    processor = _RecordingLineInsertionProcessor(anchor=0)
    ctx.header_processor = processor
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    assert checker.calls == 0
    assert ctx.pre_insert_capability is InsertCapability.SKIP_IDEMPOTENCE_RISK
    assert ctx.status.plan is PlanStatus.PREVIEWED
    assert materialize_updated_lines(ctx) == ["# header\n", "body\n"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.views.edit.edits == (
        PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("# header\n",),
        ),
    )
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None


def test_planner_enforces_other_reader_advisory_without_rechecking(
    tmp_path: Path,
) -> None:
    """A representative non-OK reader advisory remains authoritative in planning."""
    checker = _UnexpectedChecker()
    ctx: ProcessingContext = _make_context(tmp_path / "reader_policy.py")
    ctx.file_type = make_file_type(
        local_key="reader_policy",
        extensions=[".py"],
        pre_insert_checker=checker,
    )
    ctx.pre_insert_capability = InsertCapability.SKIP_POLICY
    ctx.pre_insert_reason = "reader policy refused insertion"
    ctx.pre_insert_origin = "topmark.pipeline.steps.reader"
    _set_image_and_render(
        ctx,
        original_lines=["body\n"],
        rendered_lines=["# header\n"],
    )

    ctx = run_planner(ctx)

    reason = "reader policy refused insertion (origin: topmark.pipeline.steps.reader)"
    assert checker.calls == 0
    assert ctx.status.plan is PlanStatus.SKIPPED
    assert materialize_updated_lines(ctx) == ["body\n"]
    assert ctx.views.edit is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == reason
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.WARNING
    assert ctx.diagnostics.items[0].message == reason
    _assert_hint(
        ctx,
        code=KnownCode.PLAN_SKIP,
        cluster=Cluster.SKIPPED,
        message=reason,
        terminal=True,
    )
