# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/config/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output payload builders for TopMark config commands.

This module contains *pure* helpers that build strongly-typed payload objects
(dataclasses) for config-related machine output.

Responsibilities:
  - Convert `Config` / TOML-derived structures into JSON-friendly values.
  - Return schema dataclasses from
    [`topmark.config.machine.schemas`][topmark.config.machine.schemas].

This module performs no I/O and does not shape envelopes/records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.keys import CliCmd
from topmark.config.io.serializers import config_to_topmark_toml_table
from topmark.config.machine.schemas import ConfigCheckSummary
from topmark.config.machine.schemas import ConfigDiagnosticsPayload
from topmark.config.machine.schemas import ConfigPayload
from topmark.config.machine.schemas import ConfigProvenanceLayerPayload
from topmark.config.machine.schemas import ConfigProvenancePayload
from topmark.config.resolution import build_config_layers_from_resolved_toml_sources
from topmark.core.machine.schemas import normalize_payload
from topmark.core.typing_guards import as_object_dict
from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts
from topmark.diagnostic.machine.schemas import MachineDiagnosticEntry
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import compute_diagnostic_stats
from topmark.toml.defaults import build_default_topmark_toml_table
from topmark.toml.getters import get_object_dict_value
from topmark.toml.getters import get_string_dict_value
from topmark.toml.getters import get_string_list_dict_value

if TYPE_CHECKING:
    from topmark.config.layers import ConfigLayer
    from topmark.config.model import Config
    from topmark.toml.resolution import ResolvedTopmarkTomlSources
    from topmark.toml.types import TomlTable


def build_config_payload(config: Config) -> ConfigPayload:
    """Build a JSON-friendly payload capturing a Config snapshot.

    Args:
        config: Immutable layered configuration instance.

    Returns:
        ConfigPayload: JSON-serializable representation of the layered Config,
            without diagnostics.
    """
    base: TomlTable = config_to_topmark_toml_table(
        config,
        include_files=False,
    )

    normalized_base: object = normalize_payload(base)
    normalized_dict: dict[str, object] = as_object_dict(normalized_base)

    return ConfigPayload(
        fields=get_string_dict_value(normalized_dict, "fields"),
        header=get_string_list_dict_value(normalized_dict, "header"),
        formatting=get_object_dict_value(normalized_dict, "formatting"),
        files=get_object_dict_value(normalized_dict, "files"),
        policy=get_object_dict_value(normalized_dict, "policy"),
        policy_by_type=get_object_dict_value(normalized_dict, "policy_by_type"),
    )


def _normalize_toml_fragment(fragment: TomlTable) -> dict[str, object]:
    """Normalize one TOML fragment to a JSON-friendly mapping.

    Args:
        fragment: Source-local TopMark TOML fragment.

    Returns:
        A JSON-friendly mapping produced by recursively normalizing TOML values
        (for example, paths and enums) and then narrowing the result to an
        object-like dict.
    """
    normalized: object = normalize_payload(fragment)
    return as_object_dict(normalized)


def build_config_provenance_payload(
    resolved_toml: ResolvedTopmarkTomlSources,
) -> ConfigProvenancePayload:
    """Build a machine-readable layered config provenance payload.

    Args:
        resolved_toml: Resolved TOML sources for the current run.

    Returns:
        JSON-friendly provenance payload with ordered layers, starting with the
        built-in defaults layer when present.
    """
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved_toml.sources
    )

    out_layers: list[ConfigProvenanceLayerPayload] = []

    # Preserve the synthetic built-in defaults layer first so that machine
    # output mirrors the human-facing layered provenance export.
    if layers:
        default_layer: ConfigLayer = layers[0]
        scope_root: str | None = (
            str(default_layer.scope_root) if default_layer.scope_root is not None else None
        )
        out_layers.append(
            ConfigProvenanceLayerPayload(
                origin=str(default_layer.origin),
                kind=default_layer.kind.value,
                precedence=default_layer.precedence,
                scope_root=(scope_root),
                toml=_normalize_toml_fragment(build_default_topmark_toml_table()),
            )
        )

    # Then append one payload per resolved TOML source, preserving resolution
    # order and the corresponding source-local TOML fragment.
    for layer, source in zip(layers[1:], resolved_toml.sources, strict=True):
        scope_root = str(layer.scope_root) if layer.scope_root is not None else None
        out_layers.append(
            ConfigProvenanceLayerPayload(
                origin=str(layer.origin),
                kind=layer.kind.value,
                precedence=layer.precedence,
                scope_root=scope_root,
                toml=_normalize_toml_fragment(source.parsed.toml_fragment),
            )
        )

    return ConfigProvenancePayload(layers=out_layers)


def build_config_diagnostics_payload(config: Config) -> ConfigDiagnosticsPayload:
    """Build a JSON-friendly diagnostics payload for a given Config.

    Args:
        config: The Config instance.

    Returns:
        JSON-serializable diagnostics metadata for the given `Config`.
    """
    diag_entries: list[MachineDiagnosticEntry] = [
        MachineDiagnosticEntry(level=d.level.value, message=d.message) for d in config.diagnostics
    ]
    stats: DiagnosticStats = compute_diagnostic_stats(config.diagnostics)
    diag_counts: MachineDiagnosticCounts = MachineDiagnosticCounts(
        info=stats.n_info,
        warning=stats.n_warning,
        error=stats.n_error,
    )

    return ConfigDiagnosticsPayload(
        diagnostics=diag_entries,
        diagnostic_counts=diag_counts,
    )


def build_config_diagnostics_counts_payload(config: Config) -> MachineDiagnosticCounts:
    """Build a counts-only diagnostics payload for a given Config.

    Useful when emitting aggregate diagnostic statistics without duplicating
    per-diagnostic entries.

    Args:
        config: The Config instance.

    Returns:
        JSON-serializable mapping containing only
        ``{"diagnostic_counts": {"info": int, "warning": int, "error": int}}``.
    """
    stats: DiagnosticStats = compute_diagnostic_stats(config.diagnostics)
    return MachineDiagnosticCounts(
        info=stats.n_info,
        warning=stats.n_warning,
        error=stats.n_error,
    )


def build_config_check_summary_payload(
    *,
    config: Config,
    cfg_diag_payload: ConfigDiagnosticsPayload | None = None,
    strict: bool,
    ok: bool,
) -> ConfigCheckSummary:
    """Build the `summary` payload for `topmark config check`.

    The summary is embedded differently depending on format:
      - JSON: included as the `summary` field in the top-level envelope.
      - NDJSON: emitted as a single record with kind `summary`.

    Args:
        config: Immutable layered configuration.
        cfg_diag_payload: Optional precomputed diagnostics payload to avoid recomputation.
        strict: Whether warnings are treated as failures.
        ok: Whether the config passed validation.

    Returns:
        A JSON-friendly mapping representing the config-check summary.
    """
    if cfg_diag_payload is None:
        diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    else:
        # Reuse counts from the diagnostics payload
        diag_payload = cfg_diag_payload

    counts_only: MachineDiagnosticCounts = diag_payload.diagnostic_counts

    summary = ConfigCheckSummary(
        command=CliCmd.CONFIG,
        subcommand=CliCmd.CONFIG_CHECK,
        ok=ok,
        strict=strict,
        diagnostic_counts=counts_only,
        config_files=[str(p) for p in config.config_files],
    )

    return summary
