# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/config/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Machine-readable schema objects for config-related output (JSON/NDJSON)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from topmark.core.machine.formats import MachineKey

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(slots=True)
class ConfigDiagnosticEntry:
    """Machine-readable diagnostic entry for config metadata."""

    level: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-friendly dict of the `ConfigDiagnosticEntry` instance.

        Returns:
            dict[str, str]: dict with keys ``"level"`` and ``"message"``,
                representing the `ConfigDiagnosticEntry` instance.
        """
        return {
            "level": self.level,
            "message": self.message,
        }


@dataclass(slots=True)
class ConfigDiagnosticCounts:
    """Aggregated per-level counts for config diagnostics."""

    info: int
    warning: int
    error: int

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-friendly dict of the `ConfigDiagnosticCounts` instance.

        Returns:
            dict[str, int]: counts-only payload with keys `info`, `warning`,
                and `error`.
        """
        return {
            "info": self.info,
            "warning": self.warning,
            "error": self.error,
        }


@dataclass(slots=True)
class ConfigPayload:
    """JSON-friendly representation of the effective TopMark configuration.

    The shape loosely mirrors
    [`Config.to_toml_dict(include_files=False)`][topmark.config.model.Config.to_toml_dict]
    but guarantees JSON-serializable values (paths/Enums normalized to strings).

    Diagnostics are emitted separately via `ConfigDiagnosticsPayload`.

    Attributes:
        fields (dict[str, str]): TODO.
        header (dict[str, list[str]]): TODO.
        formatting (dict[str, Any]): TODO.
        writer (dict[str, Any]): TODO.
        files (dict[str, Any]): List of files to process.
        policy (dict[str, Any]): Global, resolved, immutable runtime policy (plain booleans),
            applied after discovery.
        policy_by_type (dict[str, Any]): Per-file-type resolved policy overrides
            (plain booleans), applied after discovery.
    """

    # loosely mirrors to_toml_dict structure with JSON-friendly types
    fields: dict[str, str]
    header: dict[str, list[str]]
    formatting: dict[str, Any]
    writer: dict[str, Any]
    files: dict[str, Any]
    policy: dict[str, Any]
    policy_by_type: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict of the `ConfigPayload` instance."""
        return {
            "fields": self.fields,
            "header": self.header,
            "formatting": self.formatting,
            "writer": self.writer,
            "files": self.files,
            "policy": self.policy,
            "policy_by_type": self.policy_by_type,
        }


@dataclass(slots=True)
class ConfigDiagnosticsPayload:
    """Machine-readable diagnostics collected while building the `Config`.

    This represents the diagnostics for the [`Config`][topmark.config.model.Config]
    as the diagnostics (list) and stats (counts per severity level).

    Attributes:
        diagnostics (list[ConfigDiagnosticEntry]): list of {level, message} entries.
        diagnostic_counts (ConfigDiagnosticCounts): aggregate per-level counts.
    """

    diagnostics: list[ConfigDiagnosticEntry]
    diagnostic_counts: ConfigDiagnosticCounts

    def to_dict(self) -> Mapping[str, object]:
        """Return a JSON-friendly mapping of the `ConfigDiagnosticsPayload` instance.

        Returns:
            Mapping[str, object]: Mapping with keys `"diagnostics"` and `"diagnostic_counts"`,
                representing config diagnostics ()`list[ConfigDiagnosticEntry]`) and the
                config diagnostic counts per diagnostic severity level.
        """
        return {
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "diagnostic_counts": self.diagnostic_counts.to_dict(),
        }


@dataclass(slots=True)
class ConfigCheckSummary:
    """Summary payload for `topmark config check` machine output.

    Captures the pass/fail outcome of validating the effective configuration
    under the selected strictness, plus diagnostic counts and the resolved
    list of config files contributing to the final config.

    Emitted as:
    - JSON: top-level `summary` payload in the JSON envelope.
    - NDJSON: `kind="summary"` record (payload container `summary`).

    Attributes:
        command (str): Top-level command name (typically "config").
        subcommand (str): Subcommand name (typically "check").
        ok (bool): True when validation succeeded under the selected strictness.
        strict (bool): True when warnings are treated as failures.
        diagnostic_counts (ConfigDiagnosticCounts): Counts per diagnostic level.
        config_files (list[str]): Resolved list of loaded config file paths.
    """

    command: str  # "config"
    subcommand: str  # "check"
    ok: bool
    strict: bool
    diagnostic_counts: ConfigDiagnosticCounts
    config_files: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly dict of the `ConfigCheckSummary` instance.

        Returns:
            dict[str, object]: JSON-friendly dict representing the `ConfigCheckSummary` instance.
        """
        return {
            MachineKey.COMMAND: self.command,
            MachineKey.SUBCOMMAND: self.subcommand,
            MachineKey.OK: self.ok,
            MachineKey.STRICT: self.strict,
            MachineKey.DIAGNOSTIC_COUNTS: self.diagnostic_counts.to_dict(),
            MachineKey.CONFIG_FILES: self.config_files,
        }
