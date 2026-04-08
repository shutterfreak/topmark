# topmark:header:start
#
#   project      : TopMark
#   file         : test_schema_validation.py
#   file_relpath : tests/toml/test_schema_validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for whole-source TopMark TOML schema validation.

These tests exercise the TOML-layer validation boundary in `topmark.toml`:
- unknown top-level keys and sections,
- unknown keys inside closed sections,
- malformed section shapes,
- nested `[policy_by_type.<filetype>]` validation,
- free-form `[fields]` behavior,
- and propagation of TOML schema diagnostics into `MutableConfig.diagnostics`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tomlkit

from tests.conftest import assert_not_warned
from tests.conftest import assert_warned_and_diagnosed
from tests.toml.conftest import draft_from_topmark_toml_file
from tests.toml.conftest import draft_from_topmark_toml_table
from tests.toml.conftest import write_toml_document
from topmark.config.policy import HeaderMutationMode
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_source
from topmark.toml.loaders import load_topmark_toml_table

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue


# --- Whole-source TOML schema tests - dict based ---


@pytest.mark.toml
def test_unknown_top_level_keys_warn_and_are_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown top-level non-table keys are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            "unknown_root_key": 123,
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Unknown top-level key 'unknown_root_key'",
    )


@pytest.mark.toml
def test_unknown_top_level_table_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown top-level tables (unknown sections) are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            "bogus": {"x": 1},
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Unknown TOML section [bogus]",
    )


@pytest.mark.toml
def test_unknown_keys_are_reported_individually(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in closed sections are reported individually."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_PATTERNS: ["src/**"],
                "z": True,
                "a": True,
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "z" in [{Toml.SECTION_FILES}]',
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "a" in [{Toml.SECTION_FILES}]',
    )


@pytest.mark.toml
def test_unknown_section_keys_warn_and_are_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys inside known sections are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_PATTERNS: ["src/**/*.py"],
                "bogus": True,
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "bogus" in [{Toml.SECTION_FILES}]',
    )


@pytest.mark.toml
def test_section_wrong_type_warns_and_is_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If a known section is not a table, TopMark warns and ignores it."""
    caplog.set_level("WARNING")
    # [files] must be a table; provide a scalar to trigger the warning.
    draft: MutableConfig = draft_from_topmark_toml_table({Toml.SECTION_FILES: "not-a-table"})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"TOML section [{Toml.SECTION_FILES}] must be a table",
    )


@pytest.mark.toml
def test_policy_by_type_unknown_keys_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys inside [policy_by_type.<ft>] are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": {
                    Toml.KEY_POLICY_HEADER_MUTATION_MODE: HeaderMutationMode.ADD_ONLY.value,
                    "unknown_policy_key": False,
                }
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "unknown_policy_key" in [{Toml.SECTION_POLICY_BY_TYPE}.python]',
    )


@pytest.mark.toml
def test_policy_by_type_entry_wrong_type_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-table entries in [policy_by_type] are warned about and ignored."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {Toml.SECTION_POLICY_BY_TYPE: {"python": 123}}
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"TOML section [{Toml.SECTION_POLICY_BY_TYPE}.python] must be a table",
    )


@pytest.mark.toml
def test_fields_table_is_free_form_and_not_subject_to_unknown_key_validation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """[fields] is intentionally free-form and must not be subject to unknown-key validation."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_FIELDS: {"totally_custom": "x"},
            Toml.SECTION_FILES: {Toml.KEY_INCLUDE_PATTERNS: ["src/**"], "bogus": True},
        }
    )

    # Should warn about bogus in [files]
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "bogus" in [{Toml.SECTION_FILES}]',
    )
    # Should NOT warn about fields keys being unknown
    assert_not_warned(caplog=caplog, needle='Unknown key "totally_custom" in [fields]')

    assert draft.field_values["totally_custom"] == "x"


@pytest.mark.toml
def test_policy_by_type_valid_keys_parse_and_unknown_keys_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Valid [policy_by_type] entries parse; unknown keys are warned and ignored."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": {
                    Toml.KEY_POLICY_HEADER_MUTATION_MODE: HeaderMutationMode.ADD_ONLY.value,
                    "bogus": False,
                }
            }
        }
    )

    assert "python" in draft.policy_by_type
    assert draft.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.ADD_ONLY

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "bogus" in [{Toml.SECTION_POLICY_BY_TYPE}.python]',
    )


@pytest.mark.toml
@pytest.mark.parametrize(
    "section, valid_key, valid_value",
    [
        (Toml.SECTION_HEADER, Toml.KEY_FIELDS, ["file"]),
        (Toml.SECTION_FILES, Toml.KEY_INCLUDE_PATTERNS, ["src/**"]),
        (Toml.SECTION_WRITER, Toml.KEY_STRATEGY, "file"),
        (Toml.SECTION_FORMATTING, Toml.KEY_ALIGN_FIELDS, True),
        (
            Toml.SECTION_POLICY,
            Toml.KEY_POLICY_HEADER_MUTATION_MODE,
            HeaderMutationMode.ADD_ONLY.value,
        ),
    ],
)
def test_unknown_key_in_known_section_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
    section: str,
    valid_key: str,
    valid_value: TomlValue,
) -> None:
    """Unknown keys inside closed sections are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {section: {valid_key: valid_value, "bogus": True}}
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "bogus" in [{section}]',
    )


# ---- Dict / in-memory TOML tests ----


@pytest.mark.toml
def test_unknown_key_in_config_section_warns_and_known_key_still_resolves(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in `[config]` warn while known config-loading keys still parse."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_CONFIG: {
                Toml.KEY_STRICT_CONFIG_CHECKING: True,
                "bogus": 1,
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle='Unknown key "bogus" in [config]',
    )
    # `[config]` is non-layered, so the layered draft stays otherwise untouched.
    assert draft.header_fields == []


@pytest.mark.toml
def test_unknown_key_in_writer_section_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in `[writer]` are validated at the TOML layer."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_WRITER: {
                Toml.KEY_STRATEGY: "file",
                "bogus": True,
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle='Unknown key "bogus" in [writer]',
    )


@pytest.mark.toml
def test_empty_topmark_toml_table_produces_empty_draft_without_schema_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An empty non-pyproject TopMark TOML table is treated as an empty source."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table({})

    assert draft.header_fields == []
    assert_not_warned(caplog=caplog, needle="Unknown top-level key")
    assert_not_warned(caplog=caplog, needle="Unknown TOML section")


@pytest.mark.toml
def test_load_topmark_toml_table_extracts_tool_topmark_from_pyproject_table() -> None:
    """`load_topmark_toml_table(..., from_pyproject=True)` extracts `[tool.topmark]`."""
    pyproject_tbl: TomlTable = tomlkit.parse(
        """
        [tool.topmark.header]
        fields = ["file"]
        """
    ).unwrap()

    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        pyproject_tbl,
        from_pyproject=True,
    )
    assert parsed is not None

    assert Toml.SECTION_HEADER in parsed.layered_config
    header_section = parsed.layered_config[Toml.SECTION_HEADER]

    assert isinstance(header_section, dict)
    assert Toml.KEY_FIELDS in header_section

    assert header_section[Toml.KEY_FIELDS] == ["file"]


@pytest.mark.toml
def test_load_topmark_toml_source_distinguishes_missing_vs_empty_tool_topmark(
    tmp_path: Path,
) -> None:
    """Missing `[tool.topmark]` returns `None`, while an empty table still parses."""
    missing_dir: Path = tmp_path / "missing"
    missing_dir.mkdir()
    missing_path: Path = missing_dir / "pyproject.toml"
    write_toml_document(
        path=missing_path,
        content="""
            [tool.other]
            value = 1
        """,
    )

    empty_dir: Path = tmp_path / "empty"
    empty_dir.mkdir()
    empty_path: Path = empty_dir / "pyproject.toml"
    write_toml_document(
        path=empty_path,
        content="""
            [tool.topmark]
        """,
    )

    missing_parsed: ParsedTopmarkToml | None = load_topmark_toml_source(missing_path)
    empty_parsed: ParsedTopmarkToml | None = load_topmark_toml_source(empty_path)

    assert missing_parsed is None
    assert empty_parsed is not None
    assert empty_parsed.layered_config == {}
    assert empty_parsed.validation_issues == ()


# --- Whole-source TOML schema tests - TOML file based ---


@pytest.mark.toml
@pytest.mark.parametrize(
    "filename",
    ["topmark.toml", "pyproject.toml"],
)
def test_unknown_keys_reported_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    filename: str,
) -> None:
    """Unknown keys are also reported when loading from a split-parsed TOML source."""
    caplog.set_level("WARNING")
    p: Path = tmp_path / filename

    if filename == "topmark.toml":
        # Root table for topmark.toml
        p.write_text(
            """
            [files]
            include_patterns = ["src/**/*.py"]
            unknown_key = true
            """.lstrip(),
            encoding="utf-8",
        )
    else:
        # Nested under [tool.topmark] for pyproject.toml
        p.write_text(
            """
            [tool.topmark.files]
            include_patterns = ["src/**/*.py"]
            unknown_key = true
            """.lstrip(),
            encoding="utf-8",
        )

    draft: MutableConfig = draft_from_topmark_toml_file(p)

    # We should see a warning for the unknown key inside [files]
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "unknown_key" in [{Toml.SECTION_FILES}]',
    )


@pytest.mark.toml
def test_unknown_key_in_config_section_warns_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in `[config]` are reported when loading from a TOML file."""
    caplog.set_level("WARNING")
    path: Path = tmp_path / "topmark.toml"
    write_toml_document(
        path=path,
        content="""
            [config]
            strict_config_checking = true
            bogus = 1
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(path)
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle='Unknown key "bogus" in [config]',
    )


@pytest.mark.toml
def test_unknown_key_in_writer_section_warns_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in `[writer]` are reported when loading from a TOML file."""
    caplog.set_level("WARNING")
    path: Path = tmp_path / "topmark.toml"
    write_toml_document(
        path=path,
        content="""
            [writer]
            strategy = "file"
            bogus = true
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(path)
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle='Unknown key "bogus" in [writer]',
    )
