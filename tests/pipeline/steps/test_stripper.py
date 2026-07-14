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

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_stripper
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.steps.stripper import StripperStep
from topmark.pipeline.views import EditView
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import PlanEditKind
from topmark.pipeline.views import ViewSlot
from topmark.processors.base import HeaderProcessor
from topmark.processors.types import StripDiagKind
from topmark.processors.types import StripDiagnostic
from topmark.processors.types import StripHeaderResult
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.views import PlannedEdit


# --- Helper classes and context factory for stripper tests ---


@dataclass(frozen=True, kw_only=True, slots=True)
class StripCall:
    """Arguments passed across the stripper-to-processor boundary."""

    lines: tuple[str, ...]
    span: tuple[int, int] | None
    newline_style: str
    ends_with_newline: bool | None


class _RecordingStripProcessor(HeaderProcessor):
    """Deterministic processor double that records stripper-owned arguments."""

    namespace = "test"
    local_key = "recording_strip"

    def __init__(self, result: StripHeaderResult) -> None:
        super().__init__()
        self.result: StripHeaderResult = result
        self.calls: list[StripCall] = []

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Record the orchestration arguments and return the configured result."""
        self.calls.append(
            StripCall(
                lines=tuple(lines),
                span=span,
                newline_style=newline_style,
                ends_with_newline=ends_with_newline,
            )
        )
        return self.result


class _NotFoundStripProcessor(HeaderProcessor):
    """Processor stub that reports no removable header."""

    namespace = "test"
    local_key = "not_found_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Return a NOT_FOUND strip diagnostic without changing lines."""
        return StripHeaderResult(
            lines=lines,
            removed_span=None,
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.NOT_FOUND,
                reason="stub not found",
            ),
        )


class _ErrorStripProcessor(HeaderProcessor):
    """Processor stub that reports a strip analysis error."""

    namespace = "test"
    local_key = "error_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Return an ERROR strip diagnostic without changing lines."""
        return StripHeaderResult(
            lines=lines,
            removed_span=None,
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.ERROR,
                reason="stub strip error",
            ),
        )


def _make_strip_context(path: Path, lines: list[str]) -> ProcessingContext:
    """Create a minimal context suitable for stripper unit tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.views.image = ListFileImageView(lines)
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.DETECTED
    ctx.newline_style = "\n"
    ctx.ends_with_newline = bool(lines and lines[-1].endswith("\n"))
    return ctx


def _only_hint(ctx: ProcessingContext) -> Hint:
    """Return the context's sole hint."""
    assert len(ctx.diagnostic_hints.items) == 1
    return ctx.diagnostic_hints.items[0]


def _assert_hint(
    ctx: ProcessingContext,
    *,
    code: KnownCode,
    cluster: Cluster,
    message: str,
    terminal: bool,
) -> None:
    """Assert the exact sole strip hint payload."""
    hint: Hint = _only_hint(ctx)
    assert hint.axis is Axis.STRIP
    assert hint.code == code.value
    assert hint.cluster == cluster.value
    assert hint.message == message
    assert hint.terminal is terminal


def test_stripper_declares_strip_axis_and_consumed_views() -> None:
    """Stripper writes only strip state and declares every view it reads."""
    step = StripperStep()

    assert step.primary_axis is Axis.STRIP
    assert step.axes_written == (Axis.STRIP,)
    assert step.consumes_views == frozenset({ViewSlot.IMAGE, ViewSlot.HEADER, ViewSlot.EDIT})


def test_stripper_passes_reader_and_scanner_state_and_prepares_removal(tmp_path: Path) -> None:
    """Reader and scanner facts cross the processor boundary unchanged."""
    file: Path = tmp_path / "x.py"
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "\n",
        "code\n",
    ]

    ctx: ProcessingContext = _make_strip_context(file, lines)
    processor = _RecordingStripProcessor(
        StripHeaderResult(
            lines=["code\n"],
            removed_span=(0, 2),
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.MALFORMED_REMOVED,
                reason="removed recoverable header",
                notes=["processor preserved a recoverable removal"],
            ),
        )
    )
    ctx.header_processor = processor
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=None,
        block=None,
        mapping=None,
    )

    ctx = run_stripper(ctx)

    assert processor.calls == [
        StripCall(
            lines=tuple(lines),
            span=(0, 2),
            newline_style="\n",
            ends_with_newline=True,
        )
    ]
    assert ctx.status.strip is StripStatus.READY
    assert ctx.status.header is HeaderStatus.DETECTED
    assert materialize_updated_lines(ctx) == ["code\n"]
    # EditView records the full single-splice transformation used by the
    # structured diff path, including the owned blank separator after the header.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 4
    assert edit.new_lines == ()
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "processor preserved a recoverable removal")
    ]
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_READY,
        cluster=Cluster.WOULD_CHANGE,
        message="header removal available",
        terminal=False,
    )


# --- Additional stripper behavior tests ---


def test_stripper_preserves_shebang_before_header(tmp_path: Path) -> None:
    """Removing a header after a shebang should preserve the shebang and body."""
    lines: list[str] = [
        "#!/usr/bin/env python\n",
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "print('body')\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "script.py", lines)
    ctx.run_options = RunOptions(
        apply_changes=True,
    )
    ctx.views.header = HeaderView(
        range=(1, 3),
        lines=lines[1:4],
        block="".join(lines[1:4]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == [
        "#!/usr/bin/env python\n",
        "print('body')\n",
    ]
    # The planned edit starts after the shebang, so structured diffs keep the
    # interpreter line as unchanged context rather than part of the removal.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 1
    assert edit.old_end == 4
    assert edit.new_lines == ()
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_READY,
        cluster=Cluster.CHANGED,
        message="header removal available",
        terminal=False,
    )


def test_stripper_removing_whole_file_header_keeps_final_newline_placeholder(
    tmp_path: Path,
) -> None:
    """A header-only file with a final newline should strip to one newline placeholder."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "header_only.py", lines)
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\n"]


def test_stripper_removing_whole_file_header_without_final_newline_is_empty(
    tmp_path: Path,
) -> None:
    """A header-only file without a final newline strips to a truly empty image."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "header_only_no_fnl.py", lines)
    ctx.ends_with_newline = False
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert ctx.status.header is HeaderStatus.DETECTED
    assert materialize_updated_lines(ctx) == []
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 3
    assert edit.new_lines == ()
    assert ctx.halt_state is None


def test_stripper_missing_header_is_not_needed(tmp_path: Path) -> None:
    """Missing headers should not produce an updated image."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "missing.py",
        ["print('body')\n"],
    )
    ctx.status.header = HeaderStatus.MISSING
    ctx.views.header = None

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "No header to be stripped.")
    ]
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_NONE,
        cluster=Cluster.UNCHANGED,
        message="no header to remove",
        terminal=False,
    )


def test_stripper_rejects_malformed_header_status(tmp_path: Path) -> None:
    """Malformed scanner status should fail and halt before processor removal."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "malformed.py",
        ["# broken\n", "body\n"],
    )
    ctx.status.header = HeaderStatus.MALFORMED_SOME_FIELDS

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    reason: str = f"No header to be stripped: {HeaderStatus.MALFORMED_SOME_FIELDS}"
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, reason)
    ]
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "StripperStep"
    assert ctx.halt_state.reason_code == reason
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_FAILED,
        cluster=Cluster.ERROR,
        message="failed to prepare header removal",
        terminal=True,
    )


def test_stripper_not_found_diagnostic_is_not_needed(tmp_path: Path) -> None:
    """Processor NOT_FOUND diagnostics should leave stripping as not needed."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "not_found.py",
        ["# not a topmark header\n", "body\n"],
    )
    ctx.header_processor = _NotFoundStripProcessor()
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# not a topmark header\n"],
        block="# not a topmark header\n",
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "stub not found")
    ]
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_NONE,
        cluster=Cluster.UNCHANGED,
        message="no header to remove",
        terminal=False,
    )


def test_stripper_error_diagnostic_halts_without_updated_view(tmp_path: Path) -> None:
    """Processor ERROR diagnostics should halt and avoid producing updated lines."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "error.py",
        ["# broken\n", "body\n"],
    )
    ctx.header_processor = _ErrorStripProcessor()
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# broken\n"],
        block="# broken\n",
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.ERROR, "stub strip error")
    ]
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "StripperStep"
    assert ctx.halt_state.reason_code == "stub strip error"
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_FAILED,
        cluster=Cluster.ERROR,
        message="failed to prepare header removal",
        terminal=True,
    )


def test_stripper_preserves_crlf_newline_style_for_empty_placeholder(
    tmp_path: Path,
) -> None:
    """Header-only CRLF input should preserve CRLF in the logical-empty placeholder."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\r\n",
        "# h\r\n",
        f"# {TOPMARK_END_MARKER}\r\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "crlf.py", lines)
    ctx.newline_style = "\r\n"
    ctx.ends_with_newline = True
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\r\n"]


def test_stripper_removing_bom_only_header_keeps_bom_placeholder(
    tmp_path: Path,
) -> None:
    """BOM-only strip results should preserve the BOM and final newline semantics.

    `ReaderStep` strips the BOM before populating `ctx.views.image`;
    `ctx.leading_bom=True` is the stripper's sole BOM input.
    """
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "bom_only.py", lines)
    ctx.leading_bom = True
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\ufeff\n"]
    # The BOM placeholder is replacement content because the whole original
    # image is removed by the splice.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 3
    assert edit.new_lines == ("\ufeff\n",)


def test_stripper_removing_bom_only_header_without_final_newline_keeps_bom(
    tmp_path: Path,
) -> None:
    """Reader-stripped BOM state is restored without inventing a final newline.

    `ReaderStep` strips the BOM before populating `ctx.views.image`;
    `ctx.leading_bom=True` is the stripper's sole BOM input.
    """
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "bom_no_fnl.py", lines)
    ctx.leading_bom = True
    ctx.ends_with_newline = False
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert ctx.status.header is HeaderStatus.DETECTED
    assert materialize_updated_lines(ctx) == ["\ufeff"]
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 3
    assert edit.new_lines == ("\ufeff",)
    assert ctx.halt_state is None


def test_stripper_preserves_leading_bom_on_remaining_body(tmp_path: Path) -> None:
    """If the original image had a BOM, stripped output should retain it.

    `ReaderStep` strips the BOM before populating `ctx.views.image`;
    `ctx.leading_bom=True` is the stripper's sole BOM input.
    """
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "body\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "bom.py", lines)
    ctx.leading_bom = True
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines[:3],
        block="".join(lines[:3]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\ufeffbody\n"]
    # The structured edit describes the actual output transformation: the BOM
    # is reattached to the remaining body, so the body line is replacement text.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 4
    assert edit.new_lines == ("\ufeffbody\n",)


class _NoopEmptyStripProcessor(HeaderProcessor):
    """Processor stub that reports an empty/no-op strip result."""

    namespace = "test"
    local_key = "noop_empty_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Return a NOOP_EMPTY diagnostic."""
        return StripHeaderResult(
            lines=lines,
            removed_span=None,
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.NOOP_EMPTY,
                reason="stub empty no-op",
            ),
        )


class _MalformedRefusedStripProcessor(HeaderProcessor):
    """Processor stub that refuses malformed header removal."""

    namespace = "test"
    local_key = "malformed_refused_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Return a MALFORMED_REFUSED diagnostic."""
        return StripHeaderResult(
            lines=lines,
            removed_span=None,
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.MALFORMED_REFUSED,
                reason="stub malformed refused",
            ),
        )


class _RemovedWithoutSpanStripProcessor(HeaderProcessor):
    """Processor stub that reports removal without a removed span."""

    namespace = "test"
    local_key = "removed_without_span_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Return changed lines with an invalid missing span."""
        return StripHeaderResult(
            lines=lines[1:],
            removed_span=None,
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.REMOVED,
                reason="stub removed without span",
            ),
        )


def test_stripper_empty_image_is_not_needed(tmp_path: Path) -> None:
    """A processable but empty image has no removable header."""
    ctx: ProcessingContext = _make_strip_context(tmp_path / "empty.py", [])

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert ctx.halt_state is None


def test_stripper_noop_empty_diagnostic_is_not_needed(tmp_path: Path) -> None:
    """Processor NOOP_EMPTY diagnostics should not produce updated lines."""
    ctx: ProcessingContext = _make_strip_context(tmp_path / "noop.py", ["\n"])
    ctx.header_processor = _NoopEmptyStripProcessor()
    ctx.status.header = HeaderStatus.EMPTY

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "stub empty no-op")
    ]
    assert ctx.halt_state is None


def test_stripper_malformed_refused_diagnostic_halts_without_update(tmp_path: Path) -> None:
    """Processor MALFORMED_REFUSED diagnostics are policy blocks, not removals."""
    ctx: ProcessingContext = _make_strip_context(tmp_path / "refused.py", ["# broken\n"])
    ctx.header_processor = _MalformedRefusedStripProcessor()
    ctx.status.header = HeaderStatus.EMPTY

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.views.edit is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.ERROR, "stub malformed refused")
    ]
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "StripperStep"
    assert ctx.halt_state.reason_code == "stub malformed refused"
    _assert_hint(
        ctx,
        code=KnownCode.STRIP_FAILED,
        cluster=Cluster.ERROR,
        message="failed to prepare header removal",
        terminal=True,
    )


def test_stripper_removed_without_span_is_treated_as_not_needed(tmp_path: Path) -> None:
    """A processor must provide a removed span for strip normalization to proceed."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "missing_span.py",
        ["# header\n", "body\n"],
    )
    ctx.header_processor = _RemovedWithoutSpanStripProcessor()
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# header\n"],
        block="# header\n",
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is None


def test_stripper_drops_at_most_one_owned_separator_and_preserves_user_whitespace(
    tmp_path: Path,
) -> None:
    """Only one exact policy separator is removed; user whitespace remains."""
    from tests.helpers.registry import make_file_type
    from topmark.filetypes.policy import FileTypeHeaderPolicy

    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        " \n",
        "body\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "spacer.py", lines)
    processor = _RecordingStripProcessor(
        StripHeaderResult(
            lines=["\n", "\n", " \n", "body\n"],
            removed_span=(0, 2),
            diagnostic=StripDiagnostic(kind=StripDiagKind.REMOVED),
        )
    )
    ctx.header_processor = processor
    ctx.file_type = make_file_type(
        local_key="spacer_policy",
        extensions=[".py"],
        header_policy=FileTypeHeaderPolicy(ensure_blank_after_header=True),
    )
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines[:3],
        block="".join(lines[:3]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\n", " \n", "body\n"]
    assert processor.calls[0].span == (0, 2)
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.halt_state is None


def test_stripper_preserves_whitespace_only_line_at_removal_site(tmp_path: Path) -> None:
    """A non-exact whitespace line at the removal site remains user content."""
    from tests.helpers.registry import make_file_type
    from topmark.filetypes.policy import FileTypeHeaderPolicy

    lines: list[str] = ["# header\n", " \n", "body\n"]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "user_whitespace.py", lines)
    ctx.header_processor = _RecordingStripProcessor(
        StripHeaderResult(
            lines=[" \n", "body\n"],
            removed_span=(0, 0),
            diagnostic=StripDiagnostic(kind=StripDiagKind.REMOVED),
        )
    )
    ctx.file_type = make_file_type(
        local_key="user_whitespace_policy",
        extensions=[".py"],
        header_policy=FileTypeHeaderPolicy(ensure_blank_after_header=True),
    )
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=lines[:1],
        block=lines[0],
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == [" \n", "body\n"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.halt_state is None


def test_stripper_removes_processor_newline_when_reader_reported_no_final_newline(
    tmp_path: Path,
) -> None:
    """Reader-owned no-FNL state normalizes a processor-emitted CRLF suffix."""
    lines: list[str] = ["<header>\r\n", "</header>\r\n", "body"]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "no_fnl.xml", lines)
    ctx.newline_style = "\r\n"
    ctx.ends_with_newline = False
    processor = _RecordingStripProcessor(
        StripHeaderResult(
            lines=["body\r\n"],
            removed_span=(0, 1),
            diagnostic=StripDiagnostic(kind=StripDiagKind.REMOVED),
        )
    )
    ctx.header_processor = processor
    ctx.views.header = HeaderView(
        range=(0, 1),
        lines=lines[:2],
        block="".join(lines[:2]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert processor.calls[0].newline_style == "\r\n"
    assert processor.calls[0].ends_with_newline is False
    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["body"]
    assert isinstance(ctx.views.edit, EditView)
    assert ctx.halt_state is None


def test_stripper_collapses_exact_blank_body_to_single_placeholder(
    tmp_path: Path,
) -> None:
    """Exact blank-only bodies should collapse to one placeholder when FNL existed."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "\n",
        "\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "blank_body.py", lines)
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines[:3],
        block="".join(lines[:3]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\n"]
    # The final placeholder newline is the unchanged suffix line. The planned
    # edit therefore removes only the header plus the first owned blank line.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 4
    assert edit.new_lines == ()
