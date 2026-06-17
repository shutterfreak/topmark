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
from topmark.pipeline.machine.payloads import build_processing_results_summary_rows_payload
from topmark.pipeline.machine.payloads import iter_probe_results_payload_items
from topmark.pipeline.machine.payloads import iter_processing_results_payload_items
from topmark.pipeline.machine.payloads import iter_processing_results_summary_entries
from topmark.pipeline.machine.schemas import PipelineKey
from topmark.pipeline.machine.schemas import PipelineRecordKind

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from topmark.config.machine.schemas import ConfigDiagnosticsPayload
    from topmark.config.machine.schemas import ConfigPayload
    from topmark.config.model import FrozenConfig
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.pipeline.machine.schemas import OutcomeSummaryRow
    from topmark.pipeline.result import ProcessingResult
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


def build_probe_results_json_envelope(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
) -> dict[str, object]:
    """Build the JSON envelope for resolution probe results.

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: The effective [`FrozenConfig`][topmark.config.model.FrozenConfig]
            instance used for the run.
        resolved_toml: Resolved TOML sources used to build the optional layered
            provenance export.
        results: Ordered list of probe contexts. The list may include normal
            file-backed probe contexts and synthetic contexts for explicit inputs
            filtered before file-type probing.

    Returns:
        JSON-serializable envelope mapping (not yet serialized to JSON).
    """
    # Prepare config payloads once, including flattened compatibility diagnostics.
    cfg_payload: ConfigPayload = build_config_payload(
        config,
        resolved_toml=resolved_toml,
    )
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    # Probe payloads include both normal file-type probe results and synthetic
    # filtered results for explicit inputs removed during discovery.
    probe_payloads: list[dict[str, object]] = list(iter_probe_results_payload_items(results))

    return build_json_envelope(
        meta=meta,
        **{
            ConfigKey.CONFIG.value: cfg_payload,
            ConfigKey.CONFIG_DIAGNOSTICS.value: cfg_diag_payload,
            PipelineKey.PROBES.value: probe_payloads,
        },
    )


def iter_probe_results_ndjson_records(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
) -> Iterator[dict[str, object]]:
    """Yield NDJSON records for resolution probe results.

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: Effective configuration instance.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of probe contexts. The list may include normal
            file-backed probe contexts and synthetic contexts for explicit inputs
            filtered before file-type probing.

    Yields:
        Shaped NDJSON record mappings for config prefix records, config diagnostics,
        and one `kind="probe"` record per probe context.
    """
    # Prepare config payloads once, including flattened compatibility diagnostics.
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

    # One probe record per context, including synthetic filtered contexts.
    for payload in iter_probe_results_payload_items(results):
        yield build_ndjson_record(
            kind=PipelineRecordKind.PROBE,
            meta=meta,
            payload=payload,
        )


def build_processing_results_json_envelope(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
    summary_mode: bool,
) -> dict[str, object]:
    """Build the JSON envelope for processing results (`check`/`strip`).

    Detail mode (`summary_mode=False`) produces a per-file results list:

    ```json
        {
          "meta": ...,
          "config": <ConfigPayload>,
          "config_diagnostics": <ConfigDiagnosticsPayload>,
          "results": [ <per-file result dict> ... ]
        }
    ```

    Summary mode (`summary_mode=True`) produces a flat summary-row list:

    ```json
        {
          "meta": ...,
          "config": <ConfigPayload>,
          "config_diagnostics": <ConfigDiagnosticsPayload>,
          "summary": [
            {"outcome": "unchanged", "reason": "no changes needed", "count": 3},
            {"outcome": "would insert", "reason": "header missing, changes found", "count": 1}
          ]
        }
    ```

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: The effective [`FrozenConfig`][topmark.config.model.FrozenConfig]
            instance used for the run.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of durable per-file processing results.
        summary_mode: If True, emit flat summary rows instead of per-file results.

    Returns:
        A JSON-serializable envelope mapping (not yet serialized to a JSON string).
    """
    # Prepare config payloads once, including flattened compatibility diagnostics.
    cfg_payload: ConfigPayload = build_config_payload(
        config,
        resolved_toml=resolved_toml,
    )
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    # Envelope: meta + config + config diagnostics + results
    # OR meta + config + config diagnostics + summary
    # results_payload is {"results": [...]} or {"summary": {...}}
    if summary_mode:
        summary_list: list[OutcomeSummaryRow] = build_processing_results_summary_rows_payload(
            results,
        )
        payload: dict[str, object] = {
            ConfigKey.CONFIG.value: cfg_payload,
            ConfigKey.CONFIG_DIAGNOSTICS.value: cfg_diag_payload,
            PipelineKey.SUMMARY.value: summary_list,
        }
    else:
        results_iter: Iterator[dict[str, object]] = iter_processing_results_payload_items(
            results,
        )
        payload = {
            ConfigKey.CONFIG.value: cfg_payload,
            ConfigKey.CONFIG_DIAGNOSTICS.value: cfg_diag_payload,
            PipelineKey.RESULTS.value: list(results_iter),
        }

    envelope: dict[str, object] = build_json_envelope(
        meta=meta,
        **payload,
    )

    return envelope


def iter_processing_results_ndjson_records(
    *,
    meta: MetaPayload,
    config: FrozenConfig,
    resolved_toml: ResolvedTopmarkTomlSources,
    results: Iterable[ProcessingResult],
    summary_mode: bool,
) -> Iterator[dict[str, object]]:
    """Yield NDJSON records for processing results (`check`/`strip`).

    The NDJSON stream is emitted in a stable order:

    1) `kind="config"` record
    2) `kind="config_diagnostics"` record (counts-only)
    3) zero or more `kind="diagnostic"` records for flattened compatibility config diagnostics
    4) then either:
    - summary mode: one `kind="summary"` record per `(outcome, reason)` bucket
    - detail mode: one `kind="result"` record per processed file

    Args:
        meta: Shared metadata payload (`tool`/`version`).
        config: Effective configuration instance.
        resolved_toml: ResolvedTopmarkTomlSources,
        results: Ordered list of durable per-file processing results.
        summary_mode: Whether to emit summary records instead of per-file result records.

    Yields:
        Shaped NDJSON record mappings (not yet serialized). Each yielded record
        includes `kind` and `meta` and follows the project's NDJSON envelope contract.
    """
    # Prepare config payloads once, including flattened compatibility diagnostics.
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

    # One diagnostic per line
    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=flattened_diagnostics,
    )

    if summary_mode:
        for record in iter_processing_results_summary_entries(
            results,
        ):
            yield build_ndjson_record(
                kind=PipelineRecordKind.SUMMARY,
                meta=meta,
                payload=record,
            )
    else:
        for r in results:
            yield build_ndjson_record(
                kind=PipelineRecordKind.RESULT,
                meta=meta,
                payload=r.to_dict(),
            )
