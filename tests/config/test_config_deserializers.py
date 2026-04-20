# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_deserializers.py
#   file_relpath : tests/config/test_config_deserializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for layered-config deserialization into `MutableConfig`.

These tests exercise:
- coercion and fallback behavior for wrong-type layered values,
- filtering of mixed-type lists,
- field-value normalization,
- duplicate file-type diagnostics,
- and helper-level path-source normalization used by config deserializers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.config import group_patterns
from tests.helpers.diagnostics import NON_EMPTY
from tests.helpers.diagnostics import assert_diagnostic_level_stats
from tests.helpers.diagnostics import assert_validation_stage_totals
from tests.helpers.diagnostics import assert_warned_and_diagnosed
from topmark.config.io.deserializers import mutable_config_from_layered_toml_table
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.config.types import PatternSource
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue


# --- Layered-config deserialization tests (remain in topmark.config) ---


@pytest.mark.config
def test_header_fields_wrong_type_is_treated_as_empty() -> None:
    """Wrong-type [header].fields is treated as empty (must not crash)."""
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_HEADER: {
                Toml.KEY_FIELDS: True,
            },
        },
    )
    assert draft.header_fields == []


@pytest.mark.config
def test_header_fields_mixed_types_ignores_non_strings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-string entries in [header].fields are ignored with a warning."""
    caplog.set_level("WARNING")

    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_HEADER: {
                Toml.KEY_FIELDS: [
                    "file",
                    123,
                    "file_relpath",
                ],
            },
        },
    )

    assert draft.header_fields == ["file", "file_relpath"]

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_HEADER}].{Toml.KEY_FIELDS}",
        min_count=1,
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=NON_EMPTY,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=NON_EMPTY,
        runtime=0,
    )


@pytest.mark.config
def test_policy_by_type_section_wrong_type_is_ignored() -> None:
    """Non-table [policy_by_type] values are ignored (must not crash)."""
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_POLICY_BY_TYPE: 123,
        },
    )

    assert draft.policy_by_type == {}


# Silence pyright for empty lists and sets of strings
_empty_str_list: list[str] = []
_empty_str_set: set[str] = set()


@pytest.mark.config
@pytest.mark.parametrize(
    "key,_kind,expect_empty",
    [
        (Toml.KEY_INCLUDE_PATTERNS, "pattern_groups", _empty_str_list),
        (Toml.KEY_EXCLUDE_PATTERNS, "pattern_groups", _empty_str_list),
        (Toml.KEY_INCLUDE_FROM, "attr", _empty_str_list),
        (Toml.KEY_EXCLUDE_FROM, "attr", _empty_str_list),
        (Toml.KEY_FILES_FROM, "attr", _empty_str_list),
        (Toml.KEY_INCLUDE_FILE_TYPES, "attr", _empty_str_set),
        (Toml.KEY_EXCLUDE_FILE_TYPES, "attr", _empty_str_set),
    ],
)
def test_files_list_valued_keys_wrong_type_is_treated_as_empty(
    key: str,
    _kind: str,
    expect_empty: object,
) -> None:
    """Wrong-type list values in [files] are treated as empty (must not crash)."""
    toml_dict: TomlTable = {
        Toml.SECTION_FILES: {
            key: True,
        },
    }
    draft: MutableConfig = mutable_config_from_layered_toml_table(toml_dict)

    if key == Toml.KEY_INCLUDE_PATTERNS:
        assert group_patterns(draft.include_pattern_groups) == expect_empty
    elif key == Toml.KEY_EXCLUDE_PATTERNS:
        assert group_patterns(draft.exclude_pattern_groups) == expect_empty
    elif key == Toml.KEY_INCLUDE_FROM:
        assert draft.include_from == expect_empty
    elif key == Toml.KEY_EXCLUDE_FROM:
        assert draft.exclude_from == expect_empty
    elif key == Toml.KEY_FILES_FROM:
        assert draft.files_from == expect_empty
    elif key == Toml.KEY_INCLUDE_FILE_TYPES:
        assert draft.include_file_types == expect_empty
    else:
        assert draft.exclude_file_types == expect_empty


@pytest.mark.config
def test_include_from_mixed_types_ignores_non_strings(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-string entries in [files].include_from are ignored with a warning."""
    caplog.set_level("WARNING")

    proj: Path = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text("*.tmp\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_FROM: [
                    "a.txt",
                    123,
                ],
            },
        },
        config_file=proj / "topmark.toml",
    )

    assert len(draft.include_from) == 1
    assert draft.include_from[0].path.name == "a.txt"

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{Toml.KEY_INCLUDE_FROM}",
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=NON_EMPTY,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=NON_EMPTY,
        runtime=0,
    )


@pytest.mark.config
@pytest.mark.parametrize(
    "key,is_include",
    [
        (Toml.KEY_INCLUDE_PATTERNS, True),
        (Toml.KEY_EXCLUDE_PATTERNS, False),
    ],
)
def test_glob_patterns_mixed_types_ignores_non_strings(
    caplog: pytest.LogCaptureFixture,
    key: str,
    is_include: bool,
) -> None:
    """Non-string entries in [files].(include|exclude)_patterns are ignored with a warning."""
    caplog.set_level("WARNING")

    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_FILES: {
                key: [
                    "src/**/*.py",
                    123,
                ],
            },
        },
    )

    patterns: list[str] = group_patterns(
        draft.include_pattern_groups if is_include else draft.exclude_pattern_groups
    )
    assert patterns == ["src/**/*.py"]

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{key}",
        min_count=1,
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=NON_EMPTY,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=NON_EMPTY,
        runtime=0,
    )


@pytest.mark.config
@pytest.mark.parametrize(
    "key,is_include",
    [
        (Toml.KEY_INCLUDE_PATTERNS, True),
        (Toml.KEY_EXCLUDE_PATTERNS, False),
    ],
)
def test_glob_patterns_all_non_strings_results_in_empty_list(
    caplog: pytest.LogCaptureFixture,
    key: str,
    is_include: str,
) -> None:
    """If all entries are non-strings, the patterns list becomes empty (and warnings emitted)."""
    caplog.set_level("WARNING")

    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_HEADER: {
                Toml.KEY_FIELDS: ["file"],
            },
            Toml.SECTION_FILES: {
                key: [
                    True,
                    123,
                ],
            },
        },
    )

    patterns: list[str] = group_patterns(
        draft.include_pattern_groups if is_include else draft.exclude_pattern_groups
    )
    assert patterns == []

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{key}",
        min_count=2,
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=2,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=2,
        runtime=0,
    )


@pytest.mark.config
def test_fields_scalar_values_are_stringified_and_unsupported_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """[fields] values are stringified for scalar types; ignore unsupported values.

    Unsupported values are ignored with location.
    """
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_HEADER: {
                Toml.KEY_FIELDS: ["file"],
            },
            Toml.SECTION_FIELDS: {
                "project": "TopMark",
                "year": 2025,
                "pi": 3.14,
                "flag": True,
                "bad": {
                    "nested": "nope",
                },
                "bad_list": [
                    1,
                    2,
                ],
            },
        },
    )

    assert draft.field_values["project"] == "TopMark"
    assert draft.field_values["year"] == "2025"
    assert draft.field_values["pi"] == "3.14"
    assert draft.field_values["flag"] == "True"
    assert "bad" not in draft.field_values
    assert "bad_list" not in draft.field_values

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Ignoring unsupported field value for [fields].bad",
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Ignoring unsupported field value for [fields].bad_list",
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=2,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=2,
        runtime=0,
    )


@pytest.mark.config
def test_header_fields_can_reference_missing_custom_fields_without_error() -> None:
    """header.fields may reference names not present in [fields] and should not crash."""
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_HEADER: {
                Toml.KEY_FIELDS: [
                    "file",
                    "project",
                    "missing_custom",
                ],
            },
            Toml.SECTION_FIELDS: {
                "project": "TopMark",
            },
        },
    )
    assert draft.header_fields == ["file", "project", "missing_custom"]
    assert draft.field_values["project"] == "TopMark"


@pytest.mark.config
@pytest.mark.parametrize("bad_val", ["x", 123, {"a": 1}, None])
def test_header_fields_wrong_type_falls_back_to_empty_list(
    bad_val: TomlValue,
) -> None:
    """Wrong-type list values should be treated as empty lists (parsing must not crash)."""
    # Layered-config deserialization currently treats wrong-type values as an
    # empty list without emitting a dedicated warning.

    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_HEADER: {
                Toml.KEY_FIELDS: bad_val,
            },
        },
    )
    assert draft.header_fields == []


@pytest.mark.config
def test_duplicate_include_file_types_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate include_file_types entries produce a warning and a diagnostic."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_FILE_TYPES: [
                    "python",
                    "python",
                ],
            },
        }
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Duplicate included file types found in config "
        f"(key: {Toml.KEY_INCLUDE_FILE_TYPES})",
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=NON_EMPTY,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=NON_EMPTY,
        runtime=0,
    )


@pytest.mark.config
def test_duplicate_exclude_file_types_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate exclude_file_types entries produce a warning and a diagnostic."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_EXCLUDE_FILE_TYPES: [
                    "python",
                    "python",
                ],
            },
        }
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Duplicate excluded file types found in config "
        f"(key: {Toml.KEY_EXCLUDE_FILE_TYPES})",
    )
    assert_diagnostic_level_stats(
        stats=draft.validation_logs.flattened().stats(),
        expected_warning=NON_EMPTY,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=NON_EMPTY,
        runtime=0,
    )


@pytest.mark.config
def test_extend_pattern_sources_resolves_relative_paths_against_base(
    tmp_path: Path,
) -> None:
    """extend_pattern_sources() resolves relative paths against the provided base."""
    from topmark.config.paths import extend_pattern_sources
    from topmark.config.paths import pattern_source_from_config

    cfg_dir: Path = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "a.txt").write_text("x", encoding="utf-8")

    dst: list[PatternSource] = []
    extend_pattern_sources(
        ["a.txt"],
        dst=dst,
        mk=pattern_source_from_config,
        kind="include_from",
        base=cfg_dir,
    )

    assert len(dst) == 1
    assert dst[0].path == (cfg_dir / "a.txt").resolve()
    assert dst[0].base == (cfg_dir / "a.txt").resolve().parent
