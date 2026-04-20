# topmark:header:start
#
#   project      : TopMark
#   file         : test_schema_validation_missing_sections.py
#   file_relpath : tests/toml/test_schema_validation_missing_sections.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for missing-section TOML schema diagnostics.

These tests cover the TOML-layer behavior for empty or partially populated
TopMark TOML documents:
- empty-source handling,
- missing-section INFO diagnostics,
- and exclusion of present sections from missing-section diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.diagnostics import assert_not_warned
from tests.toml.conftest import draft_from_topmark_toml_table
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import DiagnosticStats
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml


# --- Missing-section and empty-source validation ---


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

    stats: DiagnosticStats = draft.validation_logs.flattened().stats()
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
