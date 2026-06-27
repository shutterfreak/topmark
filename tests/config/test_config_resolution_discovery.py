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

from tests.helpers.paths import symlink_or_skip
from tests.toml.conftest import write_toml_document
from topmark.config.resolution.bridge import ResolvedConfigDraft
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_mutable_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from topmark.config.resolution.bridge import ResolvedConfigDraft


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


def test_root_true_stops_traversal(
    tmp_path: Path,
) -> None:
    """`root = true` stops discovery above that directory."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    child.mkdir(parents=True)

    # Parent *above* root that should be ignored if traversal stops
    above: Path = tmp_path / "above"
    write_toml_document(
        path=above / "pyproject.toml",
        content="""
            [tool.topmark.formatting]
            align_fields = false
        """,
    )

    # Discovery root marker declared in the `[tool.topmark]` table.
    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark]
            root = true

            [tool.topmark.formatting]
            align_fields = true
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child]
    )
    # Should see settings from `root`, not from `above`
    assert resolved_config.draft.align_fields is True


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
