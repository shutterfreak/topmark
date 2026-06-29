# topmark:header:start
#
#   project      : TopMark
#   file         : test_perf_baseline_tooling.py
#   file_relpath : tests/dev_validation/test_perf_baseline_tooling.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation tests for benchmark-suite configuration.

These tests verify that the repository-scale benchmark suite remains
registered with the expected workload and pipeline modes without
executing the benchmarks themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from tools.perf.pipeline_memory_baseline import RunMeasurement
    from tools.perf.pipeline_memory_baseline import Scenario


def _repository_scenario(
    root: Path,
) -> Scenario:
    """Return the generated repository-scale benchmark scenario."""
    from tools.perf import pipeline_memory_baseline as baseline

    scenarios: list[Scenario] = baseline.build_scenarios(root, include_large=False)
    return next(scenario for scenario in scenarios if scenario.name == "repo_many_small_mixed")


@pytest.mark.dev_validation
def test_repository_perf_suite_uses_pruned_pipeline_modes() -> None:
    """Repository perf suite compares only pruned pipeline modes."""
    from tools.perf import pipeline_memory_baseline as baseline

    assert baseline.SUITE_MODES["repository"] == (
        "check_pruned",
        "check_diff_pruned",
        "strip_pruned",
        "strip_diff_pruned",
    )


@pytest.mark.dev_validation
def test_repository_perf_suite_uses_many_file_scenario() -> None:
    """Repository perf suite targets the synthetic many-file workload."""
    from tools.perf import pipeline_memory_baseline as baseline

    assert baseline.SUITE_SCENARIOS["repository"] == baseline.REPOSITORY_SCENARIOS
    assert baseline.REPOSITORY_SCENARIOS == ("repo_many_small_mixed",)
    assert baseline.REPOSITORY_FILE_COUNT > 1


@pytest.mark.dev_validation
def test_repository_perf_scenario_generates_expected_file_count(
    tmp_path: Path,
) -> None:
    """Repository scenario generation creates a deterministic many-file tree."""
    from tools.perf import pipeline_memory_baseline as baseline

    scenario: Scenario = _repository_scenario(tmp_path)

    assert scenario.path.is_dir()
    assert scenario.file_count == baseline.REPOSITORY_FILE_COUNT
    assert scenario.size_bytes > 0

    files: list[Path] = sorted(scenario.path.rglob("*.py"))
    assert len(files) == baseline.REPOSITORY_FILE_COUNT


@pytest.mark.dev_validation
def test_measurement_from_mapping_accepts_repository_fields() -> None:
    """Measurement JSON rehydration preserves repository aggregate fields."""
    from tools.perf import pipeline_memory_baseline as baseline

    measurement: RunMeasurement = baseline.measurement_from_mapping(
        {
            "scenario": "repo_many_small_mixed",
            "mode": "check_diff_pruned",
            "file_size_bytes": 12345,
            "elapsed_ns": 67890,
            "peak_tracemalloc_bytes": 111,
            "final_tracemalloc_bytes": 22,
            "start_rss_bytes": None,
            "end_rss_bytes": None,
            "max_observed_rss_bytes": None,
            "stdout_bytes": 0,
            "input_file_count": 250,
            "result_count": 250,
            "result_diff_bytes": 4096,
            "exit_code": None,
            "status": {},
            "views_before_prune": {
                "image_lines": 0,
                "header_lines": 0,
                "header_block_bytes": 0,
                "render_lines": 0,
                "render_block_bytes": 0,
                "updated_lines": 0,
                "diff_bytes": 0,
                "has_build_view": False,
            },
            "views_after_prune": {
                "image_lines": 0,
                "header_lines": 0,
                "header_block_bytes": 0,
                "render_lines": 0,
                "render_block_bytes": 0,
                "updated_lines": 0,
                "diff_bytes": 0,
                "has_build_view": False,
            },
            "steps": [],
        }
    )

    assert measurement.input_file_count == 250
    assert measurement.result_count == 250
    assert measurement.result_diff_bytes == 4096
    assert measurement.exit_code is None
