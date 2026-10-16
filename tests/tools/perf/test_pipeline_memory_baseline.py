# topmark:header:start
#
#   project      : TopMark
#   file         : test_pipeline_memory_baseline.py
#   file_relpath : tests/tools/perf/test_pipeline_memory_baseline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation tests for benchmark-suite configuration.

These tests verify that the repository-scale benchmark suite remains
registered with the expected workload and pipeline modes without
executing the benchmarks themselves.
"""

# Allow testing private helper functions directly without inline comment overhead.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path

    from tools.perf.pipeline_memory_baseline import Mode
    from tools.perf.pipeline_memory_baseline import RunDestination
    from tools.perf.pipeline_memory_baseline import RunMeasurement
    from tools.perf.pipeline_memory_baseline import Scenario


def _repository_scenario(
    root: Path,
) -> Scenario:
    """Return the generated repository-scale benchmark scenario."""
    from tools.perf import pipeline_memory_baseline as baseline

    scenarios: list[Scenario] = baseline.build_scenarios(root, include_large=False)
    return next(scenario for scenario in scenarios if scenario.name == "repo_many_small_mixed")


def test_repository_perf_suite_uses_pruned_pipeline_modes() -> None:
    """Repository perf suite compares only pruned pipeline modes."""
    from tools.perf import pipeline_memory_baseline as baseline

    assert baseline.SUITE_MODES["repository"] == (
        "check_pruned",
        "check_diff_pruned",
        "strip_pruned",
        "strip_diff_pruned",
    )


def test_repository_perf_suite_uses_many_file_scenario() -> None:
    """Repository perf suite targets the synthetic many-file workload."""
    from tools.perf import pipeline_memory_baseline as baseline

    assert baseline.SUITE_SCENARIOS["repository"] == baseline.REPOSITORY_SCENARIOS
    assert baseline.REPOSITORY_SCENARIOS == ("repo_many_small_mixed",)
    assert baseline.REPOSITORY_FILE_COUNT > 1


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "n/a"),
        (12, "12 B"),
        (1024, "1.0 KiB"),
        (1126, "1.1 KiB"),
        (1_048_576, "1.0 MiB"),
        (1_677_722, "1.6 MiB"),
    ],
)
def test_format_bytes_uses_compact_units(
    value: int | None,
    expected: str,
) -> None:
    """Summary formatting makes absent and scaled byte counts readable."""
    from tools.perf import pipeline_memory_baseline as baseline

    assert baseline._format_bytes(value) == expected


def test_mode_resolution_preserves_pruning_and_output_contracts() -> None:
    """Mode names map to explicit pipeline behavior without running a benchmark."""
    from tools.perf import pipeline_memory_baseline as baseline
    from topmark.config.types import OutputTarget

    check: Mode = baseline._mode_from_name("check")
    pruned_stdout: Mode = baseline._mode_from_name("check_stdout_pruned")

    assert not check.prune_views
    assert check.output_target is OutputTarget.FILE
    assert pruned_stdout.prune_views
    assert pruned_stdout.output_target is OutputTarget.STDOUT
    with pytest.raises(ValueError, match="Unknown mode"):
        baseline._mode_from_name("unknown")


def test_resolve_destination_rejects_conflicting_or_existing_outputs(
    tmp_path: Path,
) -> None:
    """Preserved report destinations require an explicit overwrite choice."""
    from tools.perf import pipeline_memory_baseline as baseline

    output: Path = tmp_path / "report.json"
    args: Namespace = baseline._parse_args(
        [
            "--output",
            str(output),
        ]
    )
    destination: RunDestination = baseline._resolve_destination(args, suite=None)
    assert destination.output_file == output
    assert destination.output_dir is None

    run_dir: Path = tmp_path / "runs" / "stable"
    run_dir.mkdir(parents=True)
    args = baseline._parse_args(
        [
            "--output-dir",
            str(tmp_path / "runs"),
            "--run-id",
            "stable",
        ]
    )
    with pytest.raises(FileExistsError, match="--overwrite"):
        baseline._resolve_destination(args, suite="smoke")


def test_measurement_from_mapping_rejects_invalid_nested_payload() -> None:
    """JSON rehydration rejects malformed step objects instead of guessing."""
    from tools.perf import pipeline_memory_baseline as baseline

    with pytest.raises(TypeError, match="steps list"):
        baseline.measurement_from_mapping({"steps": "not-a-list"})
