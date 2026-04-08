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
def test_is_valid_false_on_errors() -> None:
    """Errors always make the config invalid."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.diagnostics.add_error("boom")
    assert draft.is_valid() is False

    c: Config = draft.freeze()
    assert c.is_valid() is False


@pytest.mark.config
def test_is_valid_true_on_warnings() -> None:
    """Warnings do not make the config invalid by default."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.diagnostics.add_warning("warn")
    assert draft.is_valid() is True

    c: Config = draft.freeze()
    assert c.is_valid() is True


@pytest.mark.config
def test_is_valid_false_on_warnings_when_strict() -> None:
    """Warnings make the config invalid when strict mode is enabled."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.diagnostics.add_warning("warn")
    assert draft.is_valid(strict=True) is False

    c: Config = draft.freeze()
    assert c.is_valid(strict=True) is False


@pytest.mark.config
def test_freeze_preserves_diagnostics() -> None:
    """freeze() must preserve diagnostics when producing an immutable Config."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.diagnostics.add_warning("hello")
    c: Config = draft.freeze()
    assert len(c.diagnostics.items) == 1
    assert c.diagnostics.items[0].message == "hello"
