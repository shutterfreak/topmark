# topmark:header:start
#
#   project      : TopMark
#   file         : test_bridge.py
#   file_relpath : tests/config/resolution/test_bridge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Regression tests for TOML-to-config bridge helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.paths import symlink_or_skip
from topmark.config.resolution import bridge
from topmark.config.resolution.bridge import resolve_default_table_and_build_mutable_config
from topmark.config.resolution.bridge import resolve_default_template_and_build_mutable_config
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.constants import EXAMPLE_TOPMARK_TOML_NAME
from topmark.core.constants import EXAMPLE_TOPMARK_TOML_PACKAGE
from topmark.toml.defaults import DefaultTomlTemplateText
from topmark.toml.resolution import resolve_topmark_toml_sources

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.diagnostic.model import MutableDiagnosticLog
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


def test_default_template_resolves_without_errors() -> None:
    """The bundled starter template should resolve without error diagnostics."""
    resolved_config: ResolvedConfigDraft = resolve_default_template_and_build_mutable_config()

    assert len(resolved_config.resolved.sources) == 1
    diagnostics: MutableDiagnosticLog = resolved_config.draft.validation_logs.flattened()
    assert not diagnostics.has_error, (
        f"An error occurred during parsing of the built-in TOML resource "
        f"in {EXAMPLE_TOPMARK_TOML_PACKAGE}/{EXAMPLE_TOPMARK_TOML_NAME}: "
        f"{diagnostics}"
    )
    assert resolved_config.draft.config_files == [
        SyntheticConfigSource(
            label="<bundled topmark-template.toml>",
        ),
    ]
    assert resolved_config.resolved.writer_options is not None


def test_builtin_defaults_resolve_without_errors() -> None:
    """The canonical built-in default table should resolve without errors."""
    resolved_config: ResolvedConfigDraft = resolve_default_table_and_build_mutable_config()

    assert len(resolved_config.resolved.sources) == 1
    diagnostics: MutableDiagnosticLog = resolved_config.draft.validation_logs.flattened()
    assert not diagnostics.has_error, (
        f"An error occurred during parsing of the built-in TOML defaults: {diagnostics}"
    )
    assert resolved_config.draft.config_files == [
        SyntheticConfigSource(
            label="<built-in topmark defaults>",
        ),
    ]
    assert resolved_config.resolved.writer_options is not None


def test_explicit_config_symlink_resolves_to_target_path(tmp_path: Path) -> None:
    """Explicit config sources use the resolved target path as source identity."""
    target_config: Path = tmp_path / "real" / "topmark.toml"
    target_config.parent.mkdir(parents=True)
    target_config.write_text("[config]\nstrict = true\n", encoding="utf-8")
    link_config: Path = symlink_or_skip(tmp_path / "links" / "topmark.toml", target_config)

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=[tmp_path],
        extra_config_files=[link_config],
        no_config=True,
    )

    assert len(resolved.sources) == 1
    assert resolved.sources[0].kind == "explicit"
    assert resolved.sources[0].path == target_config.resolve()
    assert resolved.sources[0].path != link_config
    assert resolved.strict is True


def test_duplicate_config_source_identity_keeps_highest_precedence_entry(
    tmp_path: Path,
) -> None:
    """Duplicate resolved config-source identities should be merged once."""
    config_file: Path = tmp_path / "topmark.toml"
    config_file.write_text("[config]\nstrict = true\n", encoding="utf-8")

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=[tmp_path],
        extra_config_files=[config_file],
    )

    assert len(resolved.sources) == 1
    assert resolved.sources[0].kind == "explicit"
    assert resolved.sources[0].path == config_file.resolve()
    assert resolved.strict is True


def test_duplicate_symlinked_config_source_identity_is_deduplicated(
    tmp_path: Path,
) -> None:
    """A symlinked config and its target should resolve to one source identity."""
    target_config: Path = tmp_path / "real" / "topmark.toml"
    target_config.parent.mkdir(parents=True)
    target_config.write_text("[config]\nstrict = true\n", encoding="utf-8")
    link_config: Path = symlink_or_skip(tmp_path / "links" / "topmark.toml", target_config)

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=[tmp_path],
        extra_config_files=[target_config, link_config],
        no_config=True,
    )

    assert len(resolved.sources) == 1
    assert resolved.sources[0].kind == "explicit"
    assert resolved.sources[0].path == target_config.resolve()
    assert resolved.sources[0].path != link_config
    assert resolved.strict is True


def test_default_template_replays_template_load_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Template fallback errors should be replayed into config diagnostics."""
    fallback_text: str = """
[header]
fields = ["file"]

[formatting]
align_fields = true

[policy]
header_mutation_mode = "all"
allow_header_in_empty_files = false
empty_insert_mode = "logical_empty"

[files]
include_from = []
exclude_from = []
files_from = []
include_patterns = []
exclude_patterns = []
include_file_types = []
exclude_file_types = []
files = []
"""

    def fake_load_default_topmark_template_toml_text() -> DefaultTomlTemplateText:
        return DefaultTomlTemplateText(
            toml_text=fallback_text,
            error=OSError("template unavailable"),
        )

    monkeypatch.setattr(
        bridge,
        "load_default_topmark_template_toml_text",
        fake_load_default_topmark_template_toml_text,
    )

    resolved_config: ResolvedConfigDraft = resolve_default_template_and_build_mutable_config()

    assert any(
        diagnostic.message == "template unavailable"
        for diagnostic in resolved_config.draft.validation_logs.toml_source.items
    )
