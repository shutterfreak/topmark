# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_resolution_merge.py
#   file_relpath : tests/config/test_config_resolution_merge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for config-layer applicability and merge behavior.

These tests exercise:
- accumulation versus nearest-wins behavior across layers,
- selection of layers applicable to a given path,
- construction of effective per-path configs,
- merging behavior for empty layer sets,
- and precedence of CLI overrides over resolved TOML layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.toml.conftest import write_toml_document
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import build_effective_config_for_path
from topmark.config.resolution.merge import merge_layers_globally
from topmark.config.resolution.merge import select_applicable_layers
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.resolution import resolve_topmark_toml_sources

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.config.resolution.layers import ConfigLayer


@pytest.mark.config
def test_include_from_accumulates_across_multiple_applicable_layers(
    tmp_path: Path,
) -> None:
    """include_from sources accumulate across applicable discovered config layers."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)
    write_toml_document(
        path=root / ".gitignore",
        content="*.tmp\n",
    )
    write_toml_document(
        path=child / ".include",
        content="src/**/*.py\n",
    )

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_from = [".gitignore"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            include_from = [".include"]
        """,
    )

    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=[child],
    )
    paths: list[Path] = [ps.path for ps in draft.include_from]

    assert paths == [
        (root / ".gitignore").resolve(),
        (child / ".include").resolve(),
    ]


@pytest.mark.config
def test_files_nearest_non_empty_list_wins_across_layers(
    tmp_path: Path,
) -> None:
    """Explicit files lists use nearest-wins semantics across applicable layers."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            files = ["README.md"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            files = ["module.py"]
        """,
    )

    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=[child],
    )
    assert draft.files == [str((child / "module.py").resolve())]


@pytest.mark.config
def test_include_file_types_nearest_non_empty_set_wins_across_layers(
    tmp_path: Path,
) -> None:
    """include_file_types uses nearest-wins semantics rather than set union."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_file_types = ["python"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            include_file_types = ["markdown"]
        """,
    )

    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=[child],
    )
    assert draft.include_file_types == {"markdown"}


@pytest.mark.config
def test_select_applicable_layers_filters_child_scoped_layer(
    tmp_path: Path,
) -> None:
    """select_applicable_layers keeps global layers and filters file-backed layers by scope."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.formatting]
            align_fields = false
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(input_paths=[child])
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)

    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.md"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")

    child_layers: list[ConfigLayer] = select_applicable_layers(layers, child_file)
    sibling_layers: list[ConfigLayer] = select_applicable_layers(layers, sibling_file)

    assert any(layer.scope_root == child.resolve() for layer in child_layers)
    assert not any(layer.scope_root == child.resolve() for layer in sibling_layers)


@pytest.mark.config
def test_build_effective_config_for_path_merges_only_applicable_layers(
    tmp_path: Path,
) -> None:
    """Per-path effective configs should merge only the layers whose scope applies."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.header]
            fields = ["project", "license"]

            [tool.topmark.fields]
            project = "TopMark"
            license = "MIT"
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [header]
            fields = ["project", "file"]

            [fields]
            file = "pkg/module.py"
        """,
    )

    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.md"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(input_paths=[child])
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)

    child_cfg: Config = build_effective_config_for_path(layers, child_file).freeze()
    sibling_cfg: Config = build_effective_config_for_path(layers, sibling_file).freeze()

    assert child_cfg.header_fields == ("project", "file")
    assert child_cfg.field_values["project"] == "TopMark"
    assert child_cfg.field_values["file"] == "pkg/module.py"

    assert sibling_cfg.header_fields == ("project", "license")
    assert sibling_cfg.field_values["project"] == "TopMark"
    assert "file" not in sibling_cfg.field_values


@pytest.mark.config
def test_merge_layers_globally_empty_returns_defaults() -> None:
    """Merging an empty layer sequence should fall back to defaults."""
    draft: MutableConfig = merge_layers_globally(())
    default_draft: MutableConfig = mutable_config_from_defaults()

    assert draft.header_fields == default_draft.header_fields
    assert draft.include_from == default_draft.include_from
    assert draft.include_pattern_groups == default_draft.include_pattern_groups


@pytest.mark.config
def test_cli_overrides_merge_last(
    tmp_path: Path,
) -> None:
    """CLI overrides have highest precedence."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.formatting]
            align_fields = false
        """,
    )

    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=[proj],
    )
    # Simulate CLI override
    overrides = ConfigOverrides(
        align_fields=True,
    )
    apply_config_overrides(
        draft,
        overrides,
    )
    assert draft.align_fields is True
