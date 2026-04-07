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

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypedDict
from typing import cast


class MachineKey(str, Enum):
    """Stable keys shared by all machine-output envelopes.

    These keys are intentionally limited to the shared envelope layer and other
    cross-domain fields that multiple machine-output domains rely on. Domain-
    specific payload keys belong in the corresponding `*.machine.schemas`
    module.

    Attributes:
        KIND: Top-level record kind key used by NDJSON records.
        META: Top-level metadata key shared by JSON and NDJSON machine output.
        DOMAIN: Stable diagnostic domain key used by diagnostic payloads.
        COMMAND: Top-level command name for command-summary style payloads.
        SUBCOMMAND: Optional subcommand name for command-summary style payloads.
    """

    KIND = "kind"
    META = "meta"

    # diagnostics (cross-domain)
    DOMAIN = "domain"

    # CLI context
    COMMAND = "command"
    SUBCOMMAND = "subcommand"


class MachineMetaKey(str, Enum):
    """Stable keys for the shared machine-output metadata payload.

    Attributes:
        TOOL: Executable/tool name.
        VERSION: TopMark version string.
        PLATFORM: Execution platform identifier.
    """

    TOOL = "tool"
    VERSION = "version"
    PLATFORM = "platform"


class MachineDomain(str, Enum):
    """Stable diagnostic domains shared across machine-output emitters.

    These values are used as the payload value for the envelope-level
    `MachineKey.DOMAIN` key when emitting machine-readable diagnostics.

    Attributes:
        CONFIG: Diagnostics originating from config discovery or validation.
        PIPELINE: Diagnostics originating from processing-pipeline execution.
        REGISTRY: Diagnostics originating from registry inspection commands.
        VERSION: Diagnostics originating from version computation/rendering.
    """

    CONFIG = "config"
    PIPELINE = "pipeline"
    REGISTRY = "registry"
    VERSION = "version"


class DetailLevel(str, Enum):
    """Enumeration of supported machine-output detail levels.

    These values describe how much information is included in a payload and are
    intended for **machine consumers**.

    Attributes:
        BRIEF: Minimal representation (default CLI behavior).
        LONG: Expanded representation including additional identity and
            descriptive fields (triggered via `--long`).

    Notes:
        - This is a machine-facing concept; it should not be confused with
          human-facing verbosity levels.
        - Consumers should rely on this field instead of inferring structure
          from payload shape.
    """

    BRIEF = "brief"
    LONG = "long"


@dataclass(slots=True, frozen=True, kw_only=True)
class CommandSummary:
    """Identifies the TopMark command context for a machine-output record.

    Attributes:
        command: Top-level command name (e.g. `"config"`, `"check"`, `"strip"`).
        subcommand: Optional subcommand name (e.g. `"check"` under `"config"`).
    """

    command: str
    subcommand: str | None = None


class MetaPayload(TypedDict, total=True):
    """Base metadata describing the TopMark runtime environment for machine output.

    This payload is process-stable and shared across all machine-output commands.

    Attributes:
        tool: Name of the tool (e.g. "topmark").
        version: Tool version string.
        platform: Execution platform (e.g. "darwin", "linux").
    """

    tool: str
    version: str
    platform: str


class DetailedMetaPayload(MetaPayload, total=True):
    """Extended metadata for machine output envelopes and records.

    This structure extends [`MetaPayload`] with fields that vary per command
    invocation (e.g. `--long`).

    Attributes:
        detail_level: Indicates whether the payload represents a brief or
            detailed projection of the underlying data.

    Notes:
        Inherits the base metadata fields from `MetaPayload`:
        `tool`, `version`, and `platform`.
    """

    detail_level: DetailLevel


# ---- Payload normalization ----


def normalize_payload(obj: object) -> object:
    """Normalize a payload into JSON-serializable structures.

    Conversions:
      - `Path` -> `str`
      - `Enum`:
        - `str`-backed Enum (e.g. StrEnum) -> `value`
        - other Enum -> `name`
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
        if isinstance(obj, str):
            # StrEnum → use value (already a str)
            return obj
        # non-str Enum → use name
        return obj.name

    to_dict_obj: object = getattr(obj, "to_dict", None)
    if callable(to_dict_obj):
        to_dict_func: Callable[[], object] = to_dict_obj
        return normalize_payload(to_dict_func())

    if isinstance(obj, Mapping):
        mapping = cast("Mapping[object, object]", obj)
        return {str(key): normalize_payload(value) for key, value in mapping.items()}

    if isinstance(obj, list | tuple | set | frozenset):
        values = cast("Iterable[object]", obj)
        return [normalize_payload(value) for value in values]

    return obj
