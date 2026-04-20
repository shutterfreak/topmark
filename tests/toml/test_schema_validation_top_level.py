# topmark:header:start
#
#   project      : TopMark
#   file         : test_schema_validation_top_level.py
#   file_relpath : tests/toml/test_schema_validation_top_level.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for top-level and closed-section TopMark TOML schema validation.

These tests cover the TOML-layer validation boundary for whole-source
`topmark.toml` inputs:
- unknown top-level keys and sections,
- unknown keys inside closed known sections,
- malformed known section shapes,
- and the resulting TOML validation issue payloads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.diagnostics import assert_warned_and_diagnosed
from tests.toml.conftest import draft_from_topmark_toml_table
from topmark.config.policy import HeaderMutationMode
from topmark.diagnostic.model import DiagnosticLevel
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlValue


# --- In-memory whole-source TOML validation ---


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
