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
from topmark.config.io.guards import as_object_dict
from topmark.config.io.guards import get_object_dict_value
from topmark.config.io.guards import get_string_dict_value
from topmark.config.io.guards import get_string_list_dict_value
from topmark.config.io.serializers import config_to_toml_dict
from topmark.config.machine.schemas import ConfigCheckSummary
from topmark.config.machine.schemas import ConfigDiagnosticsPayload
from topmark.config.machine.schemas import ConfigPayload
from topmark.config.model import Config
from topmark.core.machine.schemas import normalize_payload
from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts
from topmark.diagnostic.machine.schemas import MachineDiagnosticEntry
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import compute_diagnostic_stats

if TYPE_CHECKING:
    from topmark.config.io.types import TomlTable
    from topmark.config.model import Config


def build_config_payload(config: Config) -> ConfigPayload:
    """Build a JSON-friendly payload capturing a Config snapshot.

    Args:
        config: Immutable layered configuration instance.

    Returns:
        ConfigPayload: JSON-serializable representation of the layered Config,
            without diagnostics.
    """
    base: TomlTable = config_to_toml_dict(
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
