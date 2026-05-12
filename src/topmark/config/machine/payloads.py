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
(dataclasses) for config-related machine-readable output.

Responsibilities:
  - Convert [`FrozenConfig`][topmark.config.model.FrozenConfig] / TOML-derived
    structures into JSON-friendly values.
  - Return schema dataclasses from
    [`topmark.config.machine.schemas`][topmark.config.machine.schemas].
  - Flatten staged config-validation diagnostics at the machine-output
    boundary when diagnostics payloads are requested.

This module performs no I/O and does not shape envelopes/records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.keys import CliCmd
from topmark.config.io.serializers import config_to_topmark_toml_table
from topmark.config.machine.schemas import ConfigCheckSummary
from topmark.config.machine.schemas import ConfigDiagnosticsPayload
from topmark.config.machine.schemas import ConfigPayload
from topmark.core.machine.schemas import normalize_payload
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import get_object_dict_value
from topmark.core.typing_guards import get_string_dict_value
from topmark.core.typing_guards import get_string_list_dict_value
from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts
from topmark.diagnostic.machine.schemas import MachineDiagnosticEntry
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import compute_diagnostic_stats
from topmark.runtime.writer_options import writer_options_to_toml_table
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from topmark.config.model import FrozenConfig
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.toml.resolution import ResolvedTopmarkTomlSources
    from topmark.toml.types import TomlTable


def build_config_payload(
    config: FrozenConfig,
    *,
    resolved_toml: ResolvedTopmarkTomlSources,
) -> ConfigPayload:
    """Build a JSON-friendly payload capturing an effective config snapshot.

    [`FrozenConfig`][topmark.config.model.FrozenConfig] contains the layered
    TopMark configuration. Resolved writer options are runtime-facing but may
    originate from TOML, so callers can pass them here to include the effective
    `[writer]` section in machine-readable config output.

    Args:
        config: Immutable layered configuration instance.
        resolved_toml: Resolved TOML sources used to build the optional layered
            provenance export.

    Returns:
        ConfigPayload: JSON-serializable representation of the effective
            configuration snapshot, without diagnostics.
    """
    base: TomlTable = config_to_topmark_toml_table(
        config,
        include_files=False,
    )
    base.update(
        writer_options_to_toml_table(
            resolved_toml.writer_options,
        )
    )

    normalized_base: object = normalize_payload(base)
    normalized_dict: dict[str, object] = as_object_dict(normalized_base)

    return ConfigPayload(
        fields=get_string_dict_value(
            normalized_dict,
            Toml.SECTION_FIELDS,
        ),
        header=get_string_list_dict_value(
            normalized_dict,
            Toml.SECTION_HEADER,
        ),
        formatting=get_object_dict_value(
            normalized_dict,
            Toml.SECTION_FORMATTING,
        ),
        files=get_object_dict_value(
            normalized_dict,
            Toml.SECTION_FILES,
        ),
        policy=get_object_dict_value(
            normalized_dict,
            Toml.SECTION_POLICY,
        ),
        policy_by_type=get_object_dict_value(
            normalized_dict,
            Toml.SECTION_POLICY_BY_TYPE,
        ),
        writer=get_object_dict_value(
            normalized_dict,
            Toml.SECTION_WRITER,
        ),
    )


def build_config_diagnostics_payload(config: FrozenConfig) -> ConfigDiagnosticsPayload:
    """Build a JSON-friendly diagnostics payload for a given `FrozenConfig`.

    Staged config-validation logs are flattened here so machine-readable output keeps
    exposing the current compatibility diagnostics view.

    Args:
        config: The [`FrozenConfig`][topmark.config.model.FrozenConfig] instance.

    Returns:
        JSON-serializable diagnostics metadata for the given
        [`FrozenConfig`][topmark.config.model.FrozenConfig].
    """
    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    diag_entries: list[MachineDiagnosticEntry] = [
        MachineDiagnosticEntry(level=d.level.value, message=d.message)
        for d in flattened_diagnostics
    ]
    stats: DiagnosticStats = compute_diagnostic_stats(flattened_diagnostics)
    diag_counts: MachineDiagnosticCounts = MachineDiagnosticCounts(
        info=stats.n_info,
        warning=stats.n_warning,
        error=stats.n_error,
    )

    return ConfigDiagnosticsPayload(
        diagnostics=diag_entries,
        diagnostic_counts=diag_counts,
    )


def build_config_diagnostics_counts_payload(config: FrozenConfig) -> MachineDiagnosticCounts:
    """Build a counts-only diagnostics payload for a given `FrozenConfig`.

    Useful when emitting aggregate diagnostic statistics without duplicating
    per-diagnostic entries. Staged config-validation logs are flattened here at
    the machine-readable output boundary.

    Args:
        config: The [`FrozenConfig`][topmark.config.model.FrozenConfig] instance.

    Returns:
        JSON-serializable mapping containing only
        ``{"diagnostic_counts": {"info": int, "warning": int, "error": int}}``.
    """
    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    stats: DiagnosticStats = compute_diagnostic_stats(flattened_diagnostics)
    return MachineDiagnosticCounts(
        info=stats.n_info,
        warning=stats.n_warning,
        error=stats.n_error,
    )


def build_config_check_summary_payload(
    *,
    config: FrozenConfig,
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
