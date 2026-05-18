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

from topmark.config.resolution.bridge import resolve_default_table_and_build_mutable_config
from topmark.config.resolution.bridge import resolve_default_template_and_build_mutable_config
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.constants import EXAMPLE_TOPMARK_TOML_NAME
from topmark.core.constants import EXAMPLE_TOPMARK_TOML_PACKAGE

if TYPE_CHECKING:
    from topmark.diagnostic.model import MutableDiagnosticLog


def test_default_template_resolves_without_errors() -> None:
    """The bundled starter template should resolve without error diagnostics."""
    resolved_toml, draft_config = resolve_default_template_and_build_mutable_config()

    assert len(resolved_toml.sources) == 1
    diagnostics: MutableDiagnosticLog = draft_config.validation_logs.flattened()
    assert not diagnostics.has_error(), (
        f"An error occurred during parsing of the built-in TOML resource "
        f"in {EXAMPLE_TOPMARK_TOML_PACKAGE}/{EXAMPLE_TOPMARK_TOML_NAME}: "
        f"{diagnostics}"
    )
    assert draft_config.config_files == [
        SyntheticConfigSource(
            label="<bundled topmark-template.toml>",
        ),
    ]
    assert resolved_toml.writer_options is not None


def test_builtin_defaults_resolve_without_errors() -> None:
    """The canonical built-in default table should resolve without errors."""
    resolved_toml, draft_config = resolve_default_table_and_build_mutable_config()

    assert len(resolved_toml.sources) == 1
    diagnostics = draft_config.validation_logs.flattened()
    assert not diagnostics.has_error(), (
        f"An error occurred during parsing of the built-in TOML defaults: {diagnostics}"
    )
    assert draft_config.config_files == [
        SyntheticConfigSource(
            label="<built-in topmark defaults>",
        ),
    ]
    assert resolved_toml.writer_options is not None
