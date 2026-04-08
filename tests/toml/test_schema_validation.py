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

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import assert_not_warned
from tests.conftest import assert_warned_and_diagnosed
from tests.conftest import draft_from_topmark_toml_table
from tests.conftest import load_draft_from_topmark_toml
from topmark.config.policy import HeaderMutationMode
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
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

    draft: MutableConfig = load_draft_from_topmark_toml(p)

    # We should see a warning for the unknown key inside [files]
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "unknown_key" in [{Toml.SECTION_FILES}]',
    )
