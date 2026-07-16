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

import os
from typing import TYPE_CHECKING
from typing import NoReturn

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_writer
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.policy import HeaderMutationMode
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.context.model import HaltState
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import Hint
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import WriteStatus
from topmark.pipeline.steps.writer import StdoutSink
from topmark.pipeline.steps.writer import WriterStep
from topmark.pipeline.views import UpdatedContent
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import ViewSlot
from topmark.pipeline.views import compose_updated_content
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureResult
    from _pytest.monkeypatch import MonkeyPatch

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.steps.writer import WriteResult


def _make_writer_context(
    path: Path,
    *,
    updated_lines: UpdatedContent | list[str] | None = None,
    apply_changes: bool = True,
    plan_status: PlanStatus = PlanStatus.REPLACED,
    output_target: OutputTarget = OutputTarget.FILE,
    file_write_strategy: FileWriteStrategy | None = FileWriteStrategy.ATOMIC,
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
    ctx.ends_with_newline = (
        bool(updated_lines and updated_lines[-1].endswith("\n"))
        if isinstance(updated_lines, list)
        else True
    )
    return ctx


def _forbid_updated_materialization(monkeypatch: MonkeyPatch) -> None:
    """Fail the test if WriterStep falls back to eager updated-line materialization."""

    def fail_materialize(self: ProcessingContext) -> list[str]:
        raise AssertionError("WriterStep must stream updated content")

    monkeypatch.setattr(
        "topmark.pipeline.context.model.ProcessingContext.materialize_updated_lines",
        fail_materialize,
    )


def _assert_hint(
    ctx: ProcessingContext,
    *,
    code: KnownCode,
    cluster: Cluster,
    message: str,
    terminal: bool,
) -> None:
    """Assert the exact sole writer hint payload."""
    assert len(ctx.diagnostic_hints.items) == 1
    hint: Hint = ctx.diagnostic_hints.items[0]
    assert hint.axis is Axis.WRITE
    assert hint.code == code.value
    assert hint.cluster == cluster.value
    assert hint.message == message
    assert hint.terminal is terminal


def test_writer_declares_write_axis_and_updated_view_consumption() -> None:
    """Writer should advertise only the status and view contracts it owns."""
    step = WriterStep()

    assert step.primary_axis is Axis.WRITE
    assert step.axes_written == (Axis.WRITE,)
    assert step.consumes_views == frozenset({ViewSlot.UPDATED})


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


def test_writer_atomic_apply_writes_image_and_preserves_permissions(
    tmp_path: Path,
) -> None:
    """Atomic apply should replace content and preserve permissions best-effort."""
    path: Path = tmp_path / "atomic.py"
    path.write_text("original\n", encoding="utf-8")
    if os.name == "posix":
        # Use a non-default mode so replacement must deliberately preserve it.
        path.chmod(0o640)
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
    if os.name == "posix":
        # Atomic replacement creates a new file, so mode idempotence is observable here.
        assert path.stat().st_mode & 0o777 == 0o640
    assert ctx.status.plan is PlanStatus.REPLACED
    assert ctx.views.updated is not None
    assert ctx.views.updated.lines == ["updated\n", "body\n"]
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_WRITTEN,
        cluster=Cluster.CHANGED,
        message="changes written",
        terminal=False,
    )


def test_writer_inplace_apply_preserves_identity_and_permissions(
    tmp_path: Path,
) -> None:
    """In-place apply should preserve file identity and permissions best-effort."""
    path: Path = tmp_path / "inplace.py"
    path.write_text("original\n", encoding="utf-8")
    if os.name == "posix":
        # Use a non-default mode to make permission idempotence explicit.
        path.chmod(0o640)
    before: os.stat_result = path.stat()
    original_identity: tuple[int, int] = (before.st_dev, before.st_ino)
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
    after: os.stat_result = path.stat()
    assert (after.st_dev, after.st_ino) == original_identity
    if os.name == "posix":
        # Truncating in place must not alter the established mode.
        assert path.stat().st_mode & 0o777 == 0o640
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_WRITTEN,
        cluster=Cluster.CHANGED,
        message="changes written",
        terminal=False,
    )


@pytest.mark.parametrize(
    "strategy",
    (FileWriteStrategy.ATOMIC, FileWriteStrategy.INPLACE),
    ids=("atomic", "inplace"),
)
def test_writer_file_sinks_preserve_exact_planner_owned_bytes(
    tmp_path: Path,
    strategy: FileWriteStrategy,
) -> None:
    """File sinks should preserve BOM and final-newline choices without normalization."""
    path: Path = tmp_path / f"exact-{strategy.value}.py"
    path.write_text("original\n", encoding="utf-8")
    expected: str = "\ufefffirst\nlast"
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["\ufefffirst\n", "last"],
        file_write_strategy=strategy,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_bytes() == expected.encode()
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None


def test_writer_inplace_apply_creates_missing_target(tmp_path: Path) -> None:
    """In-place strategy should support creating a target in an existing directory."""
    path: Path = tmp_path / "created.py"
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["created\n"],
        file_write_strategy=FileWriteStrategy.INPLACE,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "created\n"
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None


def test_writer_unspecified_strategy_defaults_to_atomic(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """An unspecified file strategy should retain the safe atomic default."""
    path: Path = tmp_path / "default.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        file_write_strategy=None,
    )

    def fail_inplace_write(self: object, *, ctx: ProcessingContext) -> NoReturn:
        raise AssertionError(f"unspecified strategy selected in-place sink for {ctx.path}")

    monkeypatch.setattr(
        "topmark.pipeline.steps.writer.InplaceFileSink.write",
        fail_inplace_write,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "updated\n"
    assert ctx.halt_state is None


def test_writer_atomic_apply_creates_missing_target(tmp_path: Path) -> None:
    """Atomic strategy should create a new target when its parent exists."""
    path: Path = tmp_path / "atomic_created.py"
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["created\n"],
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "created\n"
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None


@pytest.mark.skipif(
    not hasattr(os, "fchmod") or not hasattr(os, "O_DIRECTORY"),
    reason="POSIX permission and directory-fsync fallback contract",
)
def test_writer_atomic_permission_and_directory_fsync_failures_are_best_effort(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Permission fallback should preserve mode despite a directory durability failure."""
    path: Path = tmp_path / "atomic_fallback.py"
    path.write_text("original\n", encoding="utf-8")
    # Establish a distinctive mode that the path-based fallback must preserve.
    path.chmod(0o640)
    ctx: ProcessingContext = _make_writer_context(path, updated_lines=["updated\n"])

    def fail_fchmod(fd: int, mode: int) -> NoReturn:
        raise OSError(f"fchmod unavailable for {fd} at {mode:o}")

    def fail_directory_open(path_text: str, flags: int) -> NoReturn:
        raise OSError(f"directory fsync unavailable for {path_text} at {flags}")

    monkeypatch.setattr("topmark.pipeline.steps.writer.os.fchmod", fail_fchmod)
    monkeypatch.setattr("topmark.pipeline.steps.writer.os.open", fail_directory_open)

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "updated\n"
    # Failed descriptor-based chmod must fall back without changing the original mode.
    assert path.stat().st_mode & 0o777 == 0o640
    assert ctx.diagnostics.items == []
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


def test_writer_preserves_preexisting_halt_and_performs_no_io(tmp_path: Path) -> None:
    """A pre-halted context should retain its owner, state, and destination contents."""
    path: Path = tmp_path / "halted.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(path, updated_lines=["updated\n"])
    ctx.halt_state = HaltState(reason_code="upstream refusal", step_name="PlannerStep")
    updated_view: UpdatedView | None = ctx.views.updated

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.PENDING
    assert ctx.status.plan is PlanStatus.REPLACED
    assert ctx.views.updated is updated_view
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.halt_state == HaltState(
        reason_code="upstream refusal",
        step_name="PlannerStep",
    )
    assert ctx.diagnostics.items == []
    assert ctx.diagnostic_hints.items == []


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
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_WRITTEN,
        cluster=Cluster.CHANGED,
        message="changes written",
        terminal=False,
    )


def test_stdout_sink_reports_utf8_bytes_for_unicode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stdout byte accounting should use encoded bytes, not character count."""
    path: Path = tmp_path / "unicode.py"
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["café ☕\n"],
        apply_changes=False,
        plan_status=PlanStatus.PREVIEWED,
        output_target=OutputTarget.STDOUT,
    )

    result = StdoutSink().write(ctx=ctx)

    assert capsys.readouterr().out == "café ☕\n"
    assert result.status is WriteStatus.WRITTEN
    assert result.bytes_written == len("café ☕\n".encode())


def test_stdout_sink_without_updated_content_skips_without_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stdout sink should report a zero-byte no-op when no updated image exists."""
    path: Path = tmp_path / "missing_stdout.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=None,
        apply_changes=False,
        plan_status=PlanStatus.PREVIEWED,
        output_target=OutputTarget.STDOUT,
    )

    result: WriteResult = StdoutSink().write(ctx=ctx)

    assert capsys.readouterr().out == ""
    assert result.status is WriteStatus.SKIPPED
    assert result.bytes_written == 0
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.diagnostics.items == []


def test_writer_policy_blocks_insert_when_update_only(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
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
    updated_view: UpdatedView = ctx.views.updated

    def fail_select_sink(context: ProcessingContext) -> NoReturn:
        raise AssertionError(f"policy refusal must not select a sink for {context.path}")

    monkeypatch.setattr("topmark.pipeline.steps.writer._select_sink", fail_select_sink)

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.SKIPPED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.status.plan is PlanStatus.INSERTED
    assert ctx.views.updated is updated_view
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.INFO
    assert ctx.diagnostics.items[0].message == "Skipped by policy: header_mutation_mode=update_only"
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_SKIPPED,
        cluster=Cluster.SKIPPED,
        message="write skipped (policy)",
        terminal=False,
    )


def test_writer_policy_blocks_replace_when_add_only(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
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
    updated_view: UpdatedView = ctx.views.updated

    def fail_select_sink(context: ProcessingContext) -> NoReturn:
        raise AssertionError(f"policy refusal must not select a sink for {context.path}")

    monkeypatch.setattr("topmark.pipeline.steps.writer._select_sink", fail_select_sink)

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.SKIPPED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert ctx.status.plan is PlanStatus.REPLACED
    assert ctx.views.updated is updated_view
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.INFO
    assert ctx.diagnostics.items[0].message == "Skipped by policy: header_mutation_mode=add_only"
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_SKIPPED,
        cluster=Cluster.SKIPPED,
        message="write skipped (policy)",
        terminal=False,
    )


def test_writer_removal_ignores_add_update_gate_and_writes_empty_image(
    tmp_path: Path,
) -> None:
    """Removal should write planner-owned empty output regardless of add-only policy."""
    path: Path = tmp_path / "removed.py"
    path.write_text("# header\nbody\n", encoding="utf-8")
    cfg: MutableConfig = mutable_config_from_defaults()
    cfg.policy.header_mutation_mode = HeaderMutationMode.ADD_ONLY
    ctx: ProcessingContext = make_pipeline_context(path, cfg.freeze())
    ctx.run_options = RunOptions(
        apply_changes=True,
        output_target=OutputTarget.FILE,
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )
    ctx.status.fs = FsStatus.OK
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.plan = PlanStatus.REMOVED
    ctx.views.updated = UpdatedView(lines=[])

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert ctx.status.plan is PlanStatus.REMOVED
    assert path.read_bytes() == b""
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_WRITTEN,
        cluster=Cluster.CHANGED,
        message="changes written",
        terminal=False,
    )


def test_writer_generic_skipped_hint_is_not_policy_labeled(tmp_path: Path) -> None:
    """A completed non-insert/replace skip should receive the generic skipped hint."""
    ctx: ProcessingContext = _make_writer_context(
        tmp_path / "skipped.py",
        updated_lines=[],
        plan_status=PlanStatus.REMOVED,
    )
    ctx.status.write = WriteStatus.SKIPPED

    WriterStep().hint(ctx)

    _assert_hint(
        ctx,
        code=KnownCode.WRITE_SKIPPED,
        cluster=Cluster.SKIPPED,
        message="write skipped",
        terminal=False,
    )


def test_writer_write_failure_sets_failed_status_and_preserves_original_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Atomic write failure should report FAILED and avoid truncating the target file."""
    path: Path = tmp_path / "target.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )

    def fail_write(**kwargs: object) -> NoReturn:
        raise OSError("controlled write failure")

    monkeypatch.setattr("topmark.pipeline.steps.writer._write_encoded_lines", fail_write)

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.FAILED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert not list(tmp_path.glob(".target.py.topmark.tmp-*"))
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == "Atomic write failed: controlled write failure"
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_FAILED,
        cluster=Cluster.ERROR,
        message="write failed",
        terminal=True,
    )


def test_writer_atomic_cleanup_failure_preserves_primary_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A secondary temp cleanup error should not mask the primary write failure."""
    path: Path = tmp_path / "cleanup.py"
    path.write_text("original\n", encoding="utf-8")
    expected_tmp: Path = tmp_path / f".cleanup.py.topmark.tmp-{os.getpid()}-fixed"
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )
    original_unlink = type(tmp_path).unlink

    def fixed_token_hex(nbytes: int | None = None) -> str:
        return "fixed"

    def fail_write(**kwargs: object) -> NoReturn:
        raise OSError("controlled primary failure")

    def fail_temp_cleanup(self: Path, *, missing_ok: bool = False) -> None:
        if self == expected_tmp:
            raise OSError("controlled cleanup failure")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr("topmark.pipeline.steps.writer.secrets.token_hex", fixed_token_hex)
    monkeypatch.setattr("topmark.pipeline.steps.writer._write_encoded_lines", fail_write)
    monkeypatch.setattr("pathlib.Path.unlink", fail_temp_cleanup)

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.FAILED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert expected_tmp.exists()
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == "Atomic write failed: controlled primary failure"
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_FAILED,
        cluster=Cluster.ERROR,
        message="write failed",
        terminal=True,
    )


def test_writer_inplace_failure_sets_failed_status_and_exact_diagnostic(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """In-place sink failures should complete as FAILED without a pending halt."""
    path: Path = tmp_path / "inplace_failure.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        file_write_strategy=FileWriteStrategy.INPLACE,
    )

    def fail_write(**kwargs: object) -> NoReturn:
        raise OSError("controlled in-place failure")

    monkeypatch.setattr("topmark.pipeline.steps.writer._write_encoded_lines", fail_write)

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.FAILED
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == "In-place write failed: controlled in-place failure"
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_FAILED,
        cluster=Cluster.ERROR,
        message="write failed",
        terminal=True,
    )


def test_writer_atomic_apply_streams_updated_content(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Atomic file writes should consume UpdatedContent without materializing it first."""
    path: Path = tmp_path / "atomic_lazy.py"
    path.write_text("original\n", encoding="utf-8")
    _forbid_updated_materialization(monkeypatch)
    content: UpdatedContent = compose_updated_content(["updated\n"], ["body\n"])
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=content,
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
        file_write_strategy=FileWriteStrategy.ATOMIC,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "updated\nbody\n"


def test_writer_inplace_apply_streams_updated_content(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """In-place file writes should consume UpdatedContent without materializing it first."""
    path: Path = tmp_path / "inplace_lazy.py"
    path.write_text("original\n", encoding="utf-8")
    _forbid_updated_materialization(monkeypatch)
    content: UpdatedContent = compose_updated_content(["updated\n"], ["body\n"])
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=content,
        apply_changes=True,
        plan_status=PlanStatus.REPLACED,
        file_write_strategy=FileWriteStrategy.INPLACE,
    )

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.WRITTEN
    assert path.read_text(encoding="utf-8") == "updated\nbody\n"


def test_writer_stdout_preview_streams_updated_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    """STDOUT writes should consume UpdatedContent without materializing it first."""
    path: Path = tmp_path / "stdout_lazy.py"
    path.write_text("original\n", encoding="utf-8")
    _forbid_updated_materialization(monkeypatch)
    content: UpdatedContent = compose_updated_content(["updated\n"], ["body\n"])
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=content,
        apply_changes=False,
        plan_status=PlanStatus.PREVIEWED,
        output_target=OutputTarget.STDOUT,
    )

    ctx = run_writer(ctx)

    captured: CaptureResult[str] = capsys.readouterr()
    assert ctx.status.write is WriteStatus.WRITTEN
    assert captured.out == "updated\nbody\n"
    assert path.read_text(encoding="utf-8") == "original\n"


def test_writer_stdout_preview_failure_sets_failed_status(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """STDOUT write failures should set FAILED and record a diagnostic."""
    path: Path = tmp_path / "stdout_failure.py"
    path.write_text("original\n", encoding="utf-8")
    ctx: ProcessingContext = _make_writer_context(
        path,
        updated_lines=["updated\n"],
        apply_changes=False,
        plan_status=PlanStatus.PREVIEWED,
        output_target=OutputTarget.STDOUT,
    )

    class FailingStdout:
        """Minimal stdout replacement that fails on writes."""

        def write(self, text: str) -> int:
            """Raise an output failure for any attempted write."""
            raise OSError("stdout unavailable")

    monkeypatch.setattr("topmark.pipeline.steps.writer.sys.stdout", FailingStdout())

    ctx = run_writer(ctx)

    assert ctx.status.write is WriteStatus.FAILED
    assert path.read_text(encoding="utf-8") == "original\n"
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level is DiagnosticLevel.ERROR
    assert ctx.diagnostics.items[0].message == "Stdout write failed: stdout unavailable"
    assert ctx.halt_state is None
    _assert_hint(
        ctx,
        code=KnownCode.WRITE_FAILED,
        cluster=Cluster.ERROR,
        message="write failed",
        terminal=True,
    )
