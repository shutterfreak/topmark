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

This module contains *pure* helpers that shape config-related payload objects
used by JSON/NDJSON output.

The builders here do not perform I/O. They return strongly typed schema
dataclasses from [`topmark.config.machine.schemas`][topmark.config.machine.schemas].
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from topmark.config.machine.schemas import (
    ConfigDiagnosticCounts,
    ConfigDiagnosticEntry,
    ConfigDiagnosticsPayload,
    ConfigPayload,
)
from topmark.core.diagnostics import DiagnosticStats, compute_diagnostic_stats
from topmark.core.machine.formats import normalize_payload

if TYPE_CHECKING:
    from topmark.config.io import TomlTable
    from topmark.config.model import Config


def build_config_payload(config: Config) -> ConfigPayload:
    """Build a JSON-friendly payload capturing a Config snapshot.

    Args:
        config (Config): Immutable runtime configuration instance.

    Returns:
        ConfigPayload: JSON-serializable representation of the Config, without
            diagnostics.
    """
    base: TomlTable = config.to_toml_dict(include_files=False)  # TomlTable ~ dict[str, Any]

    writer = base.get("writer", {})
    # Make sure Enums become simple strings
    target = config.output_target.name if config.output_target is not None else None
    strategy = config.file_write_strategy.name if config.file_write_strategy is not None else None
    writer = {**writer, "target": target, "strategy": strategy}
    base["writer"] = writer

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
        config (Config): The Config instance.

    Returns:
        ConfigDiagnosticsPayload: JSON-serializable diagnostics metadata for
            the given `Config`.
    """
    diag_entries: list[ConfigDiagnosticEntry] = [
        ConfigDiagnosticEntry(level=d.level.value, message=d.message) for d in config.diagnostics
    ]
    stats: DiagnosticStats = compute_diagnostic_stats(config.diagnostics)
    diag_counts: ConfigDiagnosticCounts = ConfigDiagnosticCounts(
        info=stats.n_info,
        warning=stats.n_warning,
        error=stats.n_error,
    )

    return ConfigDiagnosticsPayload(
        diagnostics=diag_entries,
        diagnostic_counts=diag_counts,
    )


def build_config_diagnostics_counts_payload(config: Config) -> ConfigDiagnosticCounts:
    """Build a counts-only diagnostics payload for a given Config.

    Useful when emitting aggregate diagnostic statistics without duplicating
    per-diagnostic entries.

    Args:
        config (Config): The Config instance.

    Returns:
        ConfigDiagnosticCounts: JSON-serializable mapping containing only
            ``{"diagnostic_counts": {"info": int, "warning": int, "error": int}}``.
    """
    stats: DiagnosticStats = compute_diagnostic_stats(config.diagnostics)
    counts = ConfigDiagnosticCounts(
        info=stats.n_info,
        warning=stats.n_warning,
        error=stats.n_error,
    )
    return counts
