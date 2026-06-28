# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_rendering.py
#   file_relpath : tests/presentation/test_config_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for human-facing config presentation renderers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

import pytest
import tomlkit

import topmark.presentation.shared.config as shared_config
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.presentation.markdown.config import render_config_check_markdown
from topmark.presentation.markdown.config import render_config_defaults_markdown
from topmark.presentation.markdown.config import render_config_dump_markdown
from topmark.presentation.markdown.config import render_config_init_markdown
from topmark.presentation.shared.config import ConfigCheckHumanReport
from topmark.presentation.shared.config import ConfigDefaultsHumanReport
from topmark.presentation.shared.config import ConfigDumpHumanReport
from topmark.presentation.shared.config import ConfigInitHumanReport
from topmark.presentation.shared.config import build_config_check_human_report
from topmark.presentation.shared.config import build_config_defaults_human_report
from topmark.presentation.shared.config import build_config_dump_human_report
from topmark.presentation.shared.config import build_config_init_human_report
from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts
from topmark.presentation.shared.diagnostic import HumanDiagnosticLine
from topmark.presentation.text.config import render_config_check_text
from topmark.presentation.text.config import render_config_defaults_text
from topmark.presentation.text.config import render_config_dump_text
from topmark.presentation.text.config import render_config_init_text
from topmark.toml.parse import ParsedTopmarkToml
from topmark.toml.parse import SourceConfigLoadingOptions
from topmark.toml.parse import SourceTomlOptions
from topmark.toml.resolution import ResolvedTopmarkTomlSource
from topmark.toml.resolution import ResolvedTopmarkTomlSources

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.resolution.layers import ConfigLayer
    from topmark.toml.types import TomlTable


class _ConfigInitRenderer(Protocol):
    """Callable protocol for config init renderers."""

    def __call__(self, prepared: ConfigInitHumanReport) -> str:
        """Render a config init report."""
        ...


class _ConfigDefaultsRenderer(Protocol):
    """Callable protocol for config defaults renderers."""

    def __call__(self, prepared: ConfigDefaultsHumanReport) -> str:
        """Render a config defaults report."""
        ...


class _ConfigDumpRenderer(Protocol):
    """Callable protocol for config dump renderers."""

    def __call__(self, prepared: ConfigDumpHumanReport) -> str:
        """Render a config dump report."""
        ...


class _TemplateFallbackError(Exception):
    """Distinct fallback error used in config renderer tests."""


def _parsed_toml_fragment(fragment: TomlTable) -> ParsedTopmarkToml:
    """Return a parsed TOML object around a source-local fragment."""
    return ParsedTopmarkToml(
        config_loading_options=SourceConfigLoadingOptions(),
        layered_config=fragment,
        writer_options=None,
        source_options=SourceTomlOptions(),
        toml_fragment=fragment,
        validation_issues=(),
    )


def _counts() -> HumanDiagnosticCounts:
    """Return non-zero diagnostic counts for config presentation tests."""
    return HumanDiagnosticCounts(info=1, warning=1, error=1)


def _diagnostics() -> list[HumanDiagnosticLine]:
    """Return stable diagnostic lines for config presentation tests."""
    return [
        HumanDiagnosticLine(
            level="error",
            message="invalid setting",
        ),
        HumanDiagnosticLine(
            level="warning",
            message="deprecated setting",
        ),
        HumanDiagnosticLine(
            level="info",
            message="using defaults",
        ),
    ]


def _check_report(*, merged_toml: str | None, verbosity_level: int) -> ConfigCheckHumanReport:
    """Build a config-check report with diagnostics and config-file details."""
    return ConfigCheckHumanReport(
        config_files=["topmark.toml"],
        ok=False,
        strict=True,
        merged_toml=merged_toml,
        counts=_counts(),
        diagnostics=_diagnostics(),
        verbosity_level=verbosity_level,
        styled=False,
    )


def _dump_report(
    *,
    show_config_layers: bool,
    provenance_toml: str | None,
    verbosity_level: int,
) -> ConfigDumpHumanReport:
    """Build a config-dump report for text and Markdown renderer tests."""
    return ConfigDumpHumanReport(
        config_files=["topmark.toml"],
        merged_toml='project = "Example"\n',
        provenance_toml=provenance_toml,
        show_config_layers=show_config_layers,
        verbosity_level=verbosity_level,
        styled=False,
    )


def test_build_config_init_human_report_applies_root_before_pyproject_nesting() -> None:
    """Config init preparation should preserve root mode inside `[tool.topmark]`."""
    report: ConfigInitHumanReport = build_config_init_human_report(
        for_pyproject=True,
        root=True,
        verbosity_level=0,
        styled=False,
    )

    assert "[tool.topmark.config]" in report.toml_text
    assert "root = true" in report.toml_text
    assert report.error is None


def test_build_config_defaults_human_report_can_render_root_pyproject_defaults() -> None:
    """Config defaults preparation should render copyable pyproject-root TOML."""
    report: ConfigDefaultsHumanReport = build_config_defaults_human_report(
        for_pyproject=True,
        root=True,
        verbosity_level=0,
        styled=False,
    )

    assert "[tool.topmark.config]" in report.toml_text
    assert "root = true" in report.toml_text


def test_build_config_dump_human_report_with_empty_resolved_sources_exports_default_layer() -> None:
    """Layered dump preparation should always include the built-in defaults layer."""
    config: FrozenConfig = mutable_config_from_defaults().freeze()
    report: ConfigDumpHumanReport = build_config_dump_human_report(
        config=config,
        resolved_toml=ResolvedTopmarkTomlSources(
            sources=[],
            writer_options=None,
            strict=None,
        ),
        show_config_layers=True,
        verbosity_level=0,
        styled=False,
    )

    assert report.show_config_layers is True
    assert report.provenance_toml is not None
    assert "[[layers]]" in report.provenance_toml
    assert 'origin = "<defaults>"' in report.provenance_toml
    assert "[fields]" in report.merged_toml


def test_build_config_check_human_report_verbose_prepares_effective_toml() -> None:
    """Verbose config-check preparation should include rendered effective TOML."""
    config: FrozenConfig = mutable_config_from_defaults().freeze()
    report: ConfigCheckHumanReport = build_config_check_human_report(
        config=config,
        resolved_sources=ResolvedTopmarkTomlSources(
            sources=[],
            writer_options=None,
            strict=None,
        ),
        ok=True,
        strict=False,
        verbosity_level=2,
        styled=False,
    )

    assert report.ok is True
    assert report.strict is False
    assert report.merged_toml is not None
    assert "[fields]" in report.merged_toml
    assert report.counts.error == 0
    assert report.diagnostics == []


def test_render_config_init_markdown_without_fallback_returns_toml_only() -> None:
    """Markdown config init should omit fallback footer when no template error occurred."""
    output: str = render_config_init_markdown(
        ConfigInitHumanReport(
            toml_text='project = "Clean"\n',
            error=None,
            verbosity_level=0,
            styled=False,
        )
    )

    assert output.startswith("# Initial TopMark Configuration (TOML)")
    assert 'project = "Clean"' in output
    assert "Warning" not in output
    assert "Generated by TopMark" not in output


def test_render_config_check_text_without_diagnostics_reports_compact_ok_status() -> None:
    """TEXT config check should render a compact OK status without diagnostics."""
    output: str = render_config_check_text(
        ConfigCheckHumanReport(
            config_files=[],
            ok=True,
            strict=False,
            merged_toml=None,
            counts=HumanDiagnosticCounts(info=0, warning=0, error=0),
            diagnostics=[],
            verbosity_level=0,
            styled=False,
        )
    )

    assert "✅ Config OK (no diagnostics). [strict: off]" in output
    assert output.endswith("✅ OK")
    assert "Config files processed" not in output


def test_render_config_check_markdown_without_diagnostics_or_toml_omits_optional_sections() -> None:
    """Markdown config check should omit optional diagnostics and TOML sections when absent."""
    output: str = render_config_check_markdown(
        ConfigCheckHumanReport(
            config_files=[],
            ok=True,
            strict=False,
            merged_toml=None,
            counts=HumanDiagnosticCounts(info=0, warning=0, error=0),
            diagnostics=[],
            verbosity_level=0,
            styled=False,
        )
    )

    assert "- **Status:** OK" in output
    assert "### Diagnostics" not in output
    assert "### Effective merged TOML" not in output
    assert "### Config files processed (0)" in output


def test_render_config_dump_text_without_layers_verbose_includes_files_and_single_toml() -> None:
    """Verbose TEXT config dump should render loaded files and one flattened TOML block."""
    output: str = render_config_dump_text(
        _dump_report(
            show_config_layers=False,
            provenance_toml=None,
            verbosity_level=1,
        )
    )

    assert "Config files processed: 1" in output
    assert "Loaded config 1: topmark.toml" in output
    assert "TopMark Config Dump (TOML):" in output
    assert "TopMark Config Provenance Layers" not in output
    assert 'project = "Example"' in output


def test_build_config_dump_human_report_exports_file_backed_source_layer(
    tmp_path: Path,
) -> None:
    """Layered dump preparation should include file-backed source fragments."""
    config_path: Path = tmp_path / "topmark.toml"
    config_path.write_text('[fields]\nproject = "Layered"\n', encoding="utf-8")
    fragment: TomlTable = {"fields": {"project": "Layered"}}
    config: FrozenConfig = mutable_config_from_defaults().freeze()

    report: ConfigDumpHumanReport = build_config_dump_human_report(
        config=config,
        resolved_toml=ResolvedTopmarkTomlSources(
            sources=[
                ResolvedTopmarkTomlSource(
                    path=config_path,
                    parsed=_parsed_toml_fragment(fragment),
                    kind="explicit",
                    validation_issues=(),
                    load_diagnostics=MutableDiagnosticLog().freeze(),
                )
            ],
            writer_options=None,
            strict=None,
        ),
        show_config_layers=True,
        verbosity_level=0,
        styled=False,
    )

    assert report.provenance_toml is not None

    # Parse the rendered TOML before asserting path values. Comparing the raw
    # serialized string is platform-dependent because TOML escapes Windows
    # backslashes (e.g. `C:\\Users\\...`), whereas the parsed value preserves
    # the original native path representation.
    data: tomlkit.TOMLDocument = tomlkit.loads(report.provenance_toml)
    assert data["layers"][1]["scope_root"] == str(tmp_path)

    # These fields are platform-independent and may be asserted directly on the
    # serialized TOML.
    assert 'kind = "explicit"' in report.provenance_toml
    assert 'project = "Layered"' in report.provenance_toml


@pytest.mark.parametrize(
    ("renderer", "expected_title"),
    [
        (render_config_init_text, "Initial TopMark Configuration (TOML):"),
        (render_config_init_markdown, "# Initial TopMark Configuration (TOML)"),
    ],
)
def test_config_init_renderers_include_fallback_warning(
    renderer: _ConfigInitRenderer,
    expected_title: str,
) -> None:
    """Config init renderers should preserve TOML and surface template fallbacks."""
    report = ConfigInitHumanReport(
        toml_text='project = "Fallback"\n',
        error=_TemplateFallbackError("template missing"),
        verbosity_level=1,
        styled=False,
    )

    output: str = renderer(report)

    assert expected_title in output
    assert "falling back to synthesized default config: template missing" in output
    assert 'project = "Fallback"' in output


@pytest.mark.parametrize(
    ("renderer", "expected_title"),
    [
        (render_config_defaults_text, "Default TopMark Configuration (TOML):"),
        (render_config_defaults_markdown, "# Default TopMark Configuration (TOML)"),
    ],
)
def test_config_defaults_renderers_include_toml_document(
    renderer: _ConfigDefaultsRenderer,
    expected_title: str,
) -> None:
    """Config defaults renderers should expose the generated TOML document."""
    report = ConfigDefaultsHumanReport(
        toml_text='project = "Defaults"\n',
        verbosity_level=1,
        styled=False,
    )

    output: str = renderer(report)

    assert expected_title in output
    assert 'project = "Defaults"' in output


def test_render_config_init_text_without_fallback_omits_warning() -> None:
    """TEXT config init should omit fallback warning when template loading succeeded."""
    output: str = render_config_init_text(
        ConfigInitHumanReport(
            toml_text='project = "Clean"\n',
            error=None,
            verbosity_level=0,
            styled=False,
        )
    )

    assert 'project = "Clean"' in output
    assert "falling back to synthesized default config" not in output


def test_build_config_dump_human_report_handles_empty_layer_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layered dump preparation should render a valid empty layers document defensively."""

    def no_config_layers(
        sources: list[ResolvedTopmarkTomlSource],
    ) -> list[ConfigLayer]:
        return []

    monkeypatch.setattr(
        shared_config,
        "build_config_layers_from_resolved_toml_sources",
        no_config_layers,
    )

    config: FrozenConfig = mutable_config_from_defaults().freeze()
    report: ConfigDumpHumanReport = build_config_dump_human_report(
        config=config,
        resolved_toml=ResolvedTopmarkTomlSources(
            sources=[],
            writer_options=None,
            strict=None,
        ),
        show_config_layers=True,
        verbosity_level=0,
        styled=False,
    )

    assert report.provenance_toml == "layers = []\n"


def test_render_config_check_text_verbose_includes_diagnostics_files_and_toml() -> None:
    """Verbose TEXT config check should include diagnostics, files, and merged TOML."""
    output: str = render_config_check_text(
        _check_report(
            merged_toml='project = "Checked"\n',
            verbosity_level=2,
        )
    )

    assert "Diagnostics: 1 error(s), 1 warning(s), 1 information(s)" in output
    assert "- error: invalid setting" in output
    assert "Loaded config 1: topmark.toml" in output
    assert "TopMark Config (TOML):" in output
    assert 'project = "Checked"' in output
    assert "❌ FAILED" in output


def test_render_config_check_markdown_includes_diagnostics_files_and_toml() -> None:
    """Markdown config check should include diagnostics, files, and merged TOML."""
    output: str = render_config_check_markdown(
        _check_report(
            merged_toml='project = "Checked"\n',
            verbosity_level=0,
        )
    )

    assert "- **Status:** FAILED" in output
    assert "### Diagnostics" in output
    assert "- **error**: invalid setting" in output
    assert "1. topmark.toml" in output
    assert "### Effective merged TOML" in output
    assert 'project = "Checked"' in output


@pytest.mark.parametrize(
    ("renderer", "separator"),
    [
        (render_config_dump_text, "TopMark Config Provenance Layers (TOML):"),
        (render_config_dump_markdown, "---"),
    ],
)
def test_config_dump_renderers_include_layered_and_flattened_documents(
    renderer: _ConfigDumpRenderer,
    separator: str,
) -> None:
    """Config dump renderers should show provenance before flattened TOML."""
    report: ConfigDumpHumanReport = _dump_report(
        show_config_layers=True,
        provenance_toml='[[layers]]\nkind = "default"\n',
        verbosity_level=0,
    )

    output: str = renderer(report)

    assert separator in output
    assert 'kind = "default"' in output
    assert 'project = "Example"' in output
    assert output.find('kind = "default"') < output.find('project = "Example"')


def test_render_config_dump_markdown_without_layers_uses_single_dump_heading() -> None:
    """Markdown config dump should have a single TOML heading without layer data."""
    output: str = render_config_dump_markdown(
        _dump_report(
            show_config_layers=False,
            provenance_toml=None,
            verbosity_level=0,
        )
    )

    assert "# TopMark Config Dump (TOML)" in output
    assert "TopMark Config Provenance Layers" not in output
    assert 'project = "Example"' in output
