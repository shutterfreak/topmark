# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_resolution_discovery.py
#   file_relpath : tests/config/test_config_resolution_discovery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for TopMark TOML source discovery semantics.

These tests exercise:
- same-directory precedence between `pyproject.toml` and `topmark.toml`,
- stopping upward discovery at `root = true`,
- and ignoring malformed discovered TOML sources while continuing resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.paths import symlink_or_skip
from tests.toml.conftest import write_toml_document
from topmark.config.resolution.bridge import ResolvedConfigDraft
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_mutable_config
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import build_effective_config_for_path

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.config.resolution.layers import ConfigLayer


def test_same_dir_precedence_topmark_over_pyproject(
    tmp_path: Path,
) -> None:
    """In the same directory, `topmark.toml` overrides `pyproject.toml`."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.formatting]
            align_fields = false
        """,
    )
    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[proj]
    )
    # topmark.toml should win within the same directory
    assert resolved_config.draft.align_fields is True
    assert resolved_config.draft.config_files == [
        proj.resolve() / "pyproject.toml",
        proj.resolve() / "topmark.toml",
    ]


@pytest.mark.parametrize(
    ("root_filename", "root_content"),
    [
        (
            "topmark.toml",
            """
                [config]
                root = true

                [formatting]
                align_fields = true
            """,
        ),
        (
            "pyproject.toml",
            """
                [tool.topmark.config]
                root = true

                [tool.topmark.formatting]
                align_fields = true
            """,
        ),
    ],
    ids=["topmark-toml", "pyproject-toml"],
)
def test_root_true_stops_traversal(
    tmp_path: Path,
    root_filename: str,
    root_content: str,
) -> None:
    """Both supported root-marker representations stop upward discovery."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    child.mkdir(parents=True)

    # An actual ancestor above the discovery root must be ignored.
    write_toml_document(
        path=tmp_path / "topmark.toml",
        content="""
            [formatting]
            align_fields = false
        """,
    )

    # The filename and owned config-table path are coupled representations.
    write_toml_document(
        path=root / root_filename,
        content=root_content,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child]
    )
    # Should see settings from `root`, not from its ancestor.
    assert resolved_config.draft.align_fields is True
    assert resolved_config.draft.config_files == [root.resolve() / root_filename]


def test_mixed_sources_in_different_directories_follow_root_to_nearest_precedence(
    tmp_path: Path,
) -> None:
    """Mixed source formats both participate, with the nearest layer winning."""
    parent: Path = tmp_path / "project"
    child: Path = parent / "package"
    child.mkdir(parents=True)

    write_toml_document(
        path=parent / "pyproject.toml",
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

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child]
    )

    assert resolved_config.draft.align_fields is True
    assert resolved_config.draft.config_files == [
        parent.resolve() / "pyproject.toml",
        child.resolve() / "topmark.toml",
    ]


def test_directory_input_discovers_descendant_sources_for_scoped_resolution(
    tmp_path: Path,
) -> None:
    """A directory run loads nested sources without applying them to siblings."""
    root: Path = tmp_path / "project"
    child: Path = root / "package"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir()
    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.py"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")

    write_toml_document(
        path=root / "topmark.toml",
        content="""
            [fields]
            project = "root"
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [fields]
            project = "child"
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[root]
    )

    assert resolved_config.draft.config_files == [
        root.resolve() / "topmark.toml",
        child.resolve() / "topmark.toml",
    ]
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved_config.resolved.sources
    )
    assert build_effective_config_for_path(layers, child_file).field_values["project"] == "child"
    assert build_effective_config_for_path(layers, sibling_file).field_values["project"] == "root"


def test_overlapping_directory_inputs_discover_each_source_once(
    tmp_path: Path,
) -> None:
    """Overlapping directory roots do not duplicate a descendant source."""
    root: Path = tmp_path / "project"
    child: Path = root / "package"
    grandchild: Path = child / "module"
    grandchild.mkdir(parents=True)
    write_toml_document(
        path=grandchild / "topmark.toml",
        content="""
            [fields]
            project = "child"
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[root, child]
    )

    assert resolved_config.draft.config_files == [grandchild.resolve() / "topmark.toml"]


def test_descendant_root_boundary_excludes_ancestor_layer_per_path(
    tmp_path: Path,
) -> None:
    """A nested root marker blocks loaded ancestor layers only in its subtree."""
    root: Path = tmp_path / "project"
    child: Path = root / "package"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir()
    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.py"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")
    write_toml_document(
        path=root / "topmark.toml",
        content="""
            [fields]
            project = "root"
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [config]
            root = true

            [fields]
            package = "child"
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[root]
    )
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved_config.resolved.sources
    )

    child_config: MutableConfig = build_effective_config_for_path(layers, child_file)
    sibling_config: MutableConfig = build_effective_config_for_path(layers, sibling_file)
    assert child_config.field_values == {"package": "child"}
    assert sibling_config.field_values == {"project": "root"}


def test_multiple_directory_roots_keep_nested_layers_isolated(
    tmp_path: Path,
) -> None:
    """Multiple roots retain each nested source only within its own subtree."""
    first: Path = tmp_path / "first"
    second: Path = tmp_path / "second"
    first_child: Path = first / "package"
    second_child: Path = second / "package"
    first_child.mkdir(parents=True)
    second_child.mkdir(parents=True)
    first_file: Path = first_child / "one.py"
    second_file: Path = second_child / "two.py"
    first_file.write_text("x\n", encoding="utf-8")
    second_file.write_text("x\n", encoding="utf-8")
    write_toml_document(
        path=first_child / "topmark.toml",
        content='[fields]\nproject = "first"\n',
    )
    write_toml_document(
        path=second_child / "topmark.toml",
        content='[fields]\nproject = "second"\n',
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[first, second],
    )
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved_config.resolved.sources,
    )

    assert build_effective_config_for_path(layers, first_file).field_values["project"] == "first"
    assert build_effective_config_for_path(layers, second_file).field_values["project"] == "second"


def test_no_config_keeps_only_explicit_nested_source(
    tmp_path: Path,
) -> None:
    """No-config excludes automatic sources while retaining explicit source scope."""
    root: Path = tmp_path / "project"
    child: Path = root / "package"
    child.mkdir(parents=True)
    write_toml_document(path=root / "topmark.toml", content='[fields]\nproject = "root"\n')
    explicit: Path = child / "extra.toml"
    write_toml_document(path=explicit, content='[fields]\nproject = "explicit"\n')

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[root],
        extra_config_files=[explicit],
        no_config=True,
    )

    assert resolved_config.draft.config_files == [explicit.resolve()]


def test_malformed_descendant_source_is_preserved_for_diagnostics(
    tmp_path: Path,
) -> None:
    """A malformed descendant source remains visible to staged validation."""
    root: Path = tmp_path / "project"
    child: Path = root / "package"
    child.mkdir(parents=True)
    malformed: Path = child / "topmark.toml"
    malformed.write_text("[config\ninvalid", encoding="utf-8")

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[root]
    )

    assert [source.path for source in resolved_config.resolved.sources] == [malformed.resolve()]
    assert resolved_config.resolved.sources[0].parsed is None


def test_symlinked_discovery_anchor_uses_resolved_project_chain(
    tmp_path: Path,
) -> None:
    """Project discovery follows the resolved target of a symlinked input anchor."""
    repo: Path = tmp_path / "real" / "repo"
    package: Path = repo / "pkg"
    package.mkdir(parents=True)
    write_toml_document(
        path=repo / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )
    linked_package: Path = symlink_or_skip(
        tmp_path / "links" / "pkg",
        package,
        target_is_directory=True,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[linked_package]
    )

    assert resolved_config.draft.align_fields is True
    assert resolved_config.draft.config_files == [repo.resolve() / "topmark.toml"]


def test_symlinked_cwd_discovery_uses_resolved_project_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Project discovery from CWD follows the resolved target before walking upward."""
    repo: Path = tmp_path / "real" / "repo"
    package: Path = repo / "pkg"
    package.mkdir(parents=True)
    write_toml_document(
        path=repo / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )
    linked_package: Path = symlink_or_skip(
        tmp_path / "links" / "pkg",
        package,
        target_is_directory=True,
    )
    monkeypatch.chdir(linked_package)

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config()

    assert resolved_config.draft.align_fields is True
    assert resolved_config.draft.config_files == [repo.resolve() / "topmark.toml"]


def test_repo_below_symlinked_parent_discovers_real_project_chain(
    tmp_path: Path,
) -> None:
    """Project discovery resolves a symlinked parent spelling before config traversal."""
    real_parent: Path = tmp_path / "real-parent"
    repo: Path = real_parent / "repo"
    package: Path = repo / "pkg"
    package.mkdir(parents=True)
    write_toml_document(
        path=repo / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )
    linked_parent: Path = symlink_or_skip(
        tmp_path / "linked-parent",
        real_parent,
        target_is_directory=True,
    )
    symlink_spelled_package: Path = linked_parent / "repo" / "pkg"

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[symlink_spelled_package]
    )

    assert resolved_config.draft.align_fields is True
    assert resolved_config.draft.config_files == [repo.resolve() / "topmark.toml"]


def test_malformed_toml_in_discovered_config_is_ignored(
    tmp_path: Path,
) -> None:
    """Discovery ignores TOML parse errors in an unrelated parent."""
    parent: Path = tmp_path / "parent"
    child: Path = parent / "child"
    child.mkdir(parents=True)

    # Malformed pyproject.toml in parent
    (parent / "pyproject.toml").write_text("[tool.topmark\nbad", encoding="utf-8")
    # Valid config in child
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child]
    )
    assert resolved_config.draft.align_fields is True
    assert [source.path for source in resolved_config.resolved.sources] == [
        (parent / "pyproject.toml").resolve(),
        (child / "topmark.toml").resolve(),
    ]
    assert resolved_config.resolved.sources[0].parsed is None
    assert resolved_config.resolved.sources[1].parsed is not None


@pytest.mark.parametrize(
    "content",
    [
        "",
        '[tool.example]\nname="demo"\n',
        "tool=2\n",
        "[tool]\ntopmark=2\n",
    ],
)
def test_unowned_pyproject_is_not_an_invalid_topmark_source(
    tmp_path: Path,
    content: str,
) -> None:
    """Valid project metadata without an owned table must not produce a load error."""
    path: Path = tmp_path / "pyproject.toml"
    path.write_text(content, encoding="utf-8")
    resolved: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        no_config=True,
        extra_config_files=[path],
        strict=True,
    )
    assert resolved.resolved.sources == []
    assert resolved.draft.freeze().is_valid(strict=True)
