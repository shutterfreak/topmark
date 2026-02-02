# topmark:header:start
#
#   project      : TopMark
#   file         : formats.py
#   file_relpath : src/topmark/core/machine/formats.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared machine-output envelope conventions for TopMark.

This module defines the canonical keys and kind values used across TopMark's
machine-readable output formats (JSON and NDJSON).

It is intentionally Click/console-free so it can be reused by any frontend.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Final, TypedDict, cast

from topmark.constants import TOPMARK_VERSION


class MachineKey:
    """Canonical keys used in machine-readable JSON/NDJSON output envelopes.

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
    RESULT: Final[str] = "result"

    # common fields
    DOMAIN: Final[str] = "domain"
    LEVEL: Final[str] = "level"
    MESSAGE: Final[str] = "message"

    COMMAND: Final[str] = "command"
    SUBCOMMAND: Final[str] = "subcommand"

    DIAGNOSTIC_COUNTS: Final[str] = "diagnostic_counts"

    # Config checking
    OK: Final[str] = "ok"
    STRICT: Final[str] = "strict"


class MachineKind:
    """Canonical `kind` values for NDJSON records."""

    CONFIG: Final[str] = "config"
    CONFIG_DIAGNOSTICS: Final[str] = "config_diagnostics"
    DIAGNOSTIC: Final[str] = "diagnostic"
    SUMMARY: Final[str] = "summary"
    RESULT: Final[str] = "result"


class MetaPayload(TypedDict):
    """Metadata describing the TopMark runtime environment for machine output."""

    tool: str
    version: str


# --- Schema-ish helpers ---

_KNOWN_KEYS: Final[set[str]] = {
    MachineKey.KIND,
    MachineKey.META,
    MachineKey.CONFIG,
    MachineKey.CONFIG_DIAGNOSTICS,
    MachineKey.CONFIG_FILES,
    MachineKey.DIAGNOSTIC,
    MachineKey.SUMMARY,
    MachineKey.RESULT,
    MachineKey.DOMAIN,
    MachineKey.LEVEL,
    MachineKey.MESSAGE,
    MachineKey.COMMAND,
    MachineKey.SUBCOMMAND,
    MachineKey.DIAGNOSTIC_COUNTS,
    MachineKey.OK,
    MachineKey.STRICT,
}

_KNOWN_KINDS: Final[set[str]] = {
    MachineKind.CONFIG,
    MachineKind.CONFIG_DIAGNOSTICS,
    MachineKind.DIAGNOSTIC,
    MachineKind.SUMMARY,
    MachineKind.RESULT,
}


def validate_machine_key(key: str) -> None:
    """Validate that `key` is a known machine envelope key.

    Lightweight guard to catch typos in emitters/builders.
    Payload-specific keys are intentionally not exhaustively validated here.
    """
    if not key:
        raise ValueError("machine key must be a non-empty string")
    # NOTE: “keys” are trickier because payload keys are intentionally extensible.
    # Conwider validating the envelope keys (kind, meta) + a small set of top-level payload names
    # considered canonical.
    # if key not in _KNOWN_KEYS:
    #     raise ValueError(f"Unknown machine key '{key}' - valid choices: {', '.join(_KNOWN_KEYS)}")


def validate_machine_kind(kind: str) -> None:
    """Validate that `kind` is a known machine record kind."""
    if not kind:
        raise ValueError("machine kind must be a non-empty string")
    if kind not in _KNOWN_KINDS:
        raise ValueError(
            f"Unknown machine kind '{kind}' - valid choices: {', '.join(_KNOWN_KINDS)}"
        )


def normalize_payload(obj: object) -> object:
    """Normalize a machine-output payload into JSON-serializable structures.

    Conversions:
      - Path -> str
      - Enum -> Enum.name
      - object with callable .to_dict() -> normalize(.to_dict())
      - Mapping -> dict[str, normalized value]
      - list/tuple/set/frozenset -> list[normalized item]

    Notes:
      - This function is intentionally conservative. It does not attempt
        arbitrary dataclass conversion; payload objects should implement
        `to_dict()` if they want custom serialization.
      - Keys in mappings are stringified to keep JSON object keys valid.

    Rules:
      - Recursively normalize Mapping values and sequence items.
      - Leave primitive types unchanged.

    Args:
        obj (object): The machine-output payload to be transformed into JSON-serializable format.

    Returns:
        object: The JSON-serializable representation of machine-output payload.
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
        seq: Iterable[object] = cast("Iterable[object]", obj)
        return [normalize_payload(v) for v in seq]

    return obj


# --- Payload builders ---


def build_meta_payload() -> MetaPayload:
    """Build a small metadata payload with tool name and version.

    The version is resolved using importlib.metadata for the installed
    "topmark" distribution. If the package cannot be found, the version
    is set to "unknown".
    """
    tool_name: str = "topmark"
    ver: str = TOPMARK_VERSION
    return {"tool": tool_name, "version": ver}


def build_ndjson_record(
    *,
    kind: str,
    meta: MetaPayload,
    container_key: str | None = None,
    payload: object,
) -> dict[str, object]:
    """Build a single NDJSON record with a uniform envelope.

    Contract: every line includes `kind` and `meta`. Prefer omitting `container_key`
    so the container key matches `kind`.

    Shape:
        `{"kind": <kind>, "meta": <meta>, <container_key>: <payload>}` where `<container_key>` is
        `kind` (default), unless overridden by `container_key`.

    Args:
        kind (str): NDJSON record kind.
        meta (MetaPayload): NDJSON payload meta.
        container_key (str | None): Optional payload container key; defaults to `kind`.
        payload (object): The payload object.

    Returns:
        dict[str, object]: the NDJSON record in the correct envelope.

    Notes:
        - This function does **not** JSON-serialize; it only shapes the record.
        - `meta` is typed as Mapping[str, object] to avoid importing CLI-only
          TypedDicts here.
    """
    # Ensure JSON object keys are strings and keep the envelope uniform.
    resolved_payload_name: str = container_key if container_key else kind
    record: dict[str, object] = {
        MachineKey.KIND: kind,
        MachineKey.META: dict(meta),
        resolved_payload_name: normalize_payload(
            payload
        ),  # payload may be a dict or an object with to_dict()
    }
    return record


# --- Record builders ---


def build_json_envelope(
    *,
    meta: Mapping[str, object],
    **payloads: object,
) -> dict[str, object]:
    """Build a JSON envelope with `meta` plus one or more named payloads."""
    out: dict[str, object] = {MachineKey.META: dict(meta)}
    for name, payload in payloads.items():
        out[name] = normalize_payload(payload)
    return out
