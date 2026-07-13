# topmark:header:start
#
#   project      : TopMark
#   file         : test_engine.py
#   file_relpath : tests/pipeline/test_engine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for pipeline-engine orchestration and failure handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from tests.helpers.config import make_frozen_config
from tests.helpers.pipeline import TEST_NOOP_PIPELINE_SELECTION
from topmark.core.exit_codes import ExitCode
from topmark.pipeline import engine
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import WriteStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step


@dataclass(frozen=True, slots=True)
class _ExitStatus:
    """Minimal status surface consumed by exit-code selection."""

    fs: FsStatus = FsStatus.PENDING
    content: ContentStatus = ContentStatus.PENDING
    write: WriteStatus = WriteStatus.PENDING


@dataclass(frozen=True, slots=True)
class _ExitResult:
    """Minimal result surface consumed by exit-code selection."""

    status: _ExitStatus


def test_iter_steps_for_files_passes_ordered_contexts_and_runtime_options_to_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine should preserve file order and runner view-pruning options."""
    first: Path = tmp_path / "first.py"
    second: Path = tmp_path / "second.py"
    first.write_text("print('first')\n", encoding="utf-8")
    second.write_text("print('second')\n", encoding="utf-8")

    calls: list[tuple[Path, Sequence[Step[ProcessingContext]], bool, bool]] = []

    def fake_run(
        ctx: ProcessingContext,
        steps: Sequence[Step[ProcessingContext]],
        *,
        prune_views: bool = True,
        keep_diff_view: bool = False,
    ) -> ProcessingContext:
        calls.append((ctx.path, steps, prune_views, keep_diff_view))
        return ctx

    monkeypatch.setattr(engine.runner, "run", fake_run)
    run_options: RunOptions = RunOptions(
        apply_changes=False,
        prune_views=False,
        emit_diff=True,
    )

    contexts: list[ProcessingContext] = list(
        engine.iter_steps_for_files(
            run_options=run_options,
            config=make_frozen_config(),
            pipeline=TEST_NOOP_PIPELINE_SELECTION,
            file_list=[first, second],
        ),
    )

    assert [ctx.path for ctx in contexts] == [first, second]
    assert [path for path, _, _, _ in calls] == [first, second]
    assert all(steps is TEST_NOOP_PIPELINE_SELECTION.steps for _, steps, _, _ in calls)
    assert [(prune, keep_diff) for _, _, prune, keep_diff in calls] == [
        (False, True),
        (False, True),
    ]


def test_iter_steps_for_files_preserves_first_known_error_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handled failures should skip their files without stopping the batch."""
    denied: Path = tmp_path / "denied.py"
    undecodable: Path = tmp_path / "undecodable.py"
    present: Path = tmp_path / "present.py"
    for path in (denied, undecodable, present):
        path.write_text("print('test')\n", encoding="utf-8")

    attempted_paths: list[Path] = []

    def fake_run(
        ctx: ProcessingContext,
        steps: Sequence[Step[ProcessingContext]],
        *,
        prune_views: bool = True,
        keep_diff_view: bool = False,
    ) -> ProcessingContext:
        del steps, prune_views, keep_diff_view
        attempted_paths.append(ctx.path)
        if ctx.path == denied:
            raise PermissionError(ctx.path)
        if ctx.path == undecodable:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return ctx

    monkeypatch.setattr(engine.runner, "run", fake_run)
    state: engine.PipelineExecutionState = engine.PipelineExecutionState()

    contexts: list[ProcessingContext] = list(
        engine.iter_steps_for_files(
            run_options=RunOptions(apply_changes=False),
            config=make_frozen_config(),
            pipeline=TEST_NOOP_PIPELINE_SELECTION,
            file_list=[denied, undecodable, present],
            state=state,
        ),
    )

    assert attempted_paths == [denied, undecodable, present]
    assert [ctx.path for ctx in contexts] == [present]
    assert state.exit_code is ExitCode.PERMISSION_DENIED


def test_iter_steps_for_files_maps_unexpected_failure_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpected per-file failure should be isolated as a pipeline error."""
    broken: Path = tmp_path / "broken.py"
    present: Path = tmp_path / "present.py"
    broken.write_text("print('broken')\n", encoding="utf-8")
    present.write_text("print('present')\n", encoding="utf-8")

    def fake_run(
        ctx: ProcessingContext,
        steps: Sequence[Step[ProcessingContext]],
        *,
        prune_views: bool = True,
        keep_diff_view: bool = False,
    ) -> ProcessingContext:
        del steps, prune_views, keep_diff_view
        if ctx.path == broken:
            raise RuntimeError("runner failed")
        return ctx

    monkeypatch.setattr(engine.runner, "run", fake_run)
    state: engine.PipelineExecutionState = engine.PipelineExecutionState()

    contexts: list[ProcessingContext] = list(
        engine.iter_steps_for_files(
            run_options=RunOptions(apply_changes=False),
            config=make_frozen_config(),
            pipeline=TEST_NOOP_PIPELINE_SELECTION,
            file_list=[broken, present],
            state=state,
        ),
    )

    assert [ctx.path for ctx in contexts] == [present]
    assert state.exit_code is ExitCode.PIPELINE_ERROR


def test_run_steps_for_files_maps_directory_error_and_materializes_later_contexts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The batch boundary should treat a directory as missing and continue."""
    directory: Path = tmp_path / "directory"
    present: Path = tmp_path / "present.py"
    directory.mkdir()
    present.write_text("print('present')\n", encoding="utf-8")

    def fake_run(
        ctx: ProcessingContext,
        steps: Sequence[Step[ProcessingContext]],
        *,
        prune_views: bool = True,
        keep_diff_view: bool = False,
    ) -> ProcessingContext:
        del steps, prune_views, keep_diff_view
        if ctx.path == directory:
            raise IsADirectoryError(ctx.path)
        return ctx

    monkeypatch.setattr(engine.runner, "run", fake_run)

    execution: engine.PipelineExecution = engine.run_steps_for_files(
        run_options=RunOptions(apply_changes=False),
        config=make_frozen_config(),
        pipeline=TEST_NOOP_PIPELINE_SELECTION,
        file_list=[directory, present],
    )

    assert [ctx.path for ctx in execution.contexts] == [present]
    assert execution.exit_code is ExitCode.FILE_NOT_FOUND


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (_ExitStatus(fs=FsStatus.UNICODE_DECODE_ERROR), ExitCode.ENCODING_ERROR),
        (_ExitStatus(write=WriteStatus.FAILED), ExitCode.IO_ERROR),
        (_ExitStatus(fs=FsStatus.UNREADABLE), ExitCode.IO_ERROR),
        (_ExitStatus(content=ContentStatus.UNREADABLE), ExitCode.IO_ERROR),
        (_ExitStatus(), None),
    ],
)
def test_exit_code_from_pipeline_results_maps_documented_statuses(
    status: _ExitStatus,
    expected: ExitCode | None,
) -> None:
    """Status reduction should map documented errors without presentation state."""
    assert engine.exit_code_from_pipeline_results([_ExitResult(status)]) is expected


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (
            [
                _ExitStatus(write=WriteStatus.FAILED),
                _ExitStatus(fs=FsStatus.UNICODE_DECODE_ERROR),
            ],
            ExitCode.ENCODING_ERROR,
        ),
        (
            [
                _ExitStatus(fs=FsStatus.UNICODE_DECODE_ERROR),
                _ExitStatus(fs=FsStatus.NO_READ_PERMISSION),
            ],
            ExitCode.PERMISSION_DENIED,
        ),
        (
            [
                _ExitStatus(fs=FsStatus.NO_WRITE_PERMISSION),
                _ExitStatus(fs=FsStatus.NOT_FOUND),
            ],
            ExitCode.FILE_NOT_FOUND,
        ),
    ],
)
def test_exit_code_from_pipeline_results_preserves_documented_priority(
    statuses: list[_ExitStatus],
    expected: ExitCode,
) -> None:
    """Result ordering should not override the documented error priority."""
    results: list[_ExitResult] = [_ExitResult(status) for status in statuses]

    assert engine.exit_code_from_pipeline_results(results) is expected
