# topmark:header:start
#
#   project      : TopMark
#   file         : envelopes.py
#   file_relpath : src/topmark/pipeline/machine/envelopes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output envelope builders for processing and probe commands.

This module composes **machine-readable output shapes** for pipeline runs
(`topmark check`, `topmark strip`, and `topmark probe`).

It is intentionally:
- console-/Click-free (no printing, no CLI concerns)
- serialization-free (no `json.dumps`)

Responsibilities:
- **JSON**: build a single top-level envelope containing `meta`, `config`,
  `config_diagnostics`, and either processing data (`results` / `summary`) or
  probe data (`probes`).
- **NDJSON**: yield a stream of per-record mappings following the project's
  NDJSON contract (Pattern A: every record includes `kind` and `meta`), starting
  with config prefix records and followed by processing records (`result` /
  `summary`) or probe records (`probe`).

Where config diagnostics are included, this module exposes the flattened
compatibility view derived from staged config-validation logs.

See Also:
- [`topmark.pipeline.machine.payloads`][topmark.pipeline.machine.payloads]:
    domain payload fragments for processing and probe runs.
- [`topmark.core.machine.envelopes`][topmark.core.machine.envelopes]:
    shared envelope/record helpers (`build_json_envelope`, `build_ndjson_record`,
    config prefix and diagnostic record generators).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.machine.envelopes import iter_config_prefix_ndjson_records
from topmark.config.machine.payloads import build_config_diagnostics_payload
from topmark.config.machine.payloads import build_config_payload
from topmark.config.machine.schemas import ConfigKey
from topmark.core.machine.envelopes import build_json_envelope
from topmark.core.machine.envelopes import build_ndjson_record
from topmark.core.machine.schemas import MachineDomain
from topmark.core.machine.schemas import MetaPayload
from topmark.diagnostic.machine.envelopes import iter_diagnostic_ndjson_records
from topmark.pipeline.machine.payloads import build_probe_result_payload
from topmark.pipeline.machine.payloads import build_processing_result_payload
from topmark.pipeline.machine.payloads import build_processing_results_summary_rows_payload
from topmark.pipeline.machine.payloads import build_standalone_processing_diff_payload
from topmark.pipeline.machine.schemas import PipelineKey
from topmark.pipeline.machine.schemas import PipelineRecordKind
from topmark.pipeline.machine.schemas import StandaloneProcessingDiffPayload
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import MachineRunCompletedEvent
from topmark.pipeline.machine.streaming import MachineRunStartedEvent

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from topmark.config.machine.schemas import ConfigDiagnosticsPayload
    from topmark.config.machine.schemas import ConfigPayload
    from topmark.config.model import FrozenConfig
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.pipeline.machine.streaming import MachineProcessingStreamEvent
    from topmark.pipeline.result import ProcessingResult
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


# ---- Stream error helpers ----


def _duplicate_start_error(label: str) -> ValueError:
    """Build an error for duplicate stream start events."""
    return ValueError(f"{label} stream contains more than one run-start event.")


def _result_before_start_error(label: str) -> ValueError:
    """Build an error for result events before stream start."""
    return ValueError(f"{label} file-result event appeared before run-start.")


def _result_after_completion_error(label: str) -> ValueError:
    """Build an error for result events after stream completion."""
    return ValueError(f"{label} file-result event appeared after run-completed.")


def _non_contiguous_result_index_error(
    *,
    label: str,
    expected_index: int,
    actual_index: int,
) -> ValueError:
    """Build an error for non-contiguous result indexes."""
    return ValueError(f"Expected {label} file-result index {expected_index}, got {actual_index}.")


def _completion_before_start_error(label: str) -> ValueError:
    """Build an error for completion events before stream start."""
    return ValueError(f"{label} run-completed event appeared before run-start.")


def _duplicate_completion_error(label: str) -> ValueError:
    """Build an error for duplicate stream completion events."""
    return ValueError(f"{label} stream contains more than one run-completed event.")


def _wrong_command_error(label: str) -> ValueError:
    """Build an error for stream events from another command."""
    return ValueError(f"{label} stream contains an event for a different command.")


def _missing_start_error(label: str) -> ValueError:
    """Build an error for streams missing their start event."""
    return ValueError(f"{label} stream is missing a run-start event.")


def _missing_completion_error(label: str) -> ValueError:
    """Build an error for streams missing their completion event."""
    return ValueError(f"{label} stream is missing a run-completed event.")


def build_probe_results_stream_json_envelope(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    events: Iterable[MachineProcessingStreamEvent],
) -> dict[str, object]:
    """Build the probe JSON envelope from durable-result stream events.

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: Effective configuration instance.
        resolved_toml: ResolvedTopmarkTomlSources.
        events: Internal machine stream events in deterministic producer order.

    Returns:
        JSON-serializable envelope mapping preserving the existing probe JSON schema.

    Raises:
        ValueError: If the stream lifecycle or command identity is invalid.
    """  # noqa: DOC503 - raises ValueError via exception factory helper
    cfg_payload: ConfigPayload = build_config_payload(
        config,
        resolved_toml=resolved_toml,
    )
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    expected_index: int = 0
    started: bool = False
    completed: bool = False
    probe_payloads: list[dict[str, object]] = []
    for event in events:
        match event:
            case MachineRunStartedEvent(command="probe"):
                if started:
                    raise _duplicate_start_error("Probe JSON")
                # `started` remains true for the rest of the stream, so every
                # later run-start is handled by the duplicate-start guard above.
                started = True
            case MachineProcessingResultEvent(command="probe"):
                if not started:
                    raise _result_before_start_error("Probe JSON")
                if completed:
                    raise _result_after_completion_error("Probe JSON")
                if event.index != expected_index:
                    raise _non_contiguous_result_index_error(
                        label="probe JSON",
                        expected_index=expected_index,
                        actual_index=event.index,
                    )
                expected_index += 1
                probe_payloads.append(build_probe_result_payload(event.result))
            case MachineRunCompletedEvent(command="probe"):
                if not started:
                    raise _completion_before_start_error("Probe JSON")
                if completed:
                    raise _duplicate_completion_error("Probe JSON")
                completed = True
            case _:
                raise _wrong_command_error("Probe JSON")

    if not started:
        raise _missing_start_error("Probe JSON")
    if not completed:
        raise _missing_completion_error("Probe JSON")

    return build_json_envelope(
        meta=meta,
        **{
            ConfigKey.CONFIG.value: cfg_payload,
            ConfigKey.CONFIG_DIAGNOSTICS.value: cfg_diag_payload,
            PipelineKey.PROBES.value: probe_payloads,
        },
    )


def iter_probe_results_stream_ndjson_records(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    events: Iterable[MachineProcessingStreamEvent],
) -> Iterator[dict[str, object]]:
    """Yield probe NDJSON records from an internal processing stream.

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: Effective configuration instance.
        resolved_toml: ResolvedTopmarkTomlSources.
        events: Internal machine stream events in deterministic producer order.

    Yields:
        Shaped NDJSON records preserving the existing probe machine schema.

    Raises:
        ValueError: If the stream contains events for another command, duplicate
            lifecycle events, missing lifecycle events, file events before start or
            after completion, or non-contiguous file-result indexes.
    """  # noqa: DOC503 - raises ValueError via exception factory helper
    cfg_payload: ConfigPayload = build_config_payload(
        config,
        resolved_toml=resolved_toml,
    )
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    yield from iter_config_prefix_ndjson_records(
        meta=meta,
        config=config,
        resolved_toml=resolved_toml,
        cfg_payload=cfg_payload,
        cfg_diag_payload=cfg_diag_payload,
    )

    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=flattened_diagnostics,
    )

    expected_index: int = 0
    started: bool = False
    completed: bool = False
    for event in events:
        match event:
            case MachineRunStartedEvent(command="probe"):
                if started:
                    raise _duplicate_start_error("Probe NDJSON")
                # `started` remains true for the rest of the stream, so every
                # later run-start is handled by the duplicate-start guard above.
                started = True
            case MachineProcessingResultEvent(command="probe"):
                if not started:
                    raise _result_before_start_error("Probe NDJSON")
                if completed:
                    raise _result_after_completion_error("Probe NDJSON")
                if event.index != expected_index:
                    raise _non_contiguous_result_index_error(
                        label="probe NDJSON",
                        expected_index=expected_index,
                        actual_index=event.index,
                    )
                expected_index += 1
                yield build_ndjson_record(
                    kind=PipelineRecordKind.PROBE,
                    meta=meta,
                    payload=build_probe_result_payload(event.result),
                )
            case MachineRunCompletedEvent(command="probe"):
                if not started:
                    raise _completion_before_start_error("Probe NDJSON")
                if completed:
                    raise _duplicate_completion_error("Probe NDJSON")
                completed = True
            case _:
                raise _wrong_command_error("Probe NDJSON")

    if not started:
        raise _missing_start_error("Probe NDJSON")
    if not completed:
        raise _missing_completion_error("Probe NDJSON")


def build_processing_results_stream_json_envelope(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    events: Iterable[MachineProcessingStreamEvent],
    summary_mode: bool,
) -> dict[str, object]:
    """Build the processing JSON envelope from durable-result stream events.

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: Effective configuration instance.
        resolved_toml: ResolvedTopmarkTomlSources.
        events: Internal machine stream events in deterministic producer order.
        summary_mode: If True, emit flat summary rows instead of per-file results.

    Returns:
        JSON-serializable envelope mapping preserving the existing processing JSON schema.

    Raises:
        ValueError: If the stream lifecycle or command identity is invalid.
    """  # noqa: DOC503 - raises ValueError via exception factory helper
    cfg_payload: ConfigPayload = build_config_payload(
        config,
        resolved_toml=resolved_toml,
    )
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    expected_index: int = 0
    started: bool = False
    completed: bool = False
    result_payloads: list[dict[str, object]] = []
    summary_results: list[ProcessingResult] = []
    for event in events:
        match event:
            case MachineRunStartedEvent(command="check" | "strip"):
                if started:
                    raise _duplicate_start_error("Processing JSON")
                # `started` remains true for the rest of the stream, so every
                # later run-start is handled by the duplicate-start guard above.
                started = True
            case MachineProcessingResultEvent(command="check" | "strip"):
                if not started:
                    raise _result_before_start_error("Processing JSON")
                if completed:
                    raise _result_after_completion_error("Processing JSON")
                if event.index != expected_index:
                    raise _non_contiguous_result_index_error(
                        label="processing JSON",
                        expected_index=expected_index,
                        actual_index=event.index,
                    )
                expected_index += 1
                if summary_mode:
                    summary_results.append(event.result)
                else:
                    result_payloads.append(build_processing_result_payload(event.result))
            case MachineRunCompletedEvent(command="check" | "strip"):
                if not started:
                    raise _completion_before_start_error("Processing JSON")
                if completed:
                    raise _duplicate_completion_error("Processing JSON")
                completed = True
            case _:
                raise _wrong_command_error("Processing JSON")

    if not started:
        raise _missing_start_error("Processing JSON")
    if not completed:
        raise _missing_completion_error("Processing JSON")

    if summary_mode:
        payload: dict[str, object] = {
            ConfigKey.CONFIG.value: cfg_payload,
            ConfigKey.CONFIG_DIAGNOSTICS.value: cfg_diag_payload,
            PipelineKey.SUMMARY.value: build_processing_results_summary_rows_payload(
                summary_results,
            ),
        }
    else:
        payload = {
            ConfigKey.CONFIG.value: cfg_payload,
            ConfigKey.CONFIG_DIAGNOSTICS.value: cfg_diag_payload,
            PipelineKey.RESULTS.value: result_payloads,
        }

    return build_json_envelope(
        meta=meta,
        **payload,
    )


def iter_processing_results_stream_ndjson_records(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    events: Iterable[MachineProcessingStreamEvent],
    summary_mode: bool,
) -> Iterator[dict[str, object]]:
    """Yield processing NDJSON records from an internal processing stream.

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: Effective configuration instance.
        resolved_toml: ResolvedTopmarkTomlSources.
        events: Internal machine stream events in deterministic producer order.
        summary_mode: Whether to emit summary records instead of per-file result records.

    Yields:
        Shaped NDJSON records preserving the existing processing machine schema.

    Raises:
        ValueError: If the stream contains events for another command, duplicate
            lifecycle events, missing lifecycle events, file events before start or
            after completion, or non-contiguous file-result indexes.
    """  # noqa: DOC503 - raises ValueError via exception factory helper
    cfg_payload: ConfigPayload = build_config_payload(
        config,
        resolved_toml=resolved_toml,
    )
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    yield from iter_config_prefix_ndjson_records(
        meta=meta,
        config=config,
        resolved_toml=resolved_toml,
        cfg_payload=cfg_payload,
        cfg_diag_payload=cfg_diag_payload,
    )

    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=flattened_diagnostics,
    )

    expected_index: int = 0
    started: bool = False
    completed: bool = False
    summary_results: list[ProcessingResult] = []
    for event in events:
        match event:
            case MachineRunStartedEvent(command="check" | "strip"):
                if started:
                    raise _duplicate_start_error("Processing NDJSON")
                # `started` remains true for the rest of the stream, so every
                # later run-start is handled by the duplicate-start guard above.
                started = True
            case MachineProcessingResultEvent(command="check" | "strip"):
                if not started:
                    raise _result_before_start_error("Processing NDJSON")
                if completed:
                    raise _result_after_completion_error("Processing NDJSON")
                if event.index != expected_index:
                    raise _non_contiguous_result_index_error(
                        label="processing NDJSON",
                        expected_index=expected_index,
                        actual_index=event.index,
                    )
                expected_index += 1
                if summary_mode:
                    summary_results.append(event.result)
                else:
                    yield build_ndjson_record(
                        kind=PipelineRecordKind.RESULT,
                        meta=meta,
                        payload=build_processing_result_payload(
                            event.result,
                            include_diff=False,
                        ),
                    )
                    diff_payload: StandaloneProcessingDiffPayload | None = (
                        build_standalone_processing_diff_payload(
                            event.result,
                        )
                    )
                    if diff_payload is not None:
                        yield build_ndjson_record(
                            kind=PipelineRecordKind.DIFF,
                            meta=meta,
                            payload=diff_payload,
                        )
            case MachineRunCompletedEvent(command="check" | "strip"):
                if not started:
                    raise _completion_before_start_error("Processing NDJSON")
                if completed:
                    raise _duplicate_completion_error("Processing NDJSON")
                completed = True
            case _:
                raise _wrong_command_error("Processing NDJSON")

    if not started:
        raise _missing_start_error("Processing NDJSON")
    if not completed:
        raise _missing_completion_error("Processing NDJSON")

    if summary_mode:
        for record in build_processing_results_summary_rows_payload(summary_results):
            yield build_ndjson_record(
                kind=PipelineRecordKind.SUMMARY,
                meta=meta,
                payload=record,
            )
