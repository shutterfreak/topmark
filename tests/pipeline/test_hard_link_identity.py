# topmark:header:start
#
#   project      : TopMark
#   file         : test_hard_link_identity.py
#   file_relpath : tests/pipeline/test_hard_link_identity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Regression tests for hard-link filesystem identity handling."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.helpers.config import make_frozen_config
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.pipelines import select_pipeline
from topmark.pipeline.status import FsStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.engine import PipelineExecution
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.pipelines import PipelineSelection


def _link_or_skip(source: Path, target: Path) -> None:
    """Create a hard link or skip when the current filesystem forbids it."""
    try:
        os.link(source, target)
    except OSError as exc:
        pytest.skip(f"hard links are not supported in this test environment: {exc}")


def _run_check(paths: list[Path], config: FrozenConfig) -> list[ProcessingContext]:
    """Run the check pipeline for `paths` and return per-file contexts."""
    pipeline: PipelineSelection = select_pipeline(
        "check",
        apply=False,
        diff=False,
    )
    run_options: RunOptions = RunOptions.from_pipeline_selection(
        selection=pipeline,
    )
    pipeline_run: PipelineExecution = run_steps_for_files(
        run_options=run_options,
        config=config,
        path_configs=None,
        pipeline=pipeline,
        file_list=paths,
    )
    assert pipeline_run.exit_code is None
    return pipeline_run.contexts


def test_hard_link_pair_blocks_all_selected_paths(tmp_path: Path) -> None:
    """A hard-link pair is blocked symmetrically with no winner path."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    _link_or_skip(first, second)

    results: list[ProcessingContext] = _run_check(
        [first, second],
        make_frozen_config(field_values={"project": "HardLinkTest"}),
    )

    assert [result.path for result in results] == [first, second]
    assert [result.status.fs for result in results] == [
        FsStatus.HARD_LINK_DUPLICATE,
        FsStatus.HARD_LINK_DUPLICATE,
    ]
    for result in results:
        assert result.is_halted
        hint: Hint = result.diagnostic_hints.items[0]
        assert hint is not None
        assert hint.code == KnownCode.FS_HARD_LINK_DUPLICATE.value
        assert hint.cluster == Cluster.BLOCKED_POLICY.value
        assert hint.terminal is True


def test_hard_link_triplet_blocks_all_selected_paths(tmp_path: Path) -> None:
    """A hard-link triplet blocks every selected path in the identity group."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    third: Path = tmp_path / "c.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    _link_or_skip(first, second)
    _link_or_skip(first, third)

    results: list[ProcessingContext] = _run_check(
        [first, second, third],
        make_frozen_config(field_values={"project": "HardLinkTest"}),
    )

    assert len(results) == 3
    assert {result.status.fs for result in results} == {FsStatus.HARD_LINK_DUPLICATE}


def test_hard_link_blocks_do_not_stop_unrelated_files(tmp_path: Path) -> None:
    """Unrelated selected files continue through the normal pipeline."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    normal: Path = tmp_path / "normal.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    normal.write_text("print('normal')\n", encoding="utf-8")
    _link_or_skip(first, second)

    results: list[ProcessingContext] = _run_check(
        [first, normal, second],
        make_frozen_config(field_values={"project": "HardLinkTest"}),
    )

    by_path: dict[Path, ProcessingContext] = {result.path: result for result in results}
    assert by_path[first].status.fs == FsStatus.HARD_LINK_DUPLICATE
    assert by_path[second].status.fs == FsStatus.HARD_LINK_DUPLICATE
    assert by_path[normal].status.fs == FsStatus.OK
    assert by_path[normal].steps


def test_missing_path_during_hard_link_scan_is_ignored(tmp_path: Path) -> None:
    """Hard-link preflight ignores paths that cannot be statted."""
    missing: Path = tmp_path / "missing.py"
    normal: Path = tmp_path / "normal.py"
    normal.write_text("print('normal')\n", encoding="utf-8")

    results: list[ProcessingContext] = _run_check(
        [missing, normal],
        make_frozen_config(field_values={"project": "HardLinkTest"}),
    )

    by_path: dict[Path, ProcessingContext] = {result.path: result for result in results}
    assert by_path[normal].status.fs == FsStatus.OK
