# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/toml/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output schema dataclasses for TOML provenance exports.

This module defines strongly typed, JSON-friendly payload dataclasses used for
machine-readable TOML provenance output.

Responsibilities:
  - Represent ordered TOML provenance layers for config inspection output.
  - Serialize TOML provenance payloads using stable machine-output keys.

This module performs no I/O and does not build envelopes or records.
"""

from __future__ import annotations

from dataclasses import dataclass

from topmark.core.machine.schemas import MachineKey


@dataclass(slots=True, kw_only=True)
class TomlProvenanceLayerPayload:
    """One machine-readable TOML provenance layer.

    Attributes:
        origin: Provenance origin label for the layer.
        kind: Resolved config layer kind value.
        precedence: Layer precedence (lower applied earlier).
        toml: Source-local TopMark TOML fragment for this layer.
        scope_root: Optional scope root associated with the layer.
    """

    origin: str
    kind: str
    precedence: int
    toml: dict[str, object]
    scope_root: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly dict of the layer payload."""
        out: dict[str, object] = {
            "origin": self.origin,
            MachineKey.KIND: self.kind,
            "precedence": self.precedence,
            "toml": self.toml,
        }
        if self.scope_root is not None:
            out["scope_root"] = self.scope_root
        return out


@dataclass(slots=True, kw_only=True)
class TomlProvenancePayload:
    """Machine-readable layered TopMark TOML provenance export.

    Attributes:
        layers: Ordered provenance layers, starting with built-in defaults.
    """

    layers: list[TomlProvenanceLayerPayload]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly dict of the provenance payload."""
        return {
            MachineKey.CONFIG_LAYERS: [layer.to_dict() for layer in self.layers],
        }
