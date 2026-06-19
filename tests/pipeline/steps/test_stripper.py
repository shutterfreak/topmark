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

from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_stripper
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.views import EditView
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import PlanEditKind
from topmark.processors.base import HeaderProcessor
from topmark.processors.types import StripDiagKind
from topmark.processors.types import StripDiagnostic
from topmark.processors.types import StripHeaderResult

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import PlannedEdit


# --- Helper classes and context factory for stripper tests ---


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


def test_stripper_uses_span_and_trims_leading_blank(tmp_path: Path) -> None:
    """When span is provided, stripper should remove exactly that region and trim."""
    file: Path = tmp_path / "x.py"
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "\n",
        "code\n",
    ]

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

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
    assert ctx.status.strip is StripStatus.READY
    assert ctx.status.header is HeaderStatus.DETECTED
    # EditView records the full single-splice transformation used by the
    # structured diff path, including the owned blank separator after the header.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 4
    assert edit.new_lines == ()


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
    assert ctx.halt_state is None


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
    assert ctx.halt_state is not None


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
    assert ctx.halt_state is None


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

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "stub strip error"


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
    """BOM-only strip results should preserve the BOM and final newline semantics."""
    lines: list[str] = [
        f"\ufeff# {TOPMARK_START_MARKER}\n",
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


def test_stripper_preserves_leading_bom_on_remaining_body(tmp_path: Path) -> None:
    """If the original image had a BOM, stripped output should retain it."""
    lines: list[str] = [
        f"\ufeff# {TOPMARK_START_MARKER}\n",
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


class _RemovedWithWhitespaceBodyStripProcessor(HeaderProcessor):
    """Processor stub that leaves user whitespace after removal."""

    namespace = "test"
    local_key = "removed_with_whitespace_body_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Return a removed header with a whitespace-only body line remaining."""
        return StripHeaderResult(
            lines=[" \n", "body\n"],
            removed_span=(0, 2),
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.REMOVED,
                reason="stub removed",
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
    assert ctx.halt_state is None


def test_stripper_noop_empty_diagnostic_is_not_needed(tmp_path: Path) -> None:
    """Processor NOOP_EMPTY diagnostics should not produce updated lines."""
    ctx: ProcessingContext = _make_strip_context(tmp_path / "noop.py", ["\n"])
    ctx.header_processor = _NoopEmptyStripProcessor()
    ctx.status.header = HeaderStatus.EMPTY

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is None


def test_stripper_malformed_refused_diagnostic_halts_without_update(tmp_path: Path) -> None:
    """Processor MALFORMED_REFUSED diagnostics are policy blocks, not removals."""
    ctx: ProcessingContext = _make_strip_context(tmp_path / "refused.py", ["# broken\n"])
    ctx.header_processor = _MalformedRefusedStripProcessor()
    ctx.status.header = HeaderStatus.EMPTY

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "stub malformed refused"


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


def test_stripper_drops_only_owned_exact_blank_separator(tmp_path: Path) -> None:
    """Strip removes an owned exact blank after the header but preserves user whitespace."""
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
    ctx.header_processor = _RemovedWithWhitespaceBodyStripProcessor()
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
    assert materialize_updated_lines(ctx) == [" \n", "body\n"]


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


def test_stripper_collapses_blank_body_without_final_newline_to_empty(
    tmp_path: Path,
) -> None:
    """Exact blank-only bodies should collapse to empty without original FNL."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "blank_body_no_fnl.py", lines)
    ctx.ends_with_newline = False
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines[:3],
        block="".join(lines[:3]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == []
    # Without final-newline semantics to preserve, the full image is removed
    # and no replacement lines are needed.
    assert isinstance(ctx.views.edit, EditView)
    edit: PlannedEdit = ctx.views.edit.edits[0]
    assert edit.kind is PlanEditKind.REMOVE
    assert edit.old_start == 0
    assert edit.old_end == 4
    assert edit.new_lines == ()
