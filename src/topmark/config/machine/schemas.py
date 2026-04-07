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
  - [`topmark.config.machine.envelopes`][topmark.config.machine.envelopes] (envelope/record
    builders)
  - [`topmark.config.machine.serializers`][topmark.config.machine.serializers]
    (JSON/NDJSON string rendering)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.core.machine.schemas import MachineKey
from topmark.diagnostic.machine.schemas import DiagnosticKey
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts
    from topmark.diagnostic.machine.schemas import MachineDiagnosticEntry

from enum import Enum


class ConfigKey(str, Enum):
    """Stable config-domain keys for machine-readable payloads.

    These keys belong to the config machine-output domain and should be used for
    config-specific JSON payload members and NDJSON container keys. Shared
    envelope keys remain in `topmark.core.machine.schemas`, while shared
    diagnostic keys live in `topmark.diagnostic.machine.schemas`.

    Attributes:
        CONFIG: Container key for the effective config payload.
        CONFIG_PROVENANCE: Container key for layered config provenance output.
        CONFIG_LAYERS: Container key for ordered TOML/config provenance layers.
        CONFIG_DIAGNOSTICS: Container key for config diagnostic summary payloads.
        CONFIG_FILES: Key for the resolved list of config files.
        CONFIG_CHECK: Container key for `topmark config check` summary payloads.
        OK: Boolean success field for config-check summaries.
        STRICT_CONFIG_CHECKING: Whether warnings are treated as failures.
    """

    CONFIG = "config"
    CONFIG_PROVENANCE = "config_provenance"
    CONFIG_LAYERS = "config_layers"
    CONFIG_DIAGNOSTICS = "config_diagnostics"
    CONFIG_FILES = "config_files"
    CONFIG_CHECK = "config_check"

    OK = "ok"
    STRICT_CONFIG_CHECKING = "strict_config_checking"


class ConfigKind(str, Enum):
    """Stable NDJSON kinds emitted by the config machine-output domain.

    Attributes:
        CONFIG: Effective config record.
        CONFIG_PROVENANCE: Config provenance record.
        CONFIG_LAYER: Single provenance-layer record.
        CONFIG_DIAGNOSTICS: Config diagnostic-summary record.
        CONFIG_CHECK: Config-check summary record.
    """

    CONFIG = "config"
    CONFIG_PROVENANCE = "config_provenance"
    CONFIG_LAYER = "config_layer"
    CONFIG_DIAGNOSTICS = "config_diagnostics"
    CONFIG_CHECK = "config_check"


@dataclass(slots=True, kw_only=True)
class ConfigPayload:
    """JSON-friendly representation of the effective TopMark configuration.

    The shape loosely mirrors
    [`config_to_topmark_toml_table(include_files=False)`][topmark.config.io.serializers.config_to_topmark_toml_table]
    but guarantees JSON-serializable values (paths/enums normalized to strings).

    Diagnostics are emitted separately via `ConfigDiagnosticsPayload`.

    Attributes:
        fields: Available header fields and related settings (e.g. `relative_to`).
        header: Contains the ordered list of headers fields to render in TopMark headers.
        formatting: Contains header formatting settings.
        files: List of files to process.
        policy: Global, resolved, immutable runtime policy (plain booleans),
            applied after discovery.
        policy_by_type: Per-file-type resolved policy overrides
            (plain booleans), applied after discovery.
    """

    # loosely mirrors to_toml_dict structure with JSON-friendly types
    fields: dict[str, str]
    header: dict[str, list[str]]
    formatting: dict[str, object]
    files: dict[str, object]
    policy: dict[str, object]
    policy_by_type: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly dict of the `ConfigPayload` instance."""
        return {
            Toml.SECTION_FIELDS: self.fields,
            Toml.SECTION_HEADER: self.header,
            Toml.SECTION_FORMATTING: self.formatting,
            Toml.SECTION_FILES: self.files,
            Toml.SECTION_POLICY: self.policy,
            Toml.SECTION_POLICY_BY_TYPE: self.policy_by_type,
        }


@dataclass(slots=True, kw_only=True)
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
            DiagnosticKey.DIAGNOSTICS.value: [d.to_dict() for d in self.diagnostics],
            DiagnosticKey.DIAGNOSTIC_COUNTS.value: self.diagnostic_counts.to_dict(),
        }


@dataclass(slots=True, kw_only=True)
class ConfigCheckSummary:
    """Summary payload for `topmark config check` machine output.

    Captures the pass/fail outcome of validating the effective configuration
    under the selected strictness, plus diagnostic counts and the resolved
    list of config files contributing to the final config.

    Emitted as:
    - JSON: top-level `config_check` payload in the JSON envelope.
    - NDJSON: `kind="config_check"` record (payload container `config_check`).

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
            MachineKey.COMMAND.value: self.command,
            MachineKey.SUBCOMMAND.value: self.subcommand,
            ConfigKey.OK.value: self.ok,
            ConfigKey.STRICT_CONFIG_CHECKING.value: self.strict,
            DiagnosticKey.DIAGNOSTIC_COUNTS.value: self.diagnostic_counts.to_dict(),
            ConfigKey.CONFIG_FILES.value: self.config_files,
        }
