# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/core/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Canonical schema primitives for TopMark machine output.

This module centralizes:
- canonical *keys* used in JSON envelopes and NDJSON records (`MachineKey`)
- canonical NDJSON *kinds* (`MachineKind`)
- canonical diagnostic *domains* (`MachineDomain`)
- helper types used across machine formats (`MetaPayload`, `CommandSummary`)
- payload normalization (`normalize_payload`)

Design goals:
- Pure (no Click / no Console / no serialization side-effects).
- Stable, shared constants to avoid “stringly-typed” drift across commands.
- Conservative normalization to keep payload shaping predictable.

Normalization rules:
- `Path` -> `str`
- `Enum` -> `Enum.name`
- objects with `.to_dict()` -> normalize of that mapping
- mappings -> dict with stringified keys and normalized values
- sequences/sets -> lists of normalized values
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Final, TypedDict, cast


@dataclass(slots=True)
class CommandSummary:
    """Identifies the TopMark command context for a machine-output record.

    Attributes:
        command: Top-level command name (e.g. `"config"`, `"check"`, `"strip"`).
        subcommand: Optional subcommand name (e.g. `"check"` under `"config"`).
    """

    command: str
    subcommand: str | None = None


class MachineKey:
    """Canonical keys used in machine-readable JSON/NDJSON envelopes.

    These are shared constants to avoid stringly-typed key drift across emitters.
    """

    KIND: Final[str] = "kind"
    META: Final[str] = "meta"

    # standard payload container keys
    CONFIG: Final[str] = "config"
    CONFIG_DIAGNOSTICS: Final[str] = "config_diagnostics"
    CONFIG_FILES: Final[str] = "config_files"
    DIAGNOSTIC: Final[str] = "diagnostic"
    SUMMARY: Final[str] = "summary"
    # Single processing result (NDJSON)
    RESULT: Final[str] = "result"
    # List of processing results (JSON)
    RESULTS: Final[str] = "results"

    # common fields
    DOMAIN: Final[str] = "domain"
    LEVEL: Final[str] = "level"
    MESSAGE: Final[str] = "message"

    COMMAND: Final[str] = "command"
    SUBCOMMAND: Final[str] = "subcommand"

    DIAGNOSTICS: Final[str] = "diagnostics"
    DIAGNOSTIC_COUNTS: Final[str] = "diagnostic_counts"

    # Config checking
    OK: Final[str] = "ok"
    STRICT: Final[str] = "strict"

    # Version
    VERSION: Final[str] = "version"
    VERSION_INFO: Final[str] = "version_info"
    VERSION_FORMAT: Final[str] = "version_format"

    # Generic result status (optional; command-specific usage)
    STATUS: Final[str] = "status"
    ERROR: Final[str] = "error"

    # Registry
    FILETYPES: Final[str] = "filetypes"
    PROCESSORS: Final[str] = "processors"
    UNBOUND_FILETYPES: Final[str] = "unbound_filetypes"


class MachineKind:
    """Canonical `kind` values for NDJSON records."""

    CONFIG: Final[str] = "config"
    CONFIG_DIAGNOSTICS: Final[str] = "config_diagnostics"
    DIAGNOSTIC: Final[str] = "diagnostic"
    SUMMARY: Final[str] = "summary"
    RESULT: Final[str] = "result"
    VERSION: Final[str] = "version"

    # Registry
    FILETYPE: Final[str] = "filetype"
    PROCESSOR: Final[str] = "processor"
    UNBOUND_FILETYPE: Final[str] = "unbound_filetype"


class MachineMeta:
    """Canonical keys used in MetaPayload (identified by `MachineKey.META`) (metadata)."""

    TOOL: Final[str] = "tool"
    VERSION: Final[str] = "version"
    PLATFORM: Final[str] = "platform"


class MachineDomain:
    """Canonical values for `MachineKey.DOMAIN` (diagnostics)."""

    CONFIG: Final[str] = "config"
    VERSION: Final[str] = "version"
    REGISTRY: Final[str] = "registry"


class MetaPayload(TypedDict):
    """Metadata describing the TopMark runtime environment for machine output."""

    tool: str
    version: str
    platform: str


# --- Validation helpers ---

# These sets are primarily used for guarding against accidental typos in builders.
# Payload-specific keys are intentionally extensible, so only a core set is listed.
_KNOWN_KEYS: Final[set[str]] = {
    MachineKey.KIND,
    MachineKey.META,
    MachineKey.CONFIG,
    MachineKey.CONFIG_DIAGNOSTICS,
    MachineKey.CONFIG_FILES,
    MachineKey.DIAGNOSTIC,
    MachineKey.SUMMARY,
    MachineKey.RESULT,
    MachineKey.RESULTS,
    MachineKey.DOMAIN,
    MachineKey.LEVEL,
    MachineKey.MESSAGE,
    MachineKey.COMMAND,
    MachineKey.SUBCOMMAND,
    MachineKey.DIAGNOSTIC_COUNTS,
    MachineKey.OK,
    MachineKey.STRICT,
    MachineKey.VERSION,
    MachineKey.VERSION_INFO,
    MachineKey.VERSION_FORMAT,
    MachineKey.STATUS,
    MachineKey.ERROR,
    MachineKey.FILETYPES,
    MachineKey.PROCESSORS,
    MachineKey.UNBOUND_FILETYPES,
}
_KNOWN_KINDS: Final[set[str]] = {
    MachineKind.CONFIG,
    MachineKind.CONFIG_DIAGNOSTICS,
    MachineKind.DIAGNOSTIC,
    MachineKind.SUMMARY,
    MachineKind.RESULT,
    MachineKind.VERSION,
    MachineKind.FILETYPE,
    MachineKind.PROCESSOR,
    MachineKind.UNBOUND_FILETYPE,
}


def validate_machine_key(key: str) -> None:
    """Validate that `key` looks like a usable machine-output key.

    This is a lightweight guard aimed at catching obvious mistakes (e.g. empty strings).
    The machine schema is intentionally extensible, so unknown payload keys are not
    rejected by default.

    Args:
        key: Candidate key string.

    Raises:
        ValueError: If `key` is empty.
    """
    # NOTE: “keys” are trickier because payload keys are intentionally extensible.
    # Conwider validating the envelope keys (kind, meta) + a small set of top-level payload names
    # considered canonical.
    # if key not in _KNOWN_KEYS:
    #     raise ValueError(f"Unknown machine key '{key}' - valid choices: {', '.join(_KNOWN_KEYS)}")
    if not key:
        raise ValueError("machine key must be a non-empty string")


def validate_machine_kind(kind: str) -> None:
    """Validate that `kind` is a known machine record kind.

    Args:
        kind: Candidate kind string.

    Raises:
        ValueError: If `kind` is empty or not a known kind.
    """
    if not kind:
        raise ValueError("machine kind must be a non-empty string")
    if kind not in _KNOWN_KINDS:
        raise ValueError(
            f"Unknown machine kind '{kind}' - valid choices: {', '.join(_KNOWN_KINDS)}"
        )


def normalize_payload(obj: object) -> object:
    """Normalize a payload into JSON-serializable structures.

    Conversions:
      - `Path` -> `str`
      - `Enum` -> `Enum.name`
      - object with callable `.to_dict()` -> normalize(`.to_dict()`)
      - `Mapping` -> `dict[str, normalized value]`
      - `list/tuple/set/frozenset` -> `list[normalized item]`

    Notes:
      - This function is intentionally conservative. It does not attempt arbitrary
        dataclass conversion; payload objects should implement `to_dict()` if they
        want custom serialization.
      - Mapping keys are stringified to keep JSON object keys valid.

    Args:
        obj: The payload object to normalize.

    Returns:
        A JSON-serializable representation of `obj`.
    """
    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, Enum):
        return obj.name

    to_dict: Any | None = getattr(obj, "to_dict", None)
    if callable(to_dict):
        # Allow payload objects (e.g., dataclasses) to define their own
        # JSON-friendly representation.
        return normalize_payload(to_dict())

    if isinstance(obj, (dict, Mapping)):
        # Safe: `value` is a Mapping after the isinstance check; we treat keys
        # as generic objects and values as Any for JSONification purposes.
        mapping: Mapping[object, Any] = cast("Mapping[object, Any]", obj)
        return {str(k): normalize_payload(v) for k, v in mapping.items()}

    if isinstance(obj, (list, tuple, set, frozenset)):
        # Safe: `value` is a collection after the isinstance check; iterate as objects.
        seq: Iterator[object] = cast("Iterator[object]", obj)
        return [normalize_payload(v) for v in seq]

    return obj
