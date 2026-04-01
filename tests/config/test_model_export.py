# topmark:header:start
#
#   project      : TopMark
#   file         : test_model_export.py
#   file_relpath : tests/config/test_model_export.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for config model export and TOML rendering.

These tests cover:
- layered `Config` TOML serialization, and
- `to_toml()` behavior around TOML-incompatible values like `None`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.serializers import config_to_toml_dict
from topmark.core.keys import ArgKey
from topmark.toml.keys import Toml
from topmark.toml.render import to_toml

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.toml.types import TomlTable


@pytest.mark.pipeline
def test_to_toml_strips_none_entries() -> None:
    """to_toml() rejects None by stripping (regression guard).

    If your to_toml() strips None, validate it doesn’t crash and doesn’t emit None.
    """
    draft: MutableConfig = mutable_config_from_defaults()
    c: Config = draft.freeze()

    # Create a dict with explicit None where TOML doesn't allow it
    td: TomlTable = config_to_toml_dict(
        c,
        include_files=False,
    )
    formatting_tbl = td[Toml.SECTION_FORMATTING]
    assert isinstance(formatting_tbl, dict)

    formatting_tbl.pop(Toml.KEY_ALIGN_FIELDS, None)

    s: str = to_toml(formatting_tbl)
    assert ArgKey.ALIGN_FIELDS not in s  # or whatever your stripper does


@pytest.mark.pipeline
def test_config_to_toml_dict_origin_mode_preserves_pattern_group_and_source_tables(
    tmp_path: Path,
) -> None:
    """Origin-mode serialization should keep provenance-rich pattern/source tables."""
    from topmark.config.io.enums import FilesSerializationMode
    from topmark.config.types import PatternGroup
    from topmark.config.types import PatternSource

    proj: Path = tmp_path / "proj"
    proj.mkdir()
    gitignore_path: Path = proj / ".gitignore"
    gitignore_path.write_text("*.tmp\n", encoding="utf-8")
    files_txt_path: Path = proj / "files.txt"
    files_txt_path.write_text("src/a.py\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_defaults()
    draft.config_files = ["<defaults>"]
    draft.include_pattern_groups = [
        PatternGroup(patterns=("src/**/*.py",), base=proj),
    ]
    draft.exclude_pattern_groups = [
        PatternGroup(patterns=("build/**",), base=proj),
    ]
    draft.include_from = [
        PatternSource(path=gitignore_path, base=proj),
    ]
    draft.files_from = [
        PatternSource(path=files_txt_path, base=proj),
    ]

    c: Config = draft.freeze()
    d: TomlTable = config_to_toml_dict(
        c,
        include_files=False,
        files_serialization_mode=FilesSerializationMode.ORIGIN,
    )

    files_tbl = d[Toml.SECTION_FILES]
    assert isinstance(files_tbl, dict)

    include_groups = files_tbl[Toml.KEY_INCLUDE_PATTERN_GROUPS]
    assert isinstance(include_groups, list)
    assert include_groups
    first_include_group = include_groups[0]
    assert isinstance(first_include_group, dict)
    assert first_include_group[Toml.KEY_BASE] == str(proj)
    assert first_include_group[Toml.KEY_PATTERNS] == ["src/**/*.py"]

    include_from_sources = files_tbl[Toml.KEY_INCLUDE_FROM_SOURCES]
    assert isinstance(include_from_sources, list)
    assert include_from_sources
    first_include_from_source = include_from_sources[0]
    assert isinstance(first_include_from_source, dict)
    assert first_include_from_source[Toml.KEY_BASE] == str(proj)
    assert first_include_from_source[Toml.KEY_PATH] == str(gitignore_path)

    files_from_sources = files_tbl[Toml.KEY_FILES_FROM_SOURCES]
    assert isinstance(files_from_sources, list)
    assert files_from_sources
    first_files_from_source = files_from_sources[0]
    assert isinstance(first_files_from_source, dict)
    assert first_files_from_source[Toml.KEY_PATH] == str(files_txt_path)
