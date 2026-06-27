# topmark:header:start
#
#   project      : TopMark
#   file         : test_toml_machine_payloads.py
#   file_relpath : tests/toml/machine/test_toml_machine_payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for TOML-domain machine payload builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.toml.keys import Toml
from topmark.toml.machine.payloads import build_toml_provenance_payload
from topmark.toml.parse import ParsedTopmarkToml
from topmark.toml.parse import SourceConfigLoadingOptions
from topmark.toml.parse import SourceTomlOptions
from topmark.toml.resolution import ResolvedTopmarkTomlSource
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.schema import TOPMARK_TOML_SCHEMA
from topmark.toml.schema import TomlSection
from topmark.toml.schema import TomlValidationMode
from topmark.toml.validation import TomlDiagnosticCode

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.toml.machine.schemas import TomlProvenanceLayerPayload
    from topmark.toml.machine.schemas import TomlProvenancePayload
    from topmark.toml.types import TomlTable
    from topmark.toml.validation import TomlValidationIssue


def test_toml_provenance_payload_uses_posix_paths_for_file_backed_layers(
    tmp_path: Path,
) -> None:
    """TOML provenance should serialize real source paths POSIX-style."""
    config_file: Path = tmp_path / "workspace" / "topmark.toml"
    config_file.parent.mkdir(parents=True)
    toml_fragment: TomlTable = {
        Toml.SECTION_FIELDS: {
            "project": "Demo",
        },
        Toml.SECTION_HEADER: {
            Toml.KEY_FIELDS: ["project"],
        },
    }
    parsed = ParsedTopmarkToml(
        config_loading_options=SourceConfigLoadingOptions(),
        layered_config=toml_fragment,
        writer_options=None,
        source_options=SourceTomlOptions(),
        toml_fragment=toml_fragment,
    )
    resolved = ResolvedTopmarkTomlSources(
        discovery_anchor=config_file.parent,
        sources=[
            ResolvedTopmarkTomlSource(
                path=config_file,
                parsed=parsed,
                kind="explicit",
                validation_issues=(),
                load_diagnostics=MutableDiagnosticLog().freeze(),
            ),
        ],
        writer_options=None,
        strict=None,
    )

    payload: TomlProvenancePayload = build_toml_provenance_payload(resolved)

    file_backed_layers: list[TomlProvenanceLayerPayload] = [
        layer for layer in payload.layers if layer.origin == config_file.as_posix()
    ]
    assert len(file_backed_layers) == 1
    file_backed_layer: TomlProvenanceLayerPayload = file_backed_layers[0]
    assert file_backed_layer.scope_root == config_file.parent.as_posix()
    assert file_backed_layer.toml[Toml.SECTION_FIELDS] == {"project": "Demo"}


def test_toml_provenance_payload_uses_posix_path_for_discovery_anchor(
    tmp_path: Path,
) -> None:
    """TOML provenance should serialize the discovery anchor POSIX-style."""
    workspace: Path = tmp_path / "workspace"
    resolved = ResolvedTopmarkTomlSources(
        sources=[],
        writer_options=None,
        strict=None,
        discovery_anchor=workspace,
    )

    payload: TomlProvenancePayload = build_toml_provenance_payload(resolved)

    assert payload.discovery_anchor == workspace.as_posix()
    assert payload.to_dict()["discovery_anchor"] == workspace.as_posix()


def test_toml_schema_accepts_dump_only_keys_in_provenance_mode() -> None:
    """Provenance validation should accept dump-only schema keys."""
    issues: tuple[TomlValidationIssue, ...] = TOPMARK_TOML_SCHEMA.validate_section_keys(
        TomlSection.CONFIG,
        {Toml.KEY_CONFIG_FILES: ["/workspace/topmark.toml"]},
        mode=TomlValidationMode.PROVENANCE,
    )

    assert issues == ()


def test_toml_schema_rejects_dump_only_keys_in_input_mode() -> None:
    """Input validation should reject dump-only schema keys."""
    issues: tuple[TomlValidationIssue, ...] = TOPMARK_TOML_SCHEMA.validate_section_keys(
        TomlSection.CONFIG,
        {Toml.KEY_CONFIG_FILES: ["/workspace/topmark.toml"]},
        mode=TomlValidationMode.INPUT,
    )

    assert len(issues) == 1
    assert issues[0].code is TomlDiagnosticCode.DUMP_ONLY_KEY_IN_INPUT
    assert issues[0].path == (TomlSection.CONFIG.value, Toml.KEY_CONFIG_FILES)
