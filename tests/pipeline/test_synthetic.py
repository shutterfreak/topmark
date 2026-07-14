# topmark:header:start
#
#   project      : TopMark
#   file         : test_synthetic.py
#   file_relpath : tests/pipeline/test_synthetic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for resolver-level synthetic pipeline contexts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.pipeline.context.model import HaltState
from topmark.pipeline.context.status import ProcessingStatus
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import FsStatus
from topmark.pipeline.synthetic import build_filtered_probe_contexts
from topmark.pipeline.synthetic import build_missing_file_contexts
from topmark.pipeline.synthetic import map_selection_reason_to_probe_reason
from topmark.resolution.discovery import FileSelectionProbeResult
from topmark.resolution.discovery import FileSelectionReason
from topmark.resolution.discovery import FileSelectionStatus
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def test_missing_file_contexts_preserve_inputs_and_build_isolated_terminal_state(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Each missing path should become an independent terminal filesystem context."""
    paths: list[Path] = [tmp_path / "first.py", tmp_path / "second.py"]
    run_options = RunOptions(pipeline_kind="check", apply_changes=False)

    contexts: list[ProcessingContext] = build_missing_file_contexts(
        paths=paths,
        config=default_frozen_config,
        run_options=run_options,
    )

    assert [context.path for context in contexts] == paths
    assert all(context.config is default_frozen_config for context in contexts)
    assert all(context.run_options is run_options for context in contexts)
    assert all(context.status == ProcessingStatus(fs=FsStatus.NOT_FOUND) for context in contexts)
    assert all(
        context.halt_state == HaltState(reason_code="file_not_found", step_name="file_resolution")
        for context in contexts
    )
    assert all(context.resolution_probe is None for context in contexts)

    first_hint, second_hint = (tuple(context.diagnostic_hints)[0] for context in contexts)
    assert first_hint.axis == Axis.FS
    assert first_hint.code == KnownCode.FS_NOT_FOUND.value
    assert first_hint.cluster == Cluster.ERROR.value
    assert first_hint.terminal is True
    assert first_hint.message == f"No such file or directory: {paths[0]}"
    assert second_hint.message == f"No such file or directory: {paths[1]}"

    contexts[0].hint(
        axis=Axis.FS,
        code="test:additional",
        message="Additional first-context hint",
    )
    assert len(contexts[0].diagnostic_hints) == 2
    assert len(contexts[1].diagnostic_hints) == 1


@pytest.mark.parametrize(
    ("selection_reason", "probe_reason"),
    [
        (
            FileSelectionReason.EXCLUDED_BY_PATH_FILTER,
            ResolutionProbeReason.EXCLUDED_BY_PATH_FILTER,
        ),
        (
            FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER,
            ResolutionProbeReason.EXCLUDED_BY_FILE_TYPE_FILTER,
        ),
        (
            FileSelectionReason.EXCLUDED_BY_DISCOVERY_FILTER,
            ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER,
        ),
        (
            FileSelectionReason.NOT_A_FILE,
            ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER,
        ),
        (
            FileSelectionReason.NOT_FOUND,
            ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER,
        ),
        (
            FileSelectionReason.SELECTED,
            ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER,
        ),
    ],
)
def test_selection_reasons_normalize_to_the_supported_probe_vocabulary(
    selection_reason: FileSelectionReason,
    probe_reason: ResolutionProbeReason,
) -> None:
    """Discovery-only reasons should map into the stable probe reason vocabulary."""
    assert map_selection_reason_to_probe_reason(selection_reason) == probe_reason


def test_filtered_probe_contexts_skip_selected_inputs_and_build_probe_results(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Only inputs absent from the real probe pipeline should get synthetic contexts."""
    first_filtered_path: Path = tmp_path / "first-filtered.py"
    selected_path: Path = tmp_path / "selected.py"
    second_filtered_path: Path = tmp_path / "second-filtered.py"
    selection_results: list[FileSelectionProbeResult] = [
        FileSelectionProbeResult(
            path=first_filtered_path,
            status=FileSelectionStatus.FILTERED,
            reason=FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER,
        ),
        FileSelectionProbeResult(
            path=selected_path,
            status=FileSelectionStatus.SELECTED,
            reason=FileSelectionReason.SELECTED,
        ),
        FileSelectionProbeResult(
            path=second_filtered_path,
            status=FileSelectionStatus.FILTERED,
            reason=FileSelectionReason.EXCLUDED_BY_PATH_FILTER,
        ),
    ]
    run_options = RunOptions(pipeline_kind="probe", apply_changes=False)

    contexts: list[ProcessingContext] = build_filtered_probe_contexts(
        selection_results=selection_results,
        config=default_frozen_config,
        run_options=run_options,
    )

    assert [context.path for context in contexts] == [
        first_filtered_path,
        second_filtered_path,
    ]
    assert all(context.config is default_frozen_config for context in contexts)
    assert all(context.run_options is run_options for context in contexts)

    expected_reasons: tuple[ResolutionProbeReason, ...] = (
        ResolutionProbeReason.EXCLUDED_BY_FILE_TYPE_FILTER,
        ResolutionProbeReason.EXCLUDED_BY_PATH_FILTER,
    )
    for context, expected_reason in zip(contexts, expected_reasons, strict=True):
        assert context.status == ProcessingStatus()
        assert context.halt_state is None
        assert len(context.diagnostic_hints) == 0
        assert context.resolution_probe is not None
        assert context.resolution_probe.path == context.path
        assert context.resolution_probe.status == ResolutionProbeStatus.FILTERED
        assert context.resolution_probe.reason == expected_reason
        assert context.resolution_probe.candidates == ()
        assert context.resolution_probe.selected_file_type is None
        assert context.resolution_probe.selected_processor is None
