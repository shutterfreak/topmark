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
from topmark.config.resolution.bridge import resolve_default_table_and_build_mutable_config
from topmark.config.resolution.bridge import resolve_default_template_and_build_mutable_config
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.constants import EXAMPLE_TOPMARK_TOML_NAME
from topmark.core.constants import EXAMPLE_TOPMARK_TOML_PACKAGE
from topmark.toml.resolution import resolve_topmark_toml_sources

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.diagnostic.model import MutableDiagnosticLog


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

    resolved = resolve_topmark_toml_sources(
        input_paths=[tmp_path],
        extra_config_files=[link_config],
        no_config=True,
    )

    assert len(resolved.sources) == 1
    assert resolved.sources[0].kind == "explicit"
    assert resolved.sources[0].path == target_config.resolve()
    assert resolved.sources[0].path != link_config
    assert resolved.strict is True
