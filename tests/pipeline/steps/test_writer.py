# topmark:header:start
#
#   project      : TopMark
#   file         : test_writer.py
#   file_relpath : tests/pipeline/steps/test_writer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the `writer` pipeline step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_writer
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.policy import HeaderMutationMode
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import WriteStatus
from topmark.pipeline.views import UpdatedView
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from _pytest.capture import CaptureResult

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext


def _make_writer_context(
    path: Path,
    *,
    updated_lines: list[str] | None = None,
    apply_changes: bool = True,
    plan_status: PlanStatus = PlanStatus.REPLACED,
    output_target: OutputTarget = OutputTarget.FILE,
    file_write_strategy: FileWriteStrategy = FileWriteStrategy.ATOMIC,
) -> ProcessingContext:
    """Create a minimal post-planner context for writer step tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.run_options = RunOptions(
        apply_changes=apply_changes,
        output_target=output_target,
        file_write_strategy=file_write_strategy,
    )
    ctx.status.fs = FsStatus.OK
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.plan = plan_status
    ctx.views.updated = None if updated_lines is None else UpdatedView(lines=updated_lines)
    ctx.newline_style = "\n"
    ctx.ends_with_newline = bool(updated_lines and updated_lines[-1].endswith("\n"))
    return ctx


def test_writer_dry_run_skips_filesystem_mutation(tmp_path: Path) -> None:
    """File-target preview mode should skip writes and preserve existing content."""
    path: Path = tmp_path / "dry_run.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=False,
        plan_status=PlanStatus.PREVIEWED,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.PENDING
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "WriterStep did not set state."


def test_writer_atomic_apply_writes_updated_image(tmp_path: Path) -> None:
    """Atomic apply mode should replace the file with the updated image."""
    path: Path = tmp_path / "atomic.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n", "body\n"],
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "updated\nbody\n"
    assert ctx.halt_state is None


def test_writer_inplace_apply_writes_updated_image(tmp_path: Path) -> None:
    """In-place apply mode should write the updated image."""
    path: Path = tmp_path / "inplace.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
        file_write_strategy=FileWriteStrategy.INPLACE,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "updated\n"
    assert ctx.halt_state is None


def test_writer_skips_when_updated_view_is_missing(tmp_path: Path) -> None:
    """Missing updated view should leave writer skipped and avoid mutation."""
    path: Path = tmp_path / "missing_updated.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=None,
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.PENDING
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "WriterStep did not set state."


def test_writer_skips_non_concrete_file_plan_status(tmp_path: Path) -> None:
    """File-target writer should skip when planner did not select a concrete mutation."""
    path: Path = tmp_path / "preview_apply.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=True,
        plan_status=PlanStatus.PREVIEWED,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.PENDING
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "WriterStep did not set state."


def test_writer_stdout_preview_emits_updated_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """STDOUT target should emit preview content without mutating the file."""
    path: Path = tmp_path / "stdout.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=False,
        plan_status=PlanStatus.PREVIEWED,
        output_target=OutputTarget.STDOUT,
    )

    ctx = run_writer(ctx)

    captured: CaptureResult[str] = capsys.readouterr()
    assert ctx.status.write is WriteStatus.WRITTEN
    assert captured.out == "updated\n"
    assert path.read_text(encoding="utf-8") == "original\n"


def test_writer_policy_blocks_insert_when_update_only(tmp_path: Path) -> None:
    """UPDATE_ONLY policy should block header insertion writes."""
    path: Path = tmp_path / "insert_blocked.py"
    path.write_text("original\n", encoding="utf-8")
    cfg: MutableConfig = mutable_config_from_defaults()
    cfg.policy.header_mutation_mode = HeaderMutationMode.UPDATE_ONLY
    ctx: ProcessingContext = make_pipeline_context(path, cfg.freeze())
    ctx.run_options = RunOptions(apply_changes=True)
    ctx.status.fs = FsStatus.OK
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.plan = PlanStatus.INSERTED
    ctx.views.updated = UpdatedView(lines=["updated\n"])

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.SKIPPED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert any(
        diagnostic.message == "Skipped by policy: header_mutation_mode=update_only"
        for diagnostic in ctx.diagnostics
    )


def test_writer_policy_blocks_replace_when_add_only(tmp_path: Path) -> None:
    """ADD_ONLY policy should block header replacement writes."""
    path: Path = tmp_path / "replace_blocked.py"
    path.write_text("original\n", encoding="utf-8")
    cfg: MutableConfig = mutable_config_from_defaults()
    cfg.policy.header_mutation_mode = HeaderMutationMode.ADD_ONLY
    ctx: ProcessingContext = make_pipeline_context(path, cfg.freeze())
    ctx.run_options = RunOptions(apply_changes=True)
    ctx.status.fs = FsStatus.OK
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.plan = PlanStatus.REPLACED
    ctx.views.updated = UpdatedView(lines=["updated\n"])

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.SKIPPED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert any(
        diagnostic.message == "Skipped by policy: header_mutation_mode=add_only"
        for diagnostic in ctx.diagnostics
    )


def test_writer_write_failure_sets_failed_status_and_preserves_original_file(
    tmp_path: Path,
) -> None:
    """Atomic write failure should report FAILED and avoid truncating the target file."""
    path: Path = tmp_path / "missing-parent" / "target.py"
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.FAILED
    assert not path.exists()
    assert any("Atomic write failed:" in diagnostic.message for diagnostic in ctx.diagnostics)
