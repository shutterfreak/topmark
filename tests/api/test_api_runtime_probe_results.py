# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_runtime_probe_results.py
#   file_relpath : tests/api/test_api_runtime_probe_results.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Runtime tests for durable probe-result orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.api.runtime import run_probe_pipeline_results
from topmark.core.exit_codes import ExitCode
from topmark.pipeline.pipelines import select_pipeline
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import ResolveStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.api.runtime import ApiPipelineResultRun
    from topmark.pipeline.pipelines import PipelineSelection
    from topmark.pipeline.result import ProcessingResult


def test_run_probe_pipeline_results_returns_durable_results_for_real_files(
    tmp_path: Path,
) -> None:
    """Probe runtime reduces real file contexts directly to durable results."""
    target: Path = tmp_path / "sample.py"
    target.write_text("print('hello')\n", encoding="utf-8")
    pipeline: PipelineSelection = select_pipeline("probe", apply=False, diff=False)
    run_options: RunOptions = RunOptions.from_pipeline_selection(
        selection=pipeline,
        prune_views=True,
    )

    result: ApiPipelineResultRun = run_probe_pipeline_results(
        pipeline=pipeline,
        paths=[target],
        run_options=run_options,
        base_config=None,
        include_file_types=["python"],
    )

    assert result.file_list == [target]
    assert result.exit_code is None
    assert len(result.results) == 1
    assert result.results[0].probe is not None
    assert result.results[0].probe.status == "resolved"
    assert result.results[0].execution_mode.pipeline_kind == "probe"


def test_run_probe_pipeline_results_preserves_missing_input_precedence(
    tmp_path: Path,
) -> None:
    """Missing explicit inputs remain durable probe results and hard failures."""
    missing: Path = tmp_path / "missing.py"
    pipeline: PipelineSelection = select_pipeline("probe", apply=False, diff=False)
    run_options: RunOptions = RunOptions.from_pipeline_selection(selection=pipeline)

    result: ApiPipelineResultRun = run_probe_pipeline_results(
        pipeline=pipeline,
        paths=[missing],
        run_options=run_options,
        base_config=None,
    )

    assert result.file_list == []
    assert result.exit_code == ExitCode.FILE_NOT_FOUND
    assert len(result.results) == 1
    assert result.results[0].path == missing
    assert result.results[0].probe is None
    assert result.results[0].status.fs == FsStatus.NOT_FOUND


def test_run_probe_pipeline_results_preserves_filtered_explicit_inputs(
    tmp_path: Path,
) -> None:
    """Explicit probe inputs excluded by file-type filters get durable results.

    This validates the runtime adapter directly, not only the public `api.probe()`
    DTO finalizer. Filtered explicit paths should remain visible as synthetic
    durable probe results even though no real probe pipeline context is executed
    for the excluded file.
    """
    python_file: Path = tmp_path / "sample.py"
    python_file.write_text("print('hello')\n", encoding="utf-8")
    toml_file: Path = tmp_path / "sample.toml"
    toml_file.write_text("[test]\nfoo = 'bar'\n", encoding="utf-8")

    pipeline: PipelineSelection = select_pipeline("probe", apply=False, diff=False)
    run_options: RunOptions = RunOptions.from_pipeline_selection(pipeline)

    result: ApiPipelineResultRun = run_probe_pipeline_results(
        pipeline=pipeline,
        paths=[python_file, toml_file],
        run_options=run_options,
        base_config=None,
        include_file_types=["python"],
    )

    assert result.file_list == [python_file]
    assert result.exit_code is None
    assert len(result.results) == 2

    by_path: dict[Path, ProcessingResult] = {item.path: item for item in result.results}

    python_result: ProcessingResult = by_path[python_file]
    toml_result: ProcessingResult = by_path[toml_file]

    assert python_result.status.resolve == ResolveStatus.RESOLVED
    assert python_result.probe is not None
    assert python_result.probe.status == "resolved"

    assert toml_result.status.resolve == ResolveStatus.PENDING
    assert toml_result.probe is not None
    assert toml_result.probe.status == "filtered"
    assert toml_result.probe.reason == "excluded_by_file_type_filter"
    assert toml_result.probe.candidates == ()
