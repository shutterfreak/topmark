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

import pytest

import topmark.toml.machine.payloads as toml_payloads
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.resolution.layers import ConfigLayer
from topmark.config.resolution.layers import ConfigLayerKind
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.typing_guards import is_mapping
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

    from topmark.config.model import MutableConfig
    from topmark.toml.machine.schemas import TomlProvenanceLayerPayload
    from topmark.toml.machine.schemas import TomlProvenancePayload
    from topmark.toml.types import TomlTable
    from topmark.toml.validation import TomlValidationIssue


def _parsed_toml_fragment(toml_fragment: TomlTable) -> ParsedTopmarkToml:
    """Return a split-parsed TOML source for a test fragment."""
    return ParsedTopmarkToml(
        config_loading_options=SourceConfigLoadingOptions(),
        layered_config=toml_fragment,
        writer_options=None,
        source_options=SourceTomlOptions(),
        toml_fragment=toml_fragment,
    )


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
    parsed: ParsedTopmarkToml = _parsed_toml_fragment(toml_fragment)
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


def test_toml_provenance_payload_renders_synthetic_api_and_cli_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TOML provenance should render API and CLI config layers from config state."""
    api_config: MutableConfig = mutable_config_from_defaults()
    api_config.field_values["project"] = "API Demo"

    cli_config: MutableConfig = mutable_config_from_defaults()
    cli_config.field_values["project"] = "CLI Demo"

    def _build_layers(
        sources: list[ResolvedTopmarkTomlSource],
    ) -> list[ConfigLayer]:
        assert sources == []
        return [
            ConfigLayer(
                origin=SyntheticConfigSource(label="<api>"),
                scope_root=None,
                precedence=1,
                kind=ConfigLayerKind.API,
                config=api_config,
            ),
            ConfigLayer(
                origin=SyntheticConfigSource(label="<cli>"),
                scope_root=None,
                precedence=2,
                kind=ConfigLayerKind.CLI,
                config=cli_config,
            ),
        ]

    monkeypatch.setattr(
        toml_payloads,
        "build_config_layers_from_resolved_toml_sources",
        _build_layers,
    )
    resolved = ResolvedTopmarkTomlSources(
        sources=[],
        writer_options=None,
        strict=None,
    )

    payload: TomlProvenancePayload = build_toml_provenance_payload(resolved)

    assert [(layer.origin, layer.kind, layer.precedence) for layer in payload.layers] == [
        ("<api>", ConfigLayerKind.API.value, 1),
        ("<cli>", ConfigLayerKind.CLI.value, 2),
    ]

    api_layer: TomlProvenanceLayerPayload = payload.layers[0]
    assert is_mapping(api_layer.toml)
    api_toml_section_fields: object | None = api_layer.toml.get(Toml.SECTION_FIELDS)
    assert is_mapping(api_toml_section_fields)
    assert api_toml_section_fields.get("project") == "API Demo"

    cli_layer: TomlProvenanceLayerPayload = payload.layers[1]
    assert is_mapping(cli_layer.toml)
    cli_toml_section_fields: object | None = cli_layer.toml.get(Toml.SECTION_FIELDS)
    assert is_mapping(cli_toml_section_fields)
    assert cli_toml_section_fields.get("project") == "CLI Demo"


def test_toml_provenance_payload_skips_invalid_sources_when_aligning_layers(
    tmp_path: Path,
) -> None:
    """TOML provenance should align file-backed layers with parsed sources only."""
    invalid_file: Path = tmp_path / "invalid.toml"
    config_file: Path = tmp_path / "topmark.toml"
    toml_fragment: TomlTable = {
        Toml.SECTION_FIELDS: {
            "project": "Demo",
        },
        Toml.SECTION_HEADER: {
            Toml.KEY_FIELDS: ["project"],
        },
    }
    resolved = ResolvedTopmarkTomlSources(
        sources=[
            ResolvedTopmarkTomlSource(
                path=invalid_file,
                parsed=None,
                kind="explicit",
                validation_issues=(),
                load_diagnostics=MutableDiagnosticLog().freeze(),
            ),
            ResolvedTopmarkTomlSource(
                path=config_file,
                parsed=_parsed_toml_fragment(toml_fragment),
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
        layer for layer in payload.layers if layer.origin == config_file.resolve().as_posix()
    ]
    assert len(file_backed_layers) == 1
    assert file_backed_layers[0].toml[Toml.SECTION_FIELDS] == {"project": "Demo"}


def test_toml_provenance_payload_rejects_misaligned_file_backed_layers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """TOML provenance should fail if layers cannot be matched to parsed sources."""
    config_file: Path = tmp_path / "topmark.toml"

    def _build_layers(
        sources: list[ResolvedTopmarkTomlSource],
    ) -> list[ConfigLayer]:
        assert sources == []
        return [
            ConfigLayer(
                origin=config_file,
                scope_root=tmp_path,
                precedence=1,
                kind=ConfigLayerKind.EXPLICIT,
                config=mutable_config_from_defaults(),
            )
        ]

    monkeypatch.setattr(
        toml_payloads,
        "build_config_layers_from_resolved_toml_sources",
        _build_layers,
    )
    resolved = ResolvedTopmarkTomlSources(
        sources=[],
        writer_options=None,
        strict=None,
    )

    with pytest.raises(
        ValueError,
        match="config provenance layers do not align with resolved TOML sources",
    ):
        build_toml_provenance_payload(resolved)
