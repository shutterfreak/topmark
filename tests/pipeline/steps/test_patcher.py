# topmark:header:start
#
#   project      : TopMark
#   file         : test_patcher.py
#   file_relpath : tests/pipeline/steps/test_patcher.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Contract tests for view-based unified-diff generation by the patcher step.

The tests exercise the public step lifecycle, structured-edit fast path,
updated-image fallback, status/hint semantics, and raw newline preservation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

import topmark.pipeline.steps.patcher as patcher_module
from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_builder
from tests.helpers.pipeline import run_comparer
from tests.helpers.pipeline import run_patcher
from tests.helpers.pipeline import run_planner
from tests.helpers.pipeline import run_reader
from tests.helpers.pipeline import run_renderer
from tests.helpers.pipeline import run_resolver
from tests.helpers.pipeline import run_scanner
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PatchStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps.patcher import PatcherStep
from topmark.pipeline.views import DiffView
from topmark.pipeline.views import EditView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import PlanEditKind
from topmark.pipeline.views import PlannedEdit
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import ViewSlot
from topmark.pipeline.views import compose_updated_content
from topmark.presentation.formatters.unified_diff import format_patch_plain
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import HaltState
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint


def _make_patcher_context(
    path: Path,
    *,
    image_lines: list[str],
    updated_lines: list[str] | None,
    comparison_status: ComparisonStatus = ComparisonStatus.CHANGED,
    newline_style: str = "\n",
) -> ProcessingContext:
    """Create a minimal post-comparison context for patcher step tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.comparison = comparison_status
    ctx.views.image = ListFileImageView(image_lines)
    ctx.views.updated = None if updated_lines is None else UpdatedView(lines=updated_lines)
    ctx.newline_style = newline_style
    return ctx


def _run_to_patcher(file: Path, cfg: FrozenConfig) -> ProcessingContext:
    """Drive the view-based pipeline through `PatcherStep` and return its context."""
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    ctx = run_reader(ctx)
    ctx = run_scanner(ctx)
    ctx = run_builder(ctx)
    ctx = run_renderer(ctx)
    ctx = run_planner(ctx)  # produce the updated and structured-edit views
    ctx = run_comparer(ctx)  # classify current versus planned content
    ctx = run_patcher(ctx)
    return ctx


def test_patcher_declares_status_and_view_contracts() -> None:
    """Step metadata should expose every status axis and view consumed by the patcher."""
    step = PatcherStep()

    assert step.primary_axis is Axis.PATCH
    assert step.axes_written == (Axis.COMPARISON, Axis.PATCH)
    assert step.consumes_views == frozenset({ViewSlot.IMAGE, ViewSlot.UPDATED, ViewSlot.EDIT})


def test_patcher_diff_preserves_crlf_and_render_markers(
    tmp_path: Path,
) -> None:
    r"""CRLF-seeded file → diff lines use CRLF; render_patch shows \\r\\n markers."""
    path: Path = tmp_path / "a.ts"
    # Ensure file content is CRLF-seeded.
    with path.open("w", encoding="utf-8", newline="\r\n") as fp:
        # Add a syntactically valid TopMark header field (key:value)
        fp.write(
            f"// {TOPMARK_START_MARKER}\n// test:header\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n"
        )

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = _run_to_patcher(path, cfg)

    # We expect a change (strip/replace) to have produced a diff.
    diff_text: str = (ctx.views.diff.text if ctx.views.diff else "") or ""
    assert diff_text, "Expected non-empty unified diff from patcher"

    # The raw diff is produced with lineterm = ctx.newline_style.
    # If reader detected CRLF, ensure the diff contains CRLF in hunk lines.
    if ctx.newline_style == "\r\n":
        assert "\r\n" in diff_text, "Raw diff should contain CRLF line terminators"

    # Pass a list of lines to preserve native EOLs; when given a single string,
    # render_patch would lose CRLF markers due to splitlines() default behavior.
    rendered: str = format_patch_plain(
        patch=diff_text.splitlines(keepends=True),
    )
    # Depending on render_patch implementation, CRLF may be preserved as literal
    # `\r\n` or displayed via explicit markers.
    assert (
        ("\r\n" in rendered)
        or ("\\r\\n" in rendered)
        or ("␍␊" in rendered)
        or ("CRLF" in rendered.upper())
    )
    assert "\n\r" not in rendered  # avoid flipped sequence


def test_patcher_skips_when_comparison_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNCHANGED comparison should skip without materializing either image."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "unchanged.py",
        image_lines=["body\n"],
        updated_lines=["body\n"],
        comparison_status=ComparisonStatus.UNCHANGED,
    )

    def fail_materialization(*args: object, **kwargs: object) -> list[str]:
        del args, kwargs
        raise AssertionError("unchanged content should not be materialized")

    monkeypatch.setattr(type(ctx), "materialize_image_lines", fail_materialization)
    monkeypatch.setattr(type(ctx), "materialize_updated_lines", fail_materialization)

    ctx = run_patcher(ctx)

    assert ctx.status.patch is PatchStatus.SKIPPED
    assert ctx.status.comparison is ComparisonStatus.UNCHANGED
    assert ctx.views.diff == DiffView(text=None)
    assert ctx.halt_state is None
    hint: Hint = ctx.diagnostic_hints.items[-1]
    assert (hint.axis, hint.code, hint.cluster, hint.message, hint.terminal) == (
        Axis.PATCH,
        KnownCode.PATCH_SKIPPED.value,
        Cluster.UNCHANGED.value,
        "no patch needed (unchanged)",
        False,
    )


def test_patcher_fails_when_changed_comparison_has_no_patch_source(
    tmp_path: Path,
) -> None:
    """A confirmed change without updated content or a usable edit cannot produce a patch."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "missing_updated.py",
        image_lines=["old\n"],
        updated_lines=None,
        comparison_status=ComparisonStatus.CHANGED,
    )

    ctx = run_patcher(ctx)

    assert ctx.status.patch is PatchStatus.FAILED
    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert ctx.views.diff == DiffView(text=None)
    assert ctx.halt_state is None
    assert [(item.level, item.message) for item in ctx.diagnostics] == [
        (
            DiagnosticLevel.ERROR,
            "Cannot generate patch: comparison detected changes but no updated image "
            "or usable structured edit is available.",
        )
    ]
    hint: Hint = ctx.diagnostic_hints.items[-1]
    assert (hint.axis, hint.code, hint.cluster, hint.message, hint.terminal) == (
        Axis.PATCH,
        KnownCode.PATCH_FAILED.value,
        Cluster.ERROR.value,
        "change detected but patch generation failed",
        True,
    )


def test_patcher_generates_unified_diff_for_changed_updated_image(
    tmp_path: Path,
) -> None:
    """Changed updated image should produce a unified diff view."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "changed.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert "--- " in diff_text
    assert "+++ " in diff_text
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text
    assert materialize_updated_lines(ctx) == ["new\n", "body\n"]


@pytest.mark.parametrize(
    ("log_level", "expect_preview_formatting"),
    [
        pytest.param(logging.CRITICAL, False, id="critical"),
        pytest.param(logging.INFO, True, id="info"),
    ],
)
def test_patcher_formats_log_preview_only_when_info_logging_is_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    log_level: int,
    expect_preview_formatting: bool,
) -> None:
    """Diff preview formatting should follow the patcher logger's INFO-enabled state."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "changed.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
    formatted_patches: list[list[str] | str] = []

    def record_format_patch_plain(
        *,
        patch: list[str] | str,
    ) -> str:
        formatted_patches.append(patch)
        return "formatted preview"

    monkeypatch.setattr(
        "topmark.pipeline.steps.patcher.format_patch_plain",
        record_format_patch_plain,
    )
    caplog.set_level(log_level, logger="topmark.pipeline.steps.patcher")

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text
    assert bool(formatted_patches) is expect_preview_formatting


def test_patcher_normalizes_empty_diff_to_unchanged(
    tmp_path: Path,
) -> None:
    """CHANGED comparison with identical images should normalize to unchanged."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "empty_diff.py",
        image_lines=["same\n"],
        updated_lines=["same\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )

    ctx = run_patcher(ctx)

    assert ctx.status.comparison is ComparisonStatus.UNCHANGED
    assert ctx.status.patch is PatchStatus.SKIPPED
    assert ctx.views.diff == DiffView(text=None)


def test_patcher_preserves_configured_newline_style_in_raw_diff(
    tmp_path: Path,
) -> None:
    """Raw diff text should use the newline style carried by the context."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "crlf_diff.py",
        image_lines=["old\r\n", "body\r\n"],
        updated_lines=["new\r\n", "body\r\n"],
        comparison_status=ComparisonStatus.CHANGED,
        newline_style="\r\n",
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "\r\n" in diff_text
    assert "\n\r" not in diff_text


def test_patcher_halts_when_comparison_status_is_pending(
    tmp_path: Path,
) -> None:
    """BaseStep should halt if patcher is invoked before comparison completes."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "pending.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
        comparison_status=ComparisonStatus.PENDING,
    )

    ctx = run_patcher(ctx)

    assert ctx.status.patch is PatchStatus.PENDING
    assert ctx.views.diff is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "PatcherStep did not set state."


def test_patcher_halts_when_comparison_status_is_skipped(
    tmp_path: Path,
) -> None:
    """A skipped comparison should leave patch pending for the generic lifecycle halt."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "skipped.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
        comparison_status=ComparisonStatus.SKIPPED,
    )

    ctx = run_patcher(ctx)

    assert ctx.status.patch is PatchStatus.PENDING
    assert ctx.views.diff is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "PatcherStep did not set state."


def test_patcher_preserves_existing_halt_and_patch_state(
    tmp_path: Path,
) -> None:
    """An already-halted context should not run or replace its original halt."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "halted.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
    )
    retained_diff = DiffView(text="retained patch")
    ctx.views.diff = retained_diff
    step = PatcherStep()
    ctx.request_halt(reason="earlier failure", at_step=step)
    original_halt: HaltState | None = ctx.halt_state

    ctx = step(ctx)

    assert ctx.status.patch is PatchStatus.PENDING
    assert ctx.views.diff is retained_diff
    assert ctx.halt_state is original_halt
    assert ctx.diagnostic_hints.items == []


def test_patcher_uses_stdin_filename_in_unified_diff_labels(
    tmp_path: Path,
) -> None:
    """STDIN-backed diffs should label files with the logical stdin filename."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "materialized-stdin.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
    ctx.run_options = RunOptions(
        stdin_mode=True,
        stdin_filename="logical/input.py",
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "--- logical/input.py (current)" in diff_text
    assert "+++ logical/input.py (updated)" in diff_text
    assert "materialized-stdin.py" not in diff_text


def test_patcher_uses_structured_diff_for_valid_single_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid single-edit metadata should avoid the generic difflib fallback."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "structured_match.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
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

    def fail_difflib_fallback(
        **kwargs: object,
    ) -> list[str]:
        raise AssertionError("difflib fallback should not be used")

    monkeypatch.setattr(
        patcher_module,
        "_render_difflib_unified_diff",
        fail_difflib_fallback,
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text


def test_patcher_uses_structured_diff_without_materializing_lazy_updated_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lazy updated content should not be materialized when single-edit metadata is enough."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "lazy_structured.py",
        image_lines=["old\n", "body\n"],
        updated_lines=None,
        comparison_status=ComparisonStatus.CHANGED,
    )
    ctx.views.updated = UpdatedView(
        lines=compose_updated_content(("new\n",), ("body\n",)),
    )
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

    def fail_materialize_updated_lines(
        self: ProcessingContext,
    ) -> list[str]:
        del self
        raise AssertionError("updated lines should not be materialized for structured diff")

    monkeypatch.setattr(
        type(ctx),
        "materialize_updated_lines",
        fail_materialize_updated_lines,
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text


def test_patcher_uses_valid_structured_edit_without_updated_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid structured edit should be sufficient when no updated view is retained."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "edit_only.py",
        image_lines=["old\n", "body\n"],
        updated_lines=None,
    )
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

    def fail_difflib_fallback(**kwargs: object) -> list[str]:
        del kwargs
        raise AssertionError("valid edit-only metadata should not need difflib")

    monkeypatch.setattr(patcher_module, "_render_difflib_unified_diff", fail_difflib_fallback)

    ctx = run_patcher(ctx)

    assert ctx.status.patch is PatchStatus.GENERATED
    assert ctx.views.diff is not None
    assert ctx.views.diff.text is not None
    assert "-old\n" in ctx.views.diff.text
    assert "+new\n" in ctx.views.diff.text


def test_patcher_normalizes_structured_no_op_to_unchanged_without_updated_view(
    tmp_path: Path,
) -> None:
    """An edit-only no-op should clear the claimed change instead of failing fallback."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "structured_no_op.py",
        image_lines=["body\n"],
        updated_lines=None,
    )
    ctx.views.edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=0,
                new_lines=(),
            ),
        )
    )

    ctx = run_patcher(ctx)

    assert ctx.status.comparison is ComparisonStatus.UNCHANGED
    assert ctx.status.patch is PatchStatus.SKIPPED
    assert ctx.views.diff == DiffView(text=None)


def test_patcher_falls_back_for_mismatching_structured_edit(
    tmp_path: Path,
) -> None:
    """Mismatching structured edit metadata should use the difflib fallback."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "structured_mismatch.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
    ctx.views.edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=1,
                new_lines=("different\n",),
            ),
        )
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text
    assert "different" not in diff_text


def test_patcher_falls_back_for_multiple_structured_edits(
    tmp_path: Path,
) -> None:
    """Multiple edits should use the full updated image because the fast path is contiguous."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "multiple_edits.py",
        image_lines=["old one\n", "body\n", "old two\n"],
        updated_lines=["new one\n", "body\n", "new two\n"],
    )
    ctx.views.edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=1,
                new_lines=("new one\n",),
            ),
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=2,
                old_end=3,
                new_lines=("new two\n",),
            ),
        )
    )

    ctx = run_patcher(ctx)

    assert ctx.status.patch is PatchStatus.GENERATED
    assert ctx.views.diff is not None
    assert ctx.views.diff.text is not None
    assert "-old one\n" in ctx.views.diff.text
    assert "+new one\n" in ctx.views.diff.text
    assert "-old two\n" in ctx.views.diff.text
    assert "+new two\n" in ctx.views.diff.text


def test_patcher_falls_back_when_structured_shadow_diff_is_unavailable(
    tmp_path: Path,
) -> None:
    """Invalid structured edit metadata should leave difflib as fallback output."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "structured_fallback.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
    ctx.views.edit = EditView(
        edits=(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=-1,
                old_end=1,
                new_lines=("new\n",),
            ),
        )
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=-1,
                old_end=1,
                new_lines=("new\n",),
            ),
            id="negative-start",
        ),
        pytest.param(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=1,
                old_end=0,
                new_lines=("new\n",),
            ),
            id="reversed-span",
        ),
        pytest.param(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=3,
                new_lines=("new\n",),
            ),
            id="span-past-end",
        ),
    ],
)
def test_patcher_falls_back_for_invalid_single_edit_spans(
    tmp_path: Path,
    edit: PlannedEdit,
) -> None:
    """Invalid single-edit spans should be rejected before structured rendering."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "invalid_span.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
    ctx.views.edit = EditView(edits=(edit,))

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text


def test_patcher_falls_back_when_structured_renderer_returns_no_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid edit metadata should still fall back if structured rendering declines it."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "structured_none.py",
        image_lines=["old\n", "body\n"],
        updated_lines=["new\n", "body\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )
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

    def _render_no_patch(
        *,
        original_lines: Sequence[str],
        edit: PlannedEdit,
        fromfile: str,
        tofile: str,
        fromfiledate: str,
        tofiledate: str,
        lineterm: str,
        context: int = 3,
    ) -> list[str] | None:
        """Test double that forces structured rendering fallback.

        Returns:
            None: Always returns ``None`` to simulate a structured renderer that
            declines to render the supplied edit.
        """
        del original_lines, edit, fromfile, tofile, fromfiledate, tofiledate, lineterm, context
        return None

    monkeypatch.setattr(
        patcher_module,
        "render_structured_unified_diff",
        _render_no_patch,
    )

    ctx = run_patcher(ctx)

    diff_text: str = ctx.views.diff.text if ctx.views.diff and ctx.views.diff.text else ""
    assert ctx.status.patch is PatchStatus.GENERATED
    assert "-old\n" in diff_text
    assert "+new\n" in diff_text


def test_patcher_marks_failed_when_backend_returns_empty_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-empty patch lines that join to empty text should mark patch generation failed."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "empty_text.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
        comparison_status=ComparisonStatus.CHANGED,
    )

    def _render_empty_text_patch(
        *,
        current_lines: Sequence[str],
        updated_lines: Sequence[str],
        fromfile: str,
        tofile: str,
        fromfiledate: str,
        tofiledate: str,
        lineterm: str,
    ) -> list[str]:
        """Test double that produces an empty rendered diff payload.

        Returns:
            list[str]: A single empty string element, causing the joined diff text
            to be empty while the rendered patch line collection remains non-empty.
        """
        del (
            current_lines,
            updated_lines,
            fromfile,
            tofile,
            fromfiledate,
            tofiledate,
            lineterm,
        )
        return [""]

    monkeypatch.setattr(
        patcher_module,
        "_render_difflib_unified_diff",
        _render_empty_text_patch,
    )

    ctx = run_patcher(ctx)

    assert ctx.status.comparison is ComparisonStatus.CHANGED
    assert ctx.status.patch is PatchStatus.FAILED
    assert ctx.views.diff == DiffView(text=None)
    assert [(item.level, item.message) for item in ctx.diagnostics] == [
        (
            DiagnosticLevel.ERROR,
            "Patch generation produced empty diff text for changed content.",
        )
    ]
    hint: Hint = ctx.diagnostic_hints.items[-1]
    assert (hint.code, hint.cluster, hint.message, hint.terminal) == (
        KnownCode.PATCH_FAILED.value,
        Cluster.ERROR.value,
        "change detected but patch generation failed",
        True,
    )


# Additional tests for PatcherStep.hint


@pytest.mark.parametrize(
    ("apply_changes", "expected_cluster"),
    [
        pytest.param(False, Cluster.WOULD_CHANGE, id="dry-run"),
        pytest.param(True, Cluster.CHANGED, id="apply"),
    ],
)
def test_patcher_hint_reports_generated_patch_cluster_by_apply_mode(
    tmp_path: Path,
    apply_changes: bool,
    expected_cluster: Cluster,
) -> None:
    """Generated patch hints should distinguish previews from applied changes."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "generated_hint.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
    )
    ctx.status.patch = PatchStatus.GENERATED
    ctx.run_options = RunOptions(apply_changes=apply_changes)

    PatcherStep().hint(ctx)

    hint: Hint = ctx.diagnostic_hints.items[-1]
    assert hint.axis is Axis.PATCH
    assert hint.code == KnownCode.PATCH_GENERATED.value
    assert hint.cluster == expected_cluster.value
    assert hint.message == "patch generated"
    assert hint.terminal is False
    assert ctx.halt_state is None


def test_patcher_hint_reports_failed_patch(
    tmp_path: Path,
) -> None:
    """Failed patch status should emit a terminal error hint."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "failed_hint.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
    )
    ctx.status.patch = PatchStatus.FAILED

    PatcherStep().hint(ctx)

    hint: Hint = ctx.diagnostic_hints.items[-1]
    assert hint.axis is Axis.PATCH
    assert hint.code == KnownCode.PATCH_FAILED.value
    assert hint.cluster == Cluster.ERROR.value
    assert hint.message == "change detected but patch generation failed"
    assert hint.terminal is True
    assert ctx.halt_state is None


def test_patcher_hint_does_not_halt_when_patch_status_is_pending(
    tmp_path: Path,
) -> None:
    """Pending patch status should not mutate control flow from hint()."""
    ctx: ProcessingContext = _make_patcher_context(
        tmp_path / "pending_hint.py",
        image_lines=["old\n"],
        updated_lines=["new\n"],
    )
    ctx.status.patch = PatchStatus.PENDING

    PatcherStep().hint(ctx)

    assert len(ctx.diagnostic_hints) == 0
    assert ctx.halt_state is None
