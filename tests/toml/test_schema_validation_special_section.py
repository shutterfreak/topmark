# topmark:header:start
#
#   project      : TopMark
#   file         : test_schema_validation_special_section.py
#   file_relpath : tests/toml/test_schema_validation_special_section.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for special-case TopMark TOML schema validation rules.

These tests cover TOML-layer validation semantics that differ from ordinary
closed-section validation:
- free-form `[fields]` behavior,
- source-local `[config]` validation,
- `[writer]` validation,
- and dump-only keys that are invalid in ordinary input mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.diagnostics import assert_not_warned
from tests.helpers.diagnostics import assert_warned_and_diagnosed
from tests.toml.conftest import draft_from_topmark_toml_table
from topmark.diagnostic.model import DiagnosticLevel
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml


# --- In-memory special-section validation ---


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


# --- Source-local and dump-only section rules ---


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
