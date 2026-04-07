# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/toml/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Payload builders for TOML-domain machine output.

This module contains pure helpers that build strongly typed payload dataclasses
for machine-readable TOML provenance output.

Responsibilities:
  - Convert resolved TOML-side structures into JSON-friendly values.
  - Build payload objects from
    [`topmark.toml.machine.schemas`][topmark.toml.machine.schemas].

This module performs no I/O and does not shape JSON envelopes or NDJSON
records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.io.serializers import config_to_topmark_toml_table
from topmark.config.resolution.layers import ConfigLayerKind
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.core.machine.schemas import normalize_payload
from topmark.core.typing_guards import as_object_dict
from topmark.toml.defaults import build_default_topmark_toml_table
from topmark.toml.machine.schemas import TomlProvenanceLayerPayload
from topmark.toml.machine.schemas import TomlProvenancePayload

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.resolution.layers import ConfigLayer
    from topmark.toml.resolution import ResolvedTopmarkTomlSource
    from topmark.toml.resolution import ResolvedTopmarkTomlSources
    from topmark.toml.types import TomlTable


def _normalize_toml_fragment(fragment: TomlTable) -> dict[str, object]:
    """Normalize one TOML fragment to a JSON-friendly mapping.

    Args:
        fragment: Source-local TopMark TOML fragment.

    Returns:
        A JSON-friendly mapping produced by recursively normalizing TOML values
        (for example, paths and enums) and then narrowing the normalized result
        to an object-like dict.
    """
    normalized: object = normalize_payload(fragment)
    return as_object_dict(normalized)


def build_toml_provenance_payload(
    resolved_toml: ResolvedTopmarkTomlSources,
) -> TomlProvenancePayload:
    """Build a machine-readable layered TOML provenance payload.

    Args:
        resolved_toml: Resolved TOML sources for the current run.

    Returns:
        Provenance payload with ordered layers, starting with the built-in
        defaults layer when present.

    Raises:
        ValueError: If config provenance layers do not align with the resolved
            TOML sources.
        TomlRenderError: If an invalid files serialization mode is specified
            while rendering API- or CLI-originated layers back to TopMark TOML.
    """  # noqa: DOC503
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved_toml.sources
    )

    # Keep payload layers aligned with the resolved/config-derived layer order so
    # the machine-readable provenance view mirrors the effective precedence model.
    out_layers: list[TomlProvenanceLayerPayload] = []
    # File-backed sources are consumed only for non-synthetic layers. Synthetic
    # default/API/CLI layers are reconstructed directly from the in-memory config.
    remaining_sources: Iterator[ResolvedTopmarkTomlSource] = iter(resolved_toml.sources)

    for layer in layers:
        scope_root: str | None = str(layer.scope_root) if layer.scope_root is not None else None

        if layer.kind == ConfigLayerKind.DEFAULT:
            toml_fragment: dict[str, object] = _normalize_toml_fragment(
                build_default_topmark_toml_table()
            )
        elif layer.kind in {ConfigLayerKind.API, ConfigLayerKind.CLI}:
            toml_fragment = _normalize_toml_fragment(
                config_to_topmark_toml_table(layer.config.freeze()),
            )  # May raise TomlRenderError for invalid file-serialization settings.
        else:
            source: ResolvedTopmarkTomlSource | None = next(remaining_sources, None)
            if source is None:
                raise ValueError("config provenance layers do not align with resolved TOML sources")
            toml_fragment = _normalize_toml_fragment(source.parsed.toml_fragment)

        out_layers.append(
            TomlProvenanceLayerPayload(
                origin=str(layer.origin),
                kind=layer.kind.value,
                precedence=layer.precedence,
                scope_root=scope_root,
                toml=toml_fragment,
            )
        )

    return TomlProvenancePayload(layers=out_layers)
