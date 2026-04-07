# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/toml/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Schema dataclasses for TOML-domain machine output.

This module defines strongly typed, JSON-friendly payload dataclasses used for
machine-readable TOML provenance output.

Responsibilities:
  - Represent ordered TOML provenance layers for config inspection output.
  - Serialize TOML provenance payloads using stable TOML-domain keys.

This module performs no I/O and does not build JSON envelopes or NDJSON
records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TomlKey(str, Enum):
    """Stable keys for TOML provenance payload fragments.

    These keys are owned by the TOML machine-output domain. They describe the
    inner schema of provenance-layer fragments and the outer `config_layers`
    container emitted for TOML provenance payloads.

    Attributes:
        CONFIG_LAYERS: Container key for ordered provenance layers.
        LAYER_KIND: Key describing the resolved provenance-layer kind.
        ORIGIN: Source label for the provenance layer.
        PRECEDENCE: Numeric layer precedence.
        TOML: Nested TopMark TOML fragment for the layer.
        SCOPE_ROOT: Optional scope root attached to the layer.
    """

    CONFIG_LAYERS = "config_layers"
    LAYER_KIND = "layer_kind"
    ORIGIN = "origin"
    PRECEDENCE = "precedence"
    TOML = "toml"
    SCOPE_ROOT = "scope_root"


@dataclass(slots=True, kw_only=True)
class TomlProvenanceLayerPayload:
    """One machine-readable TOML provenance layer.

    Attributes:
        origin: Provenance origin label for the layer.
        kind: Resolved config-layer kind value.
        precedence: Layer precedence, where lower values apply earlier.
        toml: Source-local TopMark TOML fragment for this layer.
        scope_root: Optional scope root associated with the layer.
    """

    origin: str
    kind: str
    precedence: int
    toml: dict[str, object]
    scope_root: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the layer payload as a JSON-friendly mapping.

        Returns:
            A dict using stable TOML-domain machine keys.
        """
        out: dict[str, object] = {
            TomlKey.ORIGIN.value: self.origin,
            TomlKey.LAYER_KIND.value: self.kind,
            TomlKey.PRECEDENCE.value: self.precedence,
            TomlKey.TOML.value: self.toml,
        }
        if self.scope_root is not None:
            out[TomlKey.SCOPE_ROOT.value] = self.scope_root
        return out


@dataclass(slots=True, kw_only=True)
class TomlProvenancePayload:
    """Machine-readable layered TopMark TOML provenance export.

    Attributes:
        layers: Ordered provenance layers, starting with the built-in defaults
            layer when present.
    """

    layers: list[TomlProvenanceLayerPayload]

    def to_dict(self) -> dict[str, object]:
        """Return the provenance payload as a JSON-friendly mapping.

        Returns:
            A dict containing the ordered `config_layers` export.
        """
        return {
            TomlKey.CONFIG_LAYERS.value: [layer.to_dict() for layer in self.layers],
        }
