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

from typing import TYPE_CHECKING, Any, cast

from topmark.cli.keys import CliCmd
from topmark.config.machine.schemas import (
    ConfigDiagnosticsPayload,
    ConfigPayload,
)
from topmark.config.model import Config
from topmark.core.machine.schemas import (
    MachineKey,
    normalize_payload,
)
from topmark.diagnostic.machine.schemas import (
    MachineDiagnosticCounts,
    MachineDiagnosticEntry,
)
from topmark.diagnostic.model import (
    DiagnosticStats,
    compute_diagnostic_stats,
)

if TYPE_CHECKING:
    from topmark.config.io import TomlTable
    from topmark.config.model import Config


def build_config_payload(config: Config) -> ConfigPayload:
    """Build a JSON-friendly payload capturing a Config snapshot.

    Args:
        config: Immutable runtime configuration instance.

    Returns:
        ConfigPayload: JSON-serializable representation of the Config, without
            diagnostics.
    """
    base: TomlTable = config.to_toml_dict(include_files=False)  # TomlTable ~ dict[str, Any]

    writer = base.get("writer", {})
    # Make sure Enums become simple strings
    target = config.output_target.name if config.output_target is not None else None
    strategy = config.file_write_strategy.name if config.file_write_strategy is not None else None
    base["writer"] = {**writer, "target": target, "strategy": strategy}

    json_safe_base: Any = normalize_payload(base)
    if isinstance(json_safe_base, dict):
        # Keep pyright happy
        data: dict[str, Any] = cast("dict[str, Any]", json_safe_base)
    else:
        data = {}

    return ConfigPayload(
        fields=data.get("fields", {}),
        header=data.get("header", {}),
        formatting=data.get("formatting", {}),
        writer=data.get("writer", {}),
        files=data.get("files", {}),
        policy=data.get("policy", {}),
        policy_by_type=data.get("policy_by_type", {}),
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
) -> dict[str, object]:
    """Build the `summary` payload for `topmark config check`.

    The summary is embedded differently depending on format:
      - JSON: included as the `summary` field in the top-level envelope.
      - NDJSON: emitted as a single record with kind `summary`.

    Args:
        config: Immutable runtime configuration.
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

    summary: dict[str, object] = {
        MachineKey.COMMAND: CliCmd.CONFIG,
        MachineKey.SUBCOMMAND: CliCmd.CONFIG_CHECK,
        MachineKey.OK: ok,
        MachineKey.STRICT: strict,
        MachineKey.DIAGNOSTIC_COUNTS: counts_only.to_dict(),
        MachineKey.CONFIG_FILES: [str(p) for p in config.config_files],
    }
    return summary
