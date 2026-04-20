# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_strictness_and_validity.py
#   file_relpath : tests/config/test_config_strictness_and_validity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for resolved strictness and config validity behavior.

These tests exercise:
- strictness resolution from `[config].strict_config_checking`,
- explicit strictness overrides,
- `MutableConfig.is_valid()` / `Config.is_valid()` semantics,
- and preservation of diagnostics across `freeze()`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.config import make_mutable_config
from tests.helpers.diagnostics import NON_EMPTY
from tests.helpers.diagnostics import assert_diagnostic_level_stats
from tests.helpers.diagnostics import assert_validation_stage_totals
from tests.toml.conftest import write_toml_document
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.config.model import MutableConfig


@pytest.mark.config
def test_load_resolved_config_applies_strictness_from_config_table(
    tmp_path: Path,
) -> None:
    """Resolved TOML strictness is applied to the merged compatibility draft."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            [config]
            strict_config_checking = true
        """,
    )

    resolved, _draft = resolve_toml_sources_and_build_config_draft(input_paths=[proj])
    assert resolved.strict_config_checking is True


@pytest.mark.config
def test_explicit_strictness_override_false_wins_over_resolved_true(
    tmp_path: Path,
) -> None:
    """An explicit strictness override of False wins over resolved TOML strictness."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            [config]
            strict_config_checking = true
        """,
    )

    resolved, _draft = resolve_toml_sources_and_build_config_draft(
        input_paths=[proj],
        strict_config_checking=False,
    )
    assert resolved.strict_config_checking is False


@pytest.mark.config
def test_explicit_strictness_override_true_wins_over_resolved_false(
    tmp_path: Path,
) -> None:
    """An explicit strictness override of True wins over resolved TOML strictness."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            [config]
            strict_config_checking = false
        """,
    )

    resolved, _draft = resolve_toml_sources_and_build_config_draft(
        input_paths=[proj],
        strict_config_checking=True,
    )
    assert resolved.strict_config_checking is True


@pytest.mark.config
def test_replayed_toml_warning_is_non_strict_valid_but_strict_invalid(
    tmp_path: Path,
) -> None:
    """Replayed TOML warnings participate in strict validity but not non-strict validity."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            bogus = 123

            [header]
            fields = ["file"]
        """,
    )

    _resolved, draft = resolve_toml_sources_and_build_config_draft(input_paths=[proj])

    assert_validation_stage_totals(
        draft.validation_logs,
        toml=NON_EMPTY,
        config=0,
        runtime=0,
    )

    assert draft.is_valid() is True
    assert draft.is_valid(strict=True) is False

    frozen: Config = draft.freeze()

    assert_validation_stage_totals(
        frozen.validation_logs,
        toml=NON_EMPTY,
        config=0,
        runtime=0,
    )

    assert frozen.is_valid() is True
    assert frozen.is_valid(strict=True) is False


@pytest.mark.config
def test_missing_section_info_does_not_fail_even_when_strict(
    tmp_path: Path,
) -> None:
    """Missing-section INFO diagnostics do not fail config validity, even in strict mode."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            [header]
            fields = ["file"]
        """,
    )

    _resolved, draft = resolve_toml_sources_and_build_config_draft(input_paths=[proj])

    assert draft.is_valid() is True
    assert draft.is_valid(strict=True) is True

    assert_diagnostic_level_stats(
        stats=draft.diagnostics.stats(),
        expected_info=NON_EMPTY,
        expected_warning=0,
        expected_error=0,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=NON_EMPTY,
        config=0,
        runtime=0,
    )

    frozen: Config = draft.freeze()
    assert frozen.is_valid() is True
    assert frozen.is_valid(strict=True) is True

    assert_validation_stage_totals(
        frozen.validation_logs,
        toml=NON_EMPTY,
        config=0,
        runtime=0,
    )


@pytest.mark.config
def test_sanitization_warning_is_non_strict_valid_but_strict_invalid() -> None:
    """Sanitization warnings participate in strict validity but not non-strict validity."""
    draft: MutableConfig = make_mutable_config(include_from=["patterns/*.txt"])

    assert_diagnostic_level_stats(
        stats=draft.diagnostics.stats(),
        expected_warning=0,
    )

    draft.sanitize()

    assert_diagnostic_level_stats(
        stats=draft.diagnostics.stats(),
        expected_warning=NON_EMPTY,
    )
    assert_validation_stage_totals(
        draft.validation_logs,
        toml=0,
        config=0,
        runtime=NON_EMPTY,
    )

    assert draft.is_valid() is True
    assert draft.is_valid(strict=True) is False

    frozen: Config = draft.freeze()
    assert frozen.is_valid() is True
    assert frozen.is_valid(strict=True) is False

    assert_validation_stage_totals(
        frozen.validation_logs,
        toml=0,
        config=0,
        runtime=NON_EMPTY,
    )


@pytest.mark.config
def test_is_valid_false_on_errors() -> None:
    """Merged-config errors always make the config invalid."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_error("boom")
    draft.refresh_diagnostics()
    assert draft.is_valid() is False

    c: Config = draft.freeze()
    assert c.is_valid() is False


@pytest.mark.config
def test_is_valid_true_on_warnings() -> None:
    """Merged-config warnings do not make the config invalid by default."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_warning("warn")
    draft.refresh_diagnostics()
    assert draft.is_valid() is True

    c: Config = draft.freeze()
    assert c.is_valid() is True


@pytest.mark.config
def test_is_valid_false_on_warnings_when_strict() -> None:
    """Merged-config warnings make the config invalid when strict mode is enabled."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_warning("warn")
    draft.refresh_diagnostics()
    assert draft.is_valid(strict=True) is False

    c: Config = draft.freeze()
    assert c.is_valid(strict=True) is False


@pytest.mark.config
def test_freeze_preserves_diagnostics() -> None:
    """freeze() must preserve flattened diagnostics derived from staged logs."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_warning("hello")
    draft.refresh_diagnostics()
    c: Config = draft.freeze()
    assert len(c.diagnostics.items) == 1
    assert c.diagnostics.items[0].message == "hello"
    assert_validation_stage_totals(
        c.validation_logs,
        toml=0,
        config=NON_EMPTY,
        runtime=0,
    )
