# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/config/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Schema objects for config-related machine output.

This module defines small dataclasses used as the *typed payload layer* for
config-related JSON/NDJSON output. Instances are designed to be trivially
JSON-serializable via `to_dict()`.

Shape construction and serialization are handled by:
  - [`topmark.config.machine.payloads`][topmark.config.machine.payloads] (payload builders)
  - [`topmark.config.machine.shapes`][topmark.config.machine.shapes] (envelope/record builders)
  - [`topmark.config.machine.serializers`][topmark.config.machine.serializers]
    (JSON/NDJSON string rendering)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from topmark.core.machine.schemas import MachineKey

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.diagnostic.machine.schemas import (
        MachineDiagnosticCounts,
        MachineDiagnosticEntry,
    )


@dataclass(slots=True)
class ConfigPayload:
    """JSON-friendly representation of the effective TopMark configuration.

    The shape loosely mirrors
    [`Config.to_toml_dict(include_files=False)`][topmark.config.model.Config.to_toml_dict]
    but guarantees JSON-serializable values (paths/enums normalized to strings).

    Diagnostics are emitted separately via `ConfigDiagnosticsPayload`.

    Attributes:
        fields: Available header fields.
        header: TODO.
        formatting: TODO.
        writer: TODO.
        files: List of files to process.
        policy: Global, resolved, immutable runtime policy (plain booleans),
            applied after discovery.
        policy_by_type: Per-file-type resolved policy overrides
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
        diagnostics: list of {level, message} entries.
        diagnostic_counts: aggregate per-level counts.
    """

    diagnostics: list[MachineDiagnosticEntry]
    diagnostic_counts: MachineDiagnosticCounts

    def to_dict(self) -> Mapping[str, object]:
        """Return a JSON-friendly mapping of diagnostics and diagnostic counts.

        Returns:
            Mapping with keys `"diagnostics"` and `"diagnostic_counts"`,
            representing config diagnostics (`list[MachineDiagnosticEntry]`) and the
            config diagnostic counts per severity level (`MachineDiagnosticCounts`).
        """
        return {
            MachineKey.DIAGNOSTICS: [d.to_dict() for d in self.diagnostics],
            MachineKey.DIAGNOSTIC_COUNTS: self.diagnostic_counts.to_dict(),
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
        command: Top-level command name (typically "config").
        subcommand: Subcommand name (typically "check").
        ok: True when validation succeeded under the selected strictness.
        strict: True when warnings are treated as failures.
        diagnostic_counts: Counts per diagnostic level.
        config_files: Resolved list of loaded config file paths.
    """

    command: str  # "config"
    subcommand: str  # "check"
    ok: bool
    strict: bool
    diagnostic_counts: MachineDiagnosticCounts
    config_files: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly dict of the `ConfigCheckSummary` instance.

        Returns:
            JSON-friendly dict representing the `ConfigCheckSummary` instance.
        """
        return {
            MachineKey.COMMAND: self.command,
            MachineKey.SUBCOMMAND: self.subcommand,
            MachineKey.OK: self.ok,
            MachineKey.STRICT: self.strict,
            MachineKey.DIAGNOSTIC_COUNTS: self.diagnostic_counts.to_dict(),
            MachineKey.CONFIG_FILES: self.config_files,
        }
