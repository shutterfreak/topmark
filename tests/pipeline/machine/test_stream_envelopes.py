# topmark:header:start
#
#   project      : TopMark
#   file         : test_stream_envelopes.py
#   file_relpath : tests/pipeline/machine/test_stream_envelopes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Defensive unit tests for pipeline machine-readable stream envelopes.

These tests exercise stream envelope guards that are intentionally unreachable
through the public CLI. They verify that the stream envelope layer rejects
malformed durable-result event lifecycles with consistent `ValueError` diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.machine.payloads import build_meta_payload
from topmark.pipeline.machine.envelopes import build_probe_results_stream_json_envelope
from topmark.pipeline.machine.envelopes import build_processing_results_stream_json_envelope
from topmark.pipeline.machine.envelopes import iter_probe_results_stream_ndjson_records
from topmark.pipeline.machine.envelopes import iter_processing_results_stream_ndjson_records
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import MachineRunCompletedEvent
from topmark.pipeline.machine.streaming import MachineRunStartedEvent
from topmark.pipeline.result import ProcessingResult
from topmark.toml.resolution import ResolvedTopmarkTomlSources

if TYPE_CHECKING:
    from pathlib import Path
    from typing import TypeAlias

    from topmark.config.model import FrozenConfig
    from topmark.core.machine.schemas import MetaPayload
    from topmark.pipeline.context.model import ProcessingContext

    SerializerContext: TypeAlias = tuple[
        MetaPayload,
        FrozenConfig,
        ResolvedTopmarkTomlSources,
    ]


def _serializer_context(from_config: FrozenConfig | None = None) -> SerializerContext:
    """Build shared serializer inputs for defensive format tests.

    Args:
        from_config: Optional frozen config to use instead of default config.

    Returns:
        A tuple containing the meta object, frozen config, and resolved TOML sources.
    """
    config: FrozenConfig = (
        from_config if from_config is not None else mutable_config_from_defaults().freeze()
    )
    return (
        build_meta_payload(),
        config,
        ResolvedTopmarkTomlSources(
            sources=[],
            writer_options=None,
            strict=False,
        ),
    )


def _processing_result(tmp_path: Path, config: FrozenConfig) -> ProcessingResult:
    """Build a single durable processing result for stream-adapter tests.

    Args:
        tmp_path: Temporary directory used for the synthetic file path.
        config: Frozen config used to build the pipeline context.

    Returns:
        A durable processing result for the synthetic path.
    """
    context: ProcessingContext = make_pipeline_context(
        path=tmp_path / "example.py",
        cfg=config,
    )
    return ProcessingResult.from_context(context)


def test_processing_json_stream_collector_rejects_missing_start() -> None:
    """Processing JSON rejects completion before the run starts."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing JSON run-completed event appeared before run-start",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunCompletedEvent(
                    command="check",
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_duplicate_start() -> None:
    """Processing JSON rejects duplicate run-start events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing JSON stream contains more than one run-start event",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="check",
                    selected_count=0,
                    paths=(),
                ),
                MachineRunStartedEvent(
                    command="check",
                    selected_count=0,
                    paths=(),
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_wrong_command() -> None:
    """Processing JSON rejects probe events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing JSON stream contains an event for a different command",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=0,
                    paths=(),
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_missing_completion() -> None:
    """Processing JSON requires a completion event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing JSON stream is missing a run-completed event",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="check",
                    selected_count=0,
                    paths=(),
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_file_before_start(
    tmp_path: Path,
) -> None:
    """Processing JSON rejects file-result events before run-start."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Processing JSON file-result event appeared before run-start",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineProcessingResultEvent(
                    command="check",
                    index=0,
                    result=result,
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_file_after_completion(
    tmp_path: Path,
) -> None:
    """Processing JSON rejects file-result events after completion."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Processing JSON file-result event appeared after run-completed",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="check",
                    selected_count=1,
                    paths=(result.path,),
                ),
                MachineRunCompletedEvent(
                    command="check",
                ),
                MachineProcessingResultEvent(
                    command="check",
                    index=0,
                    result=result,
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_out_of_order_file_index(
    tmp_path: Path,
) -> None:
    """Processing JSON rejects non-contiguous file-result indexes."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Expected processing JSON file-result index 0, got 1",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="check",
                    selected_count=1,
                    paths=(result.path,),
                ),
                MachineProcessingResultEvent(
                    command="check",
                    index=1,
                    result=result,
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_duplicate_completion() -> None:
    """Processing JSON rejects duplicate run-completed events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing JSON stream contains more than one run-completed event",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="check",
                    selected_count=0,
                    paths=(),
                ),
                MachineRunCompletedEvent(
                    command="check",
                ),
                MachineRunCompletedEvent(
                    command="check",
                ),
            ),
            summary_mode=False,
        )


def test_processing_json_stream_collector_rejects_empty_stream() -> None:
    """Processing JSON requires a run-start event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing JSON stream is missing a run-start event",
    ):
        build_processing_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(),
            summary_mode=False,
        )


def test_probe_json_stream_collector_rejects_missing_start() -> None:
    """Probe JSON rejects completion before the run starts."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe JSON run-completed event appeared before run-start",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunCompletedEvent(
                    command="probe",
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_wrong_command() -> None:
    """Probe JSON rejects check/strip events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe JSON stream contains an event for a different command",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="check",
                    selected_count=0,
                    paths=(),
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_missing_completion() -> None:
    """Probe JSON requires a completion event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe JSON stream is missing a run-completed event",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=0,
                    paths=(),
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_duplicate_start() -> None:
    """Probe JSON rejects duplicate run-start events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe JSON stream contains more than one run-start event",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=0,
                    paths=(),
                ),
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=0,
                    paths=(),
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_file_before_start(
    tmp_path: Path,
) -> None:
    """Probe JSON rejects file-result events before run-start."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Probe JSON file-result event appeared before run-start",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineProcessingResultEvent(
                    command="probe",
                    index=0,
                    result=result,
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_file_after_completion(
    tmp_path: Path,
) -> None:
    """Probe JSON rejects file-result events after completion."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Probe JSON file-result event appeared after run-completed",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=1,
                    paths=(result.path,),
                ),
                MachineRunCompletedEvent(
                    command="probe",
                ),
                MachineProcessingResultEvent(
                    command="probe",
                    index=0,
                    result=result,
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_out_of_order_file_index(
    tmp_path: Path,
) -> None:
    """Probe JSON rejects non-contiguous file-result indexes."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Expected probe JSON file-result index 0, got 1",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=1,
                    paths=(result.path,),
                ),
                MachineProcessingResultEvent(
                    command="probe",
                    index=1,
                    result=result,
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_duplicate_completion() -> None:
    """Probe JSON rejects duplicate run-completed events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe JSON stream contains more than one run-completed event",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(
                MachineRunStartedEvent(
                    command="probe",
                    selected_count=0,
                    paths=(),
                ),
                MachineRunCompletedEvent(
                    command="probe",
                ),
                MachineRunCompletedEvent(
                    command="probe",
                ),
            ),
        )


def test_probe_json_stream_collector_rejects_empty_stream() -> None:
    """Probe JSON requires a run-start event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe JSON stream is missing a run-start event",
    ):
        build_probe_results_stream_json_envelope(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            events=(),
        )


def test_processing_ndjson_stream_adapter_rejects_missing_start() -> None:
    """Processing stream NDJSON rejects file events before the run starts."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing NDJSON run-completed event appeared before run-start",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunCompletedEvent(
                        command="check",
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_duplicate_start() -> None:
    """Processing stream NDJSON rejects duplicate run-start events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing NDJSON stream contains more than one run-start event",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=0,
                        paths=(),
                    ),
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=0,
                        paths=(),
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_wrong_command() -> None:
    """Processing stream NDJSON rejects probe events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing NDJSON stream contains an event for a different command",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=0,
                        paths=(),
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_missing_completion() -> None:
    """Processing stream NDJSON requires a completion event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing NDJSON stream is missing a run-completed event",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=0,
                        paths=(),
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_file_before_start(
    tmp_path: Path,
) -> None:
    """Processing stream NDJSON rejects file-result events before run-start."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Processing NDJSON file-result event appeared before run-start",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineProcessingResultEvent(
                        command="check",
                        index=0,
                        result=result,
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_file_after_completion(
    tmp_path: Path,
) -> None:
    """Processing stream NDJSON rejects file-result events after completion."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Processing NDJSON file-result event appeared after run-completed",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=1,
                        paths=(result.path,),
                    ),
                    MachineRunCompletedEvent(
                        command="check",
                    ),
                    MachineProcessingResultEvent(
                        command="check",
                        index=0,
                        result=result,
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_out_of_order_file_index(
    tmp_path: Path,
) -> None:
    """Processing stream NDJSON rejects non-contiguous file-result indexes."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Expected processing NDJSON file-result index 0, got 1",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=1,
                        paths=(result.path,),
                    ),
                    MachineProcessingResultEvent(
                        command="check",
                        index=1,
                        result=result,
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_duplicate_completion() -> None:
    """Processing stream NDJSON rejects duplicate run-completed events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing NDJSON stream contains more than one run-completed event",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=0,
                        paths=(),
                    ),
                    MachineRunCompletedEvent(
                        command="check",
                    ),
                    MachineRunCompletedEvent(
                        command="check",
                    ),
                ),
                summary_mode=False,
            )
        )


def test_processing_ndjson_stream_adapter_rejects_empty_stream() -> None:
    """Processing stream NDJSON requires a run-start event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Processing NDJSON stream is missing a run-start event",
    ):
        list(
            iter_processing_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(),
                summary_mode=False,
            )
        )


def test_probe_ndjson_stream_adapter_rejects_missing_start() -> None:
    """Probe stream NDJSON rejects completion before the run starts."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe NDJSON run-completed event appeared before run-start",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunCompletedEvent(
                        command="probe",
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_wrong_command() -> None:
    """Probe stream NDJSON rejects check/strip events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe NDJSON stream contains an event for a different command",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="check",
                        selected_count=0,
                        paths=(),
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_missing_completion() -> None:
    """Probe stream NDJSON requires a completion event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe NDJSON stream is missing a run-completed event",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=0,
                        paths=(),
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_duplicate_start() -> None:
    """Probe stream NDJSON rejects duplicate run-start events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe NDJSON stream contains more than one run-start event",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=0,
                        paths=(),
                    ),
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=0,
                        paths=(),
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_file_before_start(
    tmp_path: Path,
) -> None:
    """Probe stream NDJSON rejects file-result events before run-start."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Probe NDJSON file-result event appeared before run-start",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineProcessingResultEvent(
                        command="probe",
                        index=0,
                        result=result,
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_file_after_completion(
    tmp_path: Path,
) -> None:
    """Probe stream NDJSON rejects file-result events after completion."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Probe NDJSON file-result event appeared after run-completed",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=1,
                        paths=(result.path,),
                    ),
                    MachineRunCompletedEvent(
                        command="probe",
                    ),
                    MachineProcessingResultEvent(
                        command="probe",
                        index=0,
                        result=result,
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_out_of_order_file_index(
    tmp_path: Path,
) -> None:
    """Probe stream NDJSON rejects non-contiguous file-result indexes."""
    meta, config, resolved_toml_sources = _serializer_context()
    result: ProcessingResult = _processing_result(tmp_path, config)

    with pytest.raises(
        ValueError,
        match="Expected probe NDJSON file-result index 0, got 1",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=1,
                        paths=(result.path,),
                    ),
                    MachineProcessingResultEvent(
                        command="probe",
                        index=1,
                        result=result,
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_duplicate_completion() -> None:
    """Probe stream NDJSON rejects duplicate run-completed events."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe NDJSON stream contains more than one run-completed event",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(
                    MachineRunStartedEvent(
                        command="probe",
                        selected_count=0,
                        paths=(),
                    ),
                    MachineRunCompletedEvent(
                        command="probe",
                    ),
                    MachineRunCompletedEvent(
                        command="probe",
                    ),
                ),
            )
        )


def test_probe_ndjson_stream_adapter_rejects_empty_stream() -> None:
    """Probe stream NDJSON requires a run-start event."""
    meta, config, resolved_toml_sources = _serializer_context()

    with pytest.raises(
        ValueError,
        match="Probe NDJSON stream is missing a run-start event",
    ):
        list(
            iter_probe_results_stream_ndjson_records(
                meta=meta,
                config=config,
                resolved_toml=resolved_toml_sources,
                events=(),
            )
        )
