# topmark:header:start
#
#   project      : TopMark
#   file         : test_schema_validation_policy.py
#   file_relpath : tests/toml/test_schema_validation_policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for nested `[policy_by_type.<filetype>]` TOML schema validation.

These tests cover the TOML-layer validation boundary for per-file-type policy
sections in `topmark.toml`:
- unknown keys inside nested policy tables,
- malformed nested section shapes,
- preservation of TOML validation payload details,
- and whether malformed nested policy entries become effective overrides.
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
