# topmark:header:start
#
#   project      : TopMark
#   file         : shapes.py
#   file_relpath : src/topmark/pipeline/machine/shapes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output shape builders for pipeline processing commands.

This module composes **machine-readable output shapes** for pipeline runs
(`topmark check` / `topmark strip`).

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

See Also:
- [`topmark.pipeline.machine.payloads`][topmark.pipeline.machine.payloads]:
    domain payload fragments for processing runs.
- [`topmark.core.machine.shapes`][topmark.core.machine.shapes]:
    shared envelope/record helpers (`build_json_envelope`, `build_ndjson_record`,
    config prefix and diagnostic record generators).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.machine.payloads import (
    build_config_diagnostics_payload,
    build_config_payload,
)
from topmark.config.machine.shapes import (
    iter_config_prefix_ndjson_records,
)
from topmark.core.machine.schemas import (
    MachineDomain,
    MachineKey,
    MachineKind,
    MetaPayload,
)
from topmark.core.machine.shapes import (
    build_json_envelope,
    build_ndjson_record,
)
from topmark.diagnostic.machine.shapes import iter_diagnostic_ndjson_records
from topmark.pipeline.machine.payloads import (
    build_processing_results_summary_map_payload,
    iter_processing_results_payload_items,
    iter_processing_results_summary_entries,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.machine.schemas import (
        ConfigDiagnosticsPayload,
        ConfigPayload,
    )
    from topmark.config.model import Config
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.machine.schemas import OutcomeSummaryMapEntry


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

    Summary mode (`summary_mode=True`) produces an outcome-keyed summary map:

    ```json
        {
          "meta": ...,
          "config": <ConfigPayload>,
          "config_diagnostics": <ConfigDiagnosticsPayload>,
          "summary": { "<outcome>": { "count": int, "label": str }, ... }
        }
    ```

    Args:
        config: The effective `Config` instance used for the run.
        meta: Shared metadata payload (`tool`/`version`).
        results: Ordered list of per-file processing contexts.
        summary_mode: If True, emit a summary map instead of per-file results.

    Returns:
        A JSON-serializable envelope mapping (not yet serialized to a JSON string).
    """
    # Prepare schema pieces once (display Config diagnostics when processing files)
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    # Envelope: meta + config + config diagnostics + results
    # OR meta + config + config diagnostics + summary
    # results_payload is {"results": [...]} or {"summary": {...}}
    if summary_mode:
        summary_dict: dict[str, OutcomeSummaryMapEntry] = (
            build_processing_results_summary_map_payload(
                results,
            )
        )
        payload: dict[str, object] = {
            MachineKey.CONFIG: cfg_payload,
            MachineKey.CONFIG_DIAGNOSTICS: cfg_diag_payload,
            MachineKey.SUMMARY: summary_dict,
        }
    else:
        results_iter: Iterator[dict[str, object]] = iter_processing_results_payload_items(
            results,
        )
        payload = {
            MachineKey.CONFIG: cfg_payload,
            MachineKey.CONFIG_DIAGNOSTICS: cfg_diag_payload,
            MachineKey.RESULTS: list(results_iter),
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
    3) zero or more `kind="diagnostic"` records for config diagnostics
    4) then either:
    - summary mode: one `kind="summary"` record per outcome bucket
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
    # Prepare schema pieces once (display Config diagnostics when processing files)
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    yield from iter_config_prefix_ndjson_records(
        config=config,
        meta=meta,
        cfg_payload=cfg_payload,
        cfg_diag_payload=cfg_diag_payload,
    )

    # One diagnostic per line
    yield from iter_diagnostic_ndjson_records(
        meta=meta,
        domain=MachineDomain.CONFIG,
        diagnostics=config.diagnostics,
    )

    if summary_mode:
        for record in iter_processing_results_summary_entries(results):
            yield build_ndjson_record(
                kind=MachineKind.SUMMARY,
                meta=meta,
                payload=record,
            )
    else:
        for r in results:
            yield build_ndjson_record(
                kind=MachineKind.RESULT,
                meta=meta,
                payload=r.to_dict(),
            )
