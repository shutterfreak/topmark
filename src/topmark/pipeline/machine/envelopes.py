# topmark:header:start
#
#   project      : TopMark
#   file         : envelopes.py
#   file_relpath : src/topmark/pipeline/machine/envelopes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output envelope builders for pipeline processing commands.

This module composes **machine-readable output shapes** for pipeline runs
(`topmark check`, `topmark strip`, and `topmark probe`).

It is intentionally:
- console-/Click-free (no printing, no CLI concerns)
- serialization-free (no `json.dumps`)

Responsibilities:
- **JSON**: build a single top-level envelope containing `meta`, `config`,
  `config_diagnostics`, and either `results` (detail mode) or `summary`
  (summary mode).
- **NDJSON**: yield a stream of per-record mappings following the project’s
  NDJSON contract (Pattern A: every record includes `kind` and `meta`), starting
  with config prefix records and followed by either per-file `result` records
  (detail mode) or per-bucket `summary` records (summary mode).

Where config diagnostics are included, this module exposes the flattened
compatibility view derived from staged config-validation logs.

See Also:
- [`topmark.pipeline.machine.payloads`][topmark.pipeline.machine.payloads]:
    domain payload fragments for processing runs.
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
from topmark.pipeline.machine.schemas import PipelineKind

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.machine.schemas import ConfigDiagnosticsPayload
    from topmark.config.machine.schemas import ConfigPayload
    from topmark.config.model import Config
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.machine.schemas import OutcomeSummaryRow


def build_probe_results_json_envelope(
    *,
    config: Config,
    meta: MetaPayload,
    results: list[ProcessingContext],
) -> dict[str, object]:
    """Build the JSON envelope for resolution probe results.

    Args:
        config: The effective `Config` instance used for the run.
        meta: Shared metadata payload (`tool`/`version`).
        results: Ordered list of per-file processing contexts.

    Returns:
        A JSON-serializable envelope mapping (not yet serialized to JSON).
    """
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
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
    config: Config,
    meta: MetaPayload,
    results: list[ProcessingContext],
) -> Iterator[dict[str, object]]:
    """Yield NDJSON records for resolution probe results.

    Args:
        config: Effective configuration instance.
        meta: Shared metadata payload (`tool`/`version`).
        results: Ordered list of per-file processing contexts.

    Yields:
        Shaped NDJSON record mappings for config prefix records, config diagnostics,
        and one `kind="probe"` record per processed file.
    """
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    yield from iter_config_prefix_ndjson_records(
        config=config,
        meta=meta,
        cfg_payload=cfg_payload,
        cfg_diag_payload=cfg_diag_payload,
    )

    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=flattened_diagnostics,
    )

    for payload in iter_probe_results_payload_items(results):
        yield build_ndjson_record(
            kind=PipelineKind.PROBE,
            meta=meta,
            payload=payload,
        )


def build_processing_results_json_envelope(
    *,
    config: Config,
    meta: MetaPayload,
    results: list[ProcessingContext],
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
        config: The effective `Config` instance used for the run.
        meta: Shared metadata payload (`tool`/`version`).
        results: Ordered list of per-file processing contexts.
        summary_mode: If True, emit flat summary rows instead of per-file results.

    Returns:
        A JSON-serializable envelope mapping (not yet serialized to a JSON string).
    """
    # Prepare config payloads once, including flattened compatibility diagnostics.
    cfg_payload: ConfigPayload = build_config_payload(config)
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
    config: Config,
    meta: MetaPayload,
    results: list[ProcessingContext],
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
        config: Effective configuration instance.
        meta: Shared metadata payload (`tool`/`version`).
        results: Ordered list of per-file processing contexts.
        summary_mode: Whether to emit summary records instead of per-file result records.

    Yields:
        Shaped NDJSON record mappings (not yet serialized). Each yielded record
        includes `kind` and `meta` and follows the project’s NDJSON envelope contract.
    """
    # Prepare config payloads once, including flattened compatibility diagnostics.
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    yield from iter_config_prefix_ndjson_records(
        config=config,
        meta=meta,
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
        for record in iter_processing_results_summary_entries(results):
            yield build_ndjson_record(
                kind=PipelineKind.SUMMARY,
                meta=meta,
                payload=record,
            )
    else:
        for r in results:
            yield build_ndjson_record(
                kind=PipelineKind.RESULT,
                meta=meta,
                payload=r.to_dict(),
            )
