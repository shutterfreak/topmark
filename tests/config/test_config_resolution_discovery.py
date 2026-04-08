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

from tests.toml.conftest import write_toml_document
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.config
@pytest.mark.toml
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

    _resolved, draft = resolve_toml_sources_and_build_config_draft(input_paths=[proj])
    # topmark.toml should win within the same directory
    assert draft.align_fields is True


@pytest.mark.config
@pytest.mark.toml
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

    _resolved, draft = resolve_toml_sources_and_build_config_draft(input_paths=[child])
    # Should see settings from `root`, not from `above`
    assert draft.align_fields is True


@pytest.mark.config
@pytest.mark.toml
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

    _resolved, draft = resolve_toml_sources_and_build_config_draft(input_paths=[child])
    assert draft.align_fields is True
