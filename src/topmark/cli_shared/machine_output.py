# topmark:header:start
#
#   project      : TopMark
#   file         : machine_output.py
#   file_relpath : src/topmark/cli_shared/machine_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-readable payload builders for TopMark CLI output.

This module defines JSON-friendly TypedDict payloads and helper functions
used to build machine-readable data structures for TopMark's CLI:

- ConfigPayload: snapshot of the effective configuration, derived from
  Config.to_toml_dict() with JSON-safe normalization.
- ConfigDiagnosticsPayload: per-level diagnostic counts and messages for
  configuration-related diagnostics.
- ProcessingSummaryEntry and build_processing_results_payload(): payloads
  for per-file results and aggregated outcome counts.

These helpers are deliberately Click-free and do not perform any I/O.
They are consumed by [`topmark.cli.utils`][topmark.cli.utils]
to render JSON/NDJSON output for
`--output-format json` and `--output-format ndjson`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

from topmark.api.view import collect_outcome_counts
from topmark.constants import TOPMARK_VERSION
from topmark.core.diagnostics import compute_diagnostic_stats

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.io import TomlTable
    from topmark.config.model import Config
    from topmark.core.diagnostics import DiagnosticStats
    from topmark.pipeline.context.model import ProcessingContext


class MetaPayload(TypedDict):
    """Metadata describing the TopMark runtime environment for machine output."""

    tool: str
    version: str


def build_meta_payload() -> MetaPayload:
    """Build a small metadata payload with tool name and version.

    The version is resolved using importlib.metadata for the installed
    "topmark" distribution. If the package cannot be found, the version
    is set to "unknown".
    """
    tool_name: str = "topmark"
    ver: str = TOPMARK_VERSION
    return {"tool": tool_name, "version": ver}


class ConfigDiagnosticEntry(TypedDict):
    """Machine-readable diagnostic entry for config metadata."""

    level: str
    message: str


class ConfigDiagnosticCounts(TypedDict):
    """Aggregated per-level counts for config diagnostics."""

    info: int
    warning: int
    error: int


class ConfigPayload(TypedDict, total=False):
    """JSON-friendly representation of the effective TopMark configuration.

    The shape loosely mirrors ``Config.to_toml_dict(include_files=False)`` but
    guarantees JSON-serializable values (paths/Enums normalized to strings).

    Diagnostics are emitted separately via ConfigDiagnosticsPayload.
    """

    # loosely mirrors to_toml_dict structure with JSON-friendly types
    fields: dict[str, str]
    header: dict[str, list[str]]
    formatting: dict[str, Any]
    writer: dict[str, Any]
    files: dict[str, Any]
    policy: dict[str, Any]
    policy_by_type: dict[str, Any]


def jsonify_config_value(value: Any) -> Any:
    """Recursively convert config payload values into JSON-serializable forms.

    This helper normalizes:
      - pathlib.Path -> str
      - Enum -> Enum.name
      - Mapping -> dict with JSON-serializable values
      - list/tuple/set/frozenset -> list with JSON-serializable values

    It is intentionally conservative and only applies to the config payload
    to avoid surprising transformations elsewhere.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, Mapping):
        # Safe: `value` is a Mapping after the isinstance check; we treat keys
        # as generic objects and values as Any for JSONification purposes.
        mapping: Mapping[object, Any] = cast("Mapping[object, Any]", value)
        return {str(k): jsonify_config_value(v) for k, v in mapping.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        # Safe: `value` is a collection after the isinstance check; iterate as objects.
        seq: Iterable[object] = cast("Iterable[object]", value)
        return [jsonify_config_value(v) for v in seq]
    return value


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

    json_safe_base: Any = jsonify_config_value(base)
    return json_safe_base


class ConfigDiagnosticsPayload(TypedDict, total=False):
    """Machine-readable diagnostics collected while building the Config.

    Structure:
      - diagnostics: list of {level, message} entries.
      - diagnostic_counts: aggregate per-level counts.
    """

    diagnostics: list[ConfigDiagnosticEntry]
    diagnostic_counts: ConfigDiagnosticCounts


def build_config_diagnostics_payload(config: Config) -> ConfigDiagnosticsPayload:
    """Build a JSON-friendly diagnostics payload for a given Config.

    Args:
        config (Config): The Config instance.

    Returns:
        ConfigDiagnosticsPayload: JSON-serializable diagnostics metadata for
            the given Config.
    """
    diag: ConfigDiagnosticsPayload = {}
    diag_entries: list[ConfigDiagnosticEntry] = [
        {"level": d.level.value, "message": d.message} for d in config.diagnostics
    ]
    stats: DiagnosticStats = compute_diagnostic_stats(config.diagnostics)
    diag_counts: ConfigDiagnosticCounts = {
        "info": stats.n_info,
        "warning": stats.n_warning,
        "error": stats.n_error,
    }

    diag["diagnostics"] = diag_entries
    diag["diagnostic_counts"] = diag_counts

    json_safe_diag: Any = jsonify_config_value(diag)
    return json_safe_diag


class ProcessingSummaryEntry(TypedDict):
    """Machine-readable summary entry for per-outcome counts."""

    count: int
    label: str


def build_processing_results_payload(
    results: list[ProcessingContext],
    *,
    summary_mode: bool,
) -> dict[str, Any]:
    """Build the machine-readable payload for processing results.

    For JSON:
      - summary_mode=False: this will be nested under "results".
      - summary_mode=True: this will be nested under "summary".
    """
    if summary_mode:
        counts = collect_outcome_counts(results)
        summary: dict[str, ProcessingSummaryEntry] = {
            key: {"count": cnt, "label": label} for key, (cnt, label, _color) in counts.items()
        }
        return {"summary": summary}
    else:
        details: list[dict[str, object]] = [r.to_dict() for r in results]
        return {"results": details}
