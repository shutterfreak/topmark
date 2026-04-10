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

from tests.helpers.diagnostics import assert_not_warned
from tests.helpers.diagnostics import assert_warned_and_diagnosed
from tests.toml.conftest import draft_from_topmark_toml_file
from tests.toml.conftest import draft_from_topmark_toml_table
from tests.toml.conftest import write_toml_document
from topmark.config.policy import HeaderMutationMode
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import DiagnosticStats
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_source
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue

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
def test_unknown_top_level_scalar_uses_unknown_top_level_key_code() -> None:
    """Unknown top-level scalar entries use the dedicated key diagnostic code."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        {
            "unknown_root_key": 123,
        }
    )
    assert parsed is not None

    matching: list[TomlValidationIssue] = [
        issue
        for issue in parsed.validation_issues
        if issue.code is TomlDiagnosticCode.UNKNOWN_TOP_LEVEL_KEY
    ]

    assert len(matching) == 1
    assert matching[0].section is None
    assert matching[0].key == "unknown_root_key"
    assert matching[0].path == ("unknown_root_key",)


@pytest.mark.toml
def test_unknown_top_level_table_uses_unknown_top_level_section_code() -> None:
    """Unknown top-level tables use the dedicated section diagnostic code."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        {
            "bogus": {"x": 1},
        }
    )
    assert parsed is not None

    matching: list[TomlValidationIssue] = [
        issue
        for issue in parsed.validation_issues
        if issue.code is TomlDiagnosticCode.UNKNOWN_TOP_LEVEL_SECTION
    ]

    assert len(matching) == 1
    assert matching[0].section is None
    assert matching[0].key == "bogus"
    assert matching[0].path == ("bogus",)


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
def test_section_wrong_type_uses_invalid_section_type_code_and_is_ignored() -> None:
    """Malformed known sections emit INVALID_SECTION_TYPE and are ignored."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        {
            Toml.SECTION_FILES: "not-a-table",
        }
    )
    assert parsed is not None

    matching: list[TomlValidationIssue] = [
        issue
        for issue in parsed.validation_issues
        if issue.code is TomlDiagnosticCode.INVALID_SECTION_TYPE
    ]

    assert len(matching) == 1
    assert matching[0].section == Toml.SECTION_FILES
    assert matching[0].key is None
    assert matching[0].path == (Toml.SECTION_FILES,)
    assert matching[0].level is DiagnosticLevel.WARNING
    assert parsed.layered_config == {}


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
def test_policy_by_type_entry_wrong_type_uses_invalid_nested_section_type_code() -> None:
    """Malformed nested policy tables emit INVALID_NESTED_SECTION_TYPE and are ignored."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": 123,
            }
        }
    )
    assert parsed is not None

    matching: list[TomlValidationIssue] = [
        issue
        for issue in parsed.validation_issues
        if issue.code is TomlDiagnosticCode.INVALID_NESTED_SECTION_TYPE
    ]

    assert len(matching) == 1
    assert matching[0].section == Toml.SECTION_POLICY_BY_TYPE
    assert matching[0].key == "python"
    assert matching[0].path == (Toml.SECTION_POLICY_BY_TYPE, "python")
    assert matching[0].level is DiagnosticLevel.WARNING

    # This test is about the TOML validation payload, not about the later effective config outcome.
    assert parsed.layered_config == {
        Toml.SECTION_POLICY_BY_TYPE: {
            "python": 123,
        }
    }


@pytest.mark.toml
def test_policy_by_type_entry_wrong_type_does_not_become_effective_policy_override() -> None:
    """Malformed nested policy entries do not produce effective policy overrides."""
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": 123,
            }
        }
    )

    assert draft.policy_by_type == {}


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
@pytest.mark.parametrize(
    ("section", "dump_only_key"),
    [
        (Toml.SECTION_FILES, Toml.KEY_INCLUDE_PATTERN_GROUPS),
        (Toml.SECTION_CONFIG, Toml.KEY_CONFIG_FILES),
    ],
)
def test_dump_only_keys_in_input_mode_warn_and_are_recorded(
    caplog: pytest.LogCaptureFixture,
    section: str,
    dump_only_key: str,
) -> None:
    """Dump/provenance-only keys are warned about when present in ordinary input mode."""
    caplog.set_level("WARNING")
    draft: MutableConfig = draft_from_topmark_toml_table(
        {
            section: {
                dump_only_key: [],
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Key "{dump_only_key}" is only valid in [{section}] '
        "when reading provenance/dump output",
    )


@pytest.mark.toml
@pytest.mark.parametrize(
    ("section", "dump_only_key"),
    [
        (Toml.SECTION_FILES, Toml.KEY_INCLUDE_PATTERN_GROUPS),
        (Toml.SECTION_CONFIG, Toml.KEY_CONFIG_FILES),
    ],
)
def test_dump_only_keys_in_input_mode_use_dump_only_code(
    section: str,
    dump_only_key: str,
) -> None:
    """Dump/provenance-only keys use the dedicated TOML diagnostic code in input mode."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        {
            section: {
                dump_only_key: [],
            }
        }
    )
    assert parsed is not None

    matching: list[TomlValidationIssue] = [
        issue
        for issue in parsed.validation_issues
        if issue.code is TomlDiagnosticCode.DUMP_ONLY_KEY_IN_INPUT
    ]

    assert len(matching) == 1
    assert matching[0].section == section
    assert matching[0].key == dump_only_key
    assert matching[0].path == (section, dump_only_key)
    assert matching[0].level is DiagnosticLevel.WARNING


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

    stats: DiagnosticStats = draft.diagnostics.stats()
    assert stats.n_info > 0


@pytest.mark.toml
def test_empty_topmark_toml_table_emits_info_diagnostics_for_missing_sections() -> None:
    """An empty TopMark TOML table emits INFO issues for each missing known section."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table({})
    assert parsed is not None

    issues: tuple[TomlValidationIssue, ...] = parsed.validation_issues
    missing_codes: list[TomlDiagnosticCode] = [
        issue.code for issue in issues if issue.code is TomlDiagnosticCode.MISSING_SECTION
    ]
    missing_sections = {
        issue.section for issue in issues if issue.code is TomlDiagnosticCode.MISSING_SECTION
    }

    assert missing_codes
    assert all(code is TomlDiagnosticCode.MISSING_SECTION for code in missing_codes)
    assert all(
        issue.level is DiagnosticLevel.INFO
        for issue in issues
        if issue.code is TomlDiagnosticCode.MISSING_SECTION
    )
    assert missing_sections == {
        Toml.SECTION_CONFIG,
        Toml.SECTION_HEADER,
        Toml.SECTION_FIELDS,
        Toml.SECTION_FORMATTING,
        Toml.SECTION_WRITER,
        Toml.SECTION_POLICY,
        Toml.SECTION_POLICY_BY_TYPE,
        Toml.SECTION_FILES,
    }


@pytest.mark.toml
def test_present_section_is_not_reported_as_missing_info_diagnostic() -> None:
    """Present known sections are excluded from missing-section INFO diagnostics."""
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_PATTERNS: ["src/**"],
            }
        }
    )
    assert parsed is not None

    missing_sections = {
        issue.section
        for issue in parsed.validation_issues
        if issue.code is TomlDiagnosticCode.MISSING_SECTION
    }

    assert Toml.SECTION_FILES not in missing_sections
    assert {
        Toml.SECTION_CONFIG,
        Toml.SECTION_HEADER,
        Toml.SECTION_FIELDS,
        Toml.SECTION_FORMATTING,
        Toml.SECTION_WRITER,
        Toml.SECTION_POLICY,
        Toml.SECTION_POLICY_BY_TYPE,
    }.issubset(missing_sections)


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
    """Missing `[tool.topmark]` returns `None`, while an empty table still parses.

    An empty table parses with missing-section INFO diagnostics.
    """
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

    missing_sections = {
        issue.section
        for issue in empty_parsed.validation_issues
        if issue.code is TomlDiagnosticCode.MISSING_SECTION
    }

    assert missing_sections == {
        Toml.SECTION_CONFIG,
        Toml.SECTION_HEADER,
        Toml.SECTION_FIELDS,
        Toml.SECTION_FORMATTING,
        Toml.SECTION_WRITER,
        Toml.SECTION_POLICY,
        Toml.SECTION_POLICY_BY_TYPE,
        Toml.SECTION_FILES,
    }
    assert all(
        issue.level is DiagnosticLevel.INFO
        for issue in empty_parsed.validation_issues
        if issue.code is TomlDiagnosticCode.MISSING_SECTION
    )


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
