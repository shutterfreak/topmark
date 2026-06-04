# topmark:header:start
#
#   project      : TopMark
#   file         : test_layers.py
#   file_relpath : tests/config/resolution/test_layers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Regression tests for config provenance layer construction."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.helpers.paths import symlink_or_skip
from topmark.config.resolution.layers import ConfigLayerKind
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import select_applicable_layers
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.toml.parse import ParsedTopmarkToml
from topmark.toml.parse import SourceConfigLoadingOptions
from topmark.toml.parse import SourceTomlOptions
from topmark.toml.resolution import ResolvedTopmarkTomlSource

if TYPE_CHECKING:
    from topmark.config.resolution.layers import ConfigLayer
    from topmark.toml.resolution import TomlSourceKind
    from topmark.toml.types import TomlTable


def _parsed_empty_toml() -> ParsedTopmarkToml:
    """Return an empty parsed TOML source for layer construction tests."""
    empty_table: TomlTable = {}
    return ParsedTopmarkToml(
        config_loading_options=SourceConfigLoadingOptions(),
        layered_config=empty_table,
        writer_options=None,
        source_options=SourceTomlOptions(),
        toml_fragment=empty_table,
        validation_issues=(),
    )


def test_config_layer_from_symlink_origin_uses_target_scope_root(tmp_path: Path) -> None:
    """File-backed config layers scope to the resolved target directory."""
    target_config: Path = tmp_path / "real" / "topmark.toml"
    target_config.parent.mkdir(parents=True)
    target_config.write_text("[config]\nstrict = true\n", encoding="utf-8")
    link_config: Path = symlink_or_skip(tmp_path / "links" / "topmark.toml", target_config)

    source = ResolvedTopmarkTomlSource(
        path=link_config,
        parsed=_parsed_empty_toml(),
        kind="explicit",
        validation_issues=(),
        load_diagnostics=MutableDiagnosticLog().freeze(),
    )

    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources([source])
    explicit_layers: list[ConfigLayer] = [
        layer for layer in layers if layer.kind.value == "explicit"
    ]

    assert len(explicit_layers) == 1
    layer: ConfigLayer = explicit_layers[0]
    assert layer.origin == target_config.resolve()
    assert layer.scope_root == target_config.parent.resolve()
    assert layer.scope_root != link_config.parent


def test_config_layer_scope_uses_resolved_processing_target(tmp_path: Path) -> None:
    """Config applicability compares resolved processing paths and scope roots."""
    target_config: Path = tmp_path / "real" / "topmark.toml"
    target_config.parent.mkdir(parents=True)
    target_config.write_text("[config]\nstrict = true\n", encoding="utf-8")
    link_config: Path = symlink_or_skip(tmp_path / "links" / "topmark.toml", target_config)
    target_file: Path = tmp_path / "real" / "pkg" / "module.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("print('hello')\n", encoding="utf-8")
    link_file: Path = symlink_or_skip(tmp_path / "linked-module.py", target_file)

    source = ResolvedTopmarkTomlSource(
        path=link_config,
        parsed=_parsed_empty_toml(),
        kind="explicit",
        validation_issues=(),
        load_diagnostics=MutableDiagnosticLog().freeze(),
    )

    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources([source])
    explicit_layers: list[ConfigLayer] = [
        layer for layer in layers if layer.kind.value == "explicit"
    ]

    assert len(explicit_layers) == 1
    layer: ConfigLayer = explicit_layers[0]
    assert select_applicable_layers([layer], link_file) == [layer]


def test_config_layer_preserves_missing_provenance_path_non_strictly(tmp_path: Path) -> None:
    """Provenance-only paths need not exist to build a stable config layer."""
    missing_config: Path = tmp_path / "generated" / "topmark.toml"
    source = ResolvedTopmarkTomlSource(
        path=missing_config,
        parsed=_parsed_empty_toml(),
        kind="explicit",
        validation_issues=(),
        load_diagnostics=MutableDiagnosticLog().freeze(),
    )

    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources([source])
    explicit_layers: list[ConfigLayer] = [
        layer for layer in layers if layer.kind.value == "explicit"
    ]

    assert len(explicit_layers) == 1
    layer: ConfigLayer = explicit_layers[0]
    assert layer.origin == missing_config.resolve()
    assert layer.scope_root == missing_config.parent.resolve()
    assert not missing_config.exists()


def test_invalid_resolved_toml_source_is_skipped() -> None:
    """Unreadable or invalid TOML sources should not produce config layers."""
    source = ResolvedTopmarkTomlSource(
        path=Path("topmark.toml"),
        parsed=None,
        kind="explicit",
        validation_issues=(),
        load_diagnostics=MutableDiagnosticLog().freeze(),
    )

    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources([source])

    assert [layer.kind.value for layer in layers] == ["default"]


@pytest.mark.parametrize(
    ("source_kind", "expected"),
    [
        pytest.param("user", ConfigLayerKind.USER, id="user-source"),
        pytest.param("explicit", ConfigLayerKind.EXPLICIT, id="explicit-source"),
        pytest.param("discovered", ConfigLayerKind.DISCOVERED, id="discovered-source"),
    ],
)
def test_resolved_source_kind_maps_to_layer_kind(
    source_kind: TomlSourceKind,
    expected: ConfigLayerKind,
) -> None:
    """Resolved TOML source kinds should map to matching config layer kinds."""
    source = ResolvedTopmarkTomlSource(
        path=Path("topmark.toml"),
        parsed=_parsed_empty_toml(),
        kind=source_kind,
        validation_issues=(),
        load_diagnostics=MutableDiagnosticLog().freeze(),
    )

    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources([source])

    assert [layer.kind for layer in layers] == [ConfigLayerKind.DEFAULT, expected]
