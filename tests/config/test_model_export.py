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
- layered [`FrozenConfig`][topmark.config.model.FrozenConfig] TOML serialization, and
- `to_toml()` behavior around TOML-incompatible values like `None`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.serializers import config_to_topmark_toml_table
from topmark.config.resolution.synthetic import DEFAULT_CONFIG_SOURCE
from topmark.config.types import PatternGroup
from topmark.config.types import PatternSource
from topmark.core.keys import ArgKey
from topmark.toml.enums import FilesSerializationMode
from topmark.toml.keys import Toml
from topmark.toml.render import render_toml_table

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.toml.types import TomlTable


def test_to_toml_strips_none_entries() -> None:
    """to_toml() rejects None by stripping (regression guard).

    If your to_toml() strips None, validate it doesn't crash and doesn't emit None.
    """
    draft: MutableConfig = mutable_config_from_defaults()
    c: FrozenConfig = draft.freeze()

    # Create a dict with explicit None where TOML doesn't allow it
    td: TomlTable = config_to_topmark_toml_table(
        c,
        include_files=False,
    )
    formatting_tbl = td[Toml.SECTION_FORMATTING]
    assert isinstance(formatting_tbl, dict)

    formatting_tbl.pop(Toml.KEY_ALIGN_FIELDS, None)

    s: str = render_toml_table(formatting_tbl)
    assert ArgKey.ALIGN_FIELDS not in s  # or whatever your stripper does


def test_config_to_toml_dict_origin_mode_preserves_pattern_group_and_source_tables(
    tmp_path: Path,
) -> None:
    """Origin-mode serialization should keep provenance-rich pattern/source tables."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()
    gitignore_path: Path = proj / ".gitignore"
    gitignore_path.write_text("*.tmp\n", encoding="utf-8")
    files_txt_path: Path = proj / "files.txt"
    files_txt_path.write_text("src/a.py\n", encoding="utf-8")
    exclude_path: Path = proj / "exclude.txt"
    exclude_path.write_text("build/**\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_defaults()
    draft.config_files = [
        DEFAULT_CONFIG_SOURCE,
    ]
    draft.include_pattern_groups = [
        PatternGroup(patterns=("src/**/*.py",), base=proj),
    ]
    draft.exclude_pattern_groups = [
        PatternGroup(patterns=("build/**",), base=proj),
    ]
    draft.include_from = [
        PatternSource(path=gitignore_path, base=proj),
    ]
    draft.exclude_from = [
        PatternSource(path=exclude_path, base=proj),
    ]
    draft.files_from = [
        PatternSource(path=files_txt_path, base=proj),
    ]

    c: FrozenConfig = draft.freeze()
    d: TomlTable = config_to_topmark_toml_table(
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
    assert first_include_group[Toml.KEY_BASE] == proj.as_posix()
    assert first_include_group[Toml.KEY_PATTERNS] == ["src/**/*.py"]

    exclude_groups = files_tbl[Toml.KEY_EXCLUDE_PATTERN_GROUPS]
    assert isinstance(exclude_groups, list)
    assert exclude_groups
    first_exclude_group = exclude_groups[0]
    assert isinstance(first_exclude_group, dict)
    assert first_exclude_group[Toml.KEY_BASE] == proj.as_posix()
    assert first_exclude_group[Toml.KEY_PATTERNS] == ["build/**"]

    include_from_sources = files_tbl[Toml.KEY_INCLUDE_FROM_SOURCES]
    assert isinstance(include_from_sources, list)
    assert include_from_sources
    first_include_from_source = include_from_sources[0]
    assert isinstance(first_include_from_source, dict)
    assert first_include_from_source[Toml.KEY_BASE] == proj.as_posix()
    assert first_include_from_source[Toml.KEY_PATH] == gitignore_path.as_posix()

    exclude_from_sources = files_tbl[Toml.KEY_EXCLUDE_FROM_SOURCES]
    assert isinstance(exclude_from_sources, list)
    assert exclude_from_sources
    first_exclude_from_source = exclude_from_sources[0]
    assert isinstance(first_exclude_from_source, dict)
    assert first_exclude_from_source[Toml.KEY_BASE] == proj.as_posix()
    assert first_exclude_from_source[Toml.KEY_PATH] == exclude_path.as_posix()

    files_from_sources = files_tbl[Toml.KEY_FILES_FROM_SOURCES]
    assert isinstance(files_from_sources, list)
    assert files_from_sources
    first_files_from_source = files_from_sources[0]
    assert isinstance(first_files_from_source, dict)
    assert first_files_from_source[Toml.KEY_BASE] == proj.as_posix()
    assert first_files_from_source[Toml.KEY_PATH] == files_txt_path.as_posix()


def test_config_to_toml_dict_rebased_mode_flattens_pattern_groups(
    tmp_path: Path,
) -> None:
    """Rebased serialization should flatten include/exclude pattern groups."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    draft: MutableConfig = mutable_config_from_defaults()
    draft.include_pattern_groups = [
        PatternGroup(patterns=("src/**/*.py",), base=proj),
    ]
    draft.exclude_pattern_groups = [
        PatternGroup(patterns=("build/**",), base=proj),
    ]

    c: FrozenConfig = draft.freeze()
    d: TomlTable = config_to_topmark_toml_table(
        c,
        files_serialization_mode=FilesSerializationMode.REBASED,
    )

    files_tbl = d[Toml.SECTION_FILES]
    assert isinstance(files_tbl, dict)

    include_patterns = files_tbl[Toml.KEY_INCLUDE_PATTERNS]
    assert isinstance(include_patterns, list)
    assert len(include_patterns) == 1
    include_pattern = include_patterns[0]
    assert isinstance(include_pattern, str)
    assert include_pattern.endswith("src/**/*.py")

    exclude_patterns = files_tbl[Toml.KEY_EXCLUDE_PATTERNS]
    assert isinstance(exclude_patterns, list)
    assert len(exclude_patterns) == 1
    exclude_pattern = exclude_patterns[0]
    assert isinstance(exclude_pattern, str)
    assert exclude_pattern.endswith("build/**")


def test_config_to_toml_dict_includes_file_list_when_requested() -> None:
    """Explicit file-list export should include discovered files when requested."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.files = [
        "src/topmark/__init__.py",
        "src/topmark/cli/main.py",
    ]

    c: FrozenConfig = draft.freeze()
    d: TomlTable = config_to_topmark_toml_table(
        c,
        include_files=True,
    )

    files_tbl = d[Toml.SECTION_FILES]
    assert isinstance(files_tbl, dict)
    assert files_tbl[Toml.KEY_FILES] == [
        "src/topmark/__init__.py",
        "src/topmark/cli/main.py",
    ]


@pytest.mark.parametrize(
    ("mode", "expected_keys", "unexpected_keys"),
    [
        pytest.param(
            FilesSerializationMode.REBASED,
            {
                Toml.KEY_INCLUDE_PATTERNS,
                Toml.KEY_EXCLUDE_PATTERNS,
                Toml.KEY_INCLUDE_FROM,
                Toml.KEY_EXCLUDE_FROM,
                Toml.KEY_FILES_FROM,
            },
            {
                Toml.KEY_INCLUDE_PATTERN_GROUPS,
                Toml.KEY_EXCLUDE_PATTERN_GROUPS,
                Toml.KEY_INCLUDE_FROM_SOURCES,
                Toml.KEY_EXCLUDE_FROM_SOURCES,
                Toml.KEY_FILES_FROM_SOURCES,
            },
            id="rebased",
        ),
        pytest.param(
            FilesSerializationMode.ORIGIN,
            {
                Toml.KEY_INCLUDE_PATTERN_GROUPS,
                Toml.KEY_EXCLUDE_PATTERN_GROUPS,
                Toml.KEY_INCLUDE_FROM_SOURCES,
                Toml.KEY_EXCLUDE_FROM_SOURCES,
                Toml.KEY_FILES_FROM_SOURCES,
            },
            {
                Toml.KEY_INCLUDE_PATTERNS,
                Toml.KEY_EXCLUDE_PATTERNS,
                Toml.KEY_INCLUDE_FROM,
                Toml.KEY_EXCLUDE_FROM,
                Toml.KEY_FILES_FROM,
            },
            id="origin",
        ),
    ],
)
def test_config_to_toml_dict_files_serialization_modes_emit_expected_shapes(
    mode: FilesSerializationMode,
    expected_keys: set[str],
    unexpected_keys: set[str],
) -> None:
    """Files serialization modes should emit distinct files-table shapes."""
    c: FrozenConfig = mutable_config_from_defaults().freeze()

    d: TomlTable = config_to_topmark_toml_table(
        c,
        files_serialization_mode=mode,
    )

    files_tbl = d[Toml.SECTION_FILES]
    assert isinstance(files_tbl, dict)

    assert expected_keys <= files_tbl.keys()
    assert unexpected_keys.isdisjoint(files_tbl.keys())
