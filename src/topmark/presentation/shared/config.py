# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/presentation/shared/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared data preparation for config CLI emitters.

This module contains Click-free helpers that *prepare* domain data for human-facing emitters
(TEXT / MARKDOWN).

It intentionally sits between:

- configuration I/O helpers in [`topmark.config.io`][topmark.config.io], and
- renderers in [`topmark.presentation.text.config`][topmark.presentation.text.config] (ANSI) and
  [`topmark.presentation.markdown.config`][topmark.presentation.markdown.config] (Markdown).

Notes:
    These helpers may perform light serialization work and may load bundled
    template resources. They do not print to stdout/stderr; user-facing
    warnings should be handled by the caller or the emitters.
    Where human-facing config diagnostics are prepared, this module flattens
    staged config-validation logs at the presentation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.io.serializers import config_to_topmark_toml_table
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts
from topmark.presentation.shared.diagnostic import HumanDiagnosticLine
from topmark.presentation.shared.diagnostic import prepare_human_diagnostics
from topmark.toml.defaults import build_default_topmark_toml_table
from topmark.toml.defaults import load_default_topmark_template_toml_text
from topmark.toml.defaults import render_default_topmark_toml_text
from topmark.toml.render import clean_toml_text
from topmark.toml.render import render_toml_table
from topmark.toml.surgery import nest_toml_under_section
from topmark.toml.surgery import set_root_flag
from topmark.toml.template_surgery import set_root_flag_in_template_text
from topmark.toml.template_surgery import validate_toml_for_config_init
from topmark.toml.utils import as_toml_table_list

if TYPE_CHECKING:
    from topmark.config.model import Config
    from topmark.config.resolution.layers import ConfigLayer
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.toml.resolution import ResolvedTopmarkTomlSources
    from topmark.toml.types import TomlTable


# --- Prepare initial / default configuration documents ---


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigInitHumanReport:
    """Prepared payload for `topmark config init` (human formats).

    Attributes:
        toml_text: Starter configuration TOML text (annotated template).
        error: Optional exception raised while reading the bundled template. When set, callers may
            render a warning and still proceed with the returned TOML text (which may be a
            synthesized fallback).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)
    """

    toml_text: str
    error: Exception | None
    verbosity_level: int
    styled: bool


def build_config_init_human_report(
    *,
    for_pyproject: bool,
    root: bool,
    verbosity_level: int,
    styled: bool,
) -> ConfigInitHumanReport:
    """Prepare human-facing data for `topmark config init`.

    The annotated template is authored in plain `topmark.toml` shape. Template
    edits therefore happen in that plain shape first:

    1. load the annotated template (or generated fallback)
    2. optionally set `[config].root = true` in the plain template text
    3. if `for_pyproject=True`, nest the whole document under `[tool.topmark]`
    4. validate the final output shape as a defensive backstop

    Args:
        for_pyproject: If `True`, nest the final document under `[tool.topmark]`.
        root: If `True`, set `[config].root = true` before any optional nesting.
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT).

    Returns:
        Prepared TOML text plus optional template read error.
    """
    toml_text, err = load_default_topmark_template_toml_text()

    changed = False

    if root:
        res = set_root_flag_in_template_text(
            toml_text,
            for_pyproject=False,
            root=True,
        )
        toml_text, changed = res.text, (changed or res.changed)

    if for_pyproject:
        nested_text: str = nest_toml_under_section(
            toml_text,
            "tool.topmark",
        )  # Raises ValueError, TomlParseError, TomlSurgeryError.

        changed: bool = changed or (nested_text != toml_text)
        toml_text: str = nested_text

    # TOML correctness backstop (raises )
    validate_toml_for_config_init(
        toml_text,
        for_pyproject=for_pyproject,
        root_expected=root,
    )  # Raises TemplateValidationError.

    return ConfigInitHumanReport(
        toml_text=toml_text,
        error=err,
        verbosity_level=verbosity_level,
        styled=styled,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigDefaultsHumanReport:
    """Prepared TOML payload for `topmark config defaults`.

    This is the *cleaned* default configuration (copy/paste friendly).

    Attributes:
        toml_text: Cleaned TOML text. When prepared with `for_pyproject=True`, the TOML is nested
            under `[tool.topmark]`.
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    """

    toml_text: str
    verbosity_level: int
    styled: bool


def build_config_defaults_human_report(
    *,
    for_pyproject: bool,
    root: bool,
    verbosity_level: int,
    styled: bool,
) -> ConfigDefaultsHumanReport:
    """Prepare human-facing data for `topmark config defaults`.

    Renders the centralized default TopMark TOML document, optionally nests it under
    `[tool.topmark]`, then cleans it for copy/paste.

    Args:
        for_pyproject: If True, nest the TOML under `[tool.topmark]`.
        root: If True, set `root = true` (top-level or tool.topmark.root).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    Returns:
        Prepared cleaned TOML text.
    """
    toml_text: str = render_default_topmark_toml_text(for_pyproject=for_pyproject)

    if root:
        toml_text = set_root_flag(toml_text, for_pyproject=for_pyproject, root=True)
        # Raises TomlParseError, TomlSurgeryError.

    cleaned: str = clean_toml_text(toml_text)
    return ConfigDefaultsHumanReport(
        toml_text=cleaned,
        verbosity_level=verbosity_level,
        styled=styled,
    )


# --- Check a resolved Config


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigCheckHumanReport:
    """Prepared human-facing data for `topmark config check`.

    Attributes:
        config_files: Config files contributing to the effective config (stringified paths).
        ok: Whether the configuration passed validation.
        strict: Whether strict checking was enabled.
        merged_toml: Effective merged configuration as TOML, or None when not requested
            (typically only included at verbosity >= 2).
        counts: Human diagnostic counts.
        diagnostics: Human diagnostic lines (ordered).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    """

    config_files: list[str]
    ok: bool
    strict: bool
    merged_toml: str | None
    counts: HumanDiagnosticCounts
    diagnostics: list[HumanDiagnosticLine]
    verbosity_level: int
    styled: bool


def _stringify_config_files(config: Config) -> list[str]:
    """Return `config.config_files` as a list of string paths.

    This keeps prepared payloads Click-free and renderer-friendly by avoiding `Path` objects in the
    shared prepared shapes.
    """
    return [str(p) for p in config.config_files]


def build_config_check_human_report(
    *,
    config: Config,
    ok: bool,
    strict: bool,
    verbosity_level: int,
    styled: bool,
) -> ConfigCheckHumanReport:
    """Prepare human-facing data for `topmark config check`.

    This helper is Click-free and may perform light computation (counts, string normalization).
    It does not print.

    Args:
        config: Effective frozen configuration.
        ok: Whether the configuration passed validation.
        strict: Whether strict checking was enabled.
        verbosity_level: Effective verbosity (used for gating heavy/verbose sections).
        styled: Whether to style text output (OutputFormat.TEXT)

    Returns:
        Prepared config file list, optional merged TOML (verbosity > 1), plus
        human diagnostic counts and lines derived from the flattened
        compatibility view of staged config-validation logs.
    """
    merged_toml: str | None = None
    if verbosity_level > 1:
        merged_toml = render_toml_table(
            config_to_topmark_toml_table(
                config,
                include_files=False,
            )
        )

    # Flatten staged validation logs here so human-facing reports keep the
    # current compatibility diagnostics view.
    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()
    counts, lines = prepare_human_diagnostics(flattened_diagnostics)

    return ConfigCheckHumanReport(
        config_files=_stringify_config_files(config),
        ok=ok,
        strict=strict,
        merged_toml=merged_toml,
        counts=counts,
        diagnostics=lines,
        styled=styled,
        verbosity_level=verbosity_level,
    )


# --- Dump a resolved Config


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigDumpHumanReport:
    """Prepared human-facing data for `topmark config dump`.

    Attributes:
        config_files: Config files contributing to the effective config, rendered
            as stringified paths.
        merged_toml: Final flattened effective configuration rendered as TOML.
        provenance_toml: Optional layered TOML provenance export rendered as
            TOML. When present, this is an inspection-oriented document whose
            `[[layers]]` entries preserve provenance metadata and expose each
            source-local TOML fragment under `[layers.toml.*]`.
        show_config_layers: Whether layered provenance output was requested.
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT).
    """

    config_files: list[str]
    merged_toml: str
    provenance_toml: str | None
    show_config_layers: bool
    verbosity_level: int
    styled: bool


def _build_layer_export_table(
    *,
    layer: ConfigLayer,
    toml_fragment: TomlTable,
) -> TomlTable:
    """Return one exported provenance layer as a TOML table.

    Args:
        layer: One resolved config layer with provenance metadata.
        toml_fragment: Full source-local TopMark TOML fragment for this layer.

    Returns:
        A TOML table ready for inclusion in the layered provenance export.

    Notes:
        The returned table is intentionally export-oriented. It preserves
        provenance metadata at the layer level and nests the corresponding
        source-local TOML fragment under the `toml` key so that rendering
        produces `[layers.toml.*]` tables.
    """
    table: TomlTable = {
        "origin": str(layer.origin),
        "kind": layer.kind.value,
        "precedence": layer.precedence,
        "toml": toml_fragment,
    }
    if layer.scope_root is not None:
        table["scope_root"] = str(layer.scope_root)
    return table


def _build_config_layers_provenance_toml(
    resolved_toml: ResolvedTopmarkTomlSources,
) -> str:
    """Render layered TopMark TOML provenance as a valid export document.

    The export is inspection-oriented rather than directly loadable as a normal
    `topmark.toml` file. Each `[[layers]]` entry preserves provenance metadata
    and exposes the source-local TOML fragment under `[layers.toml.*]`.

    Args:
        resolved_toml: Resolved TOML sources for the current run.

    Returns:
        The layered provenance document rendered as valid TOML.
    """
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved_toml.sources
    )

    exported_layers: list[TomlTable] = []

    if layers:
        default_layer: ConfigLayer = layers[0]
        exported_layers.append(
            _build_layer_export_table(
                layer=default_layer,
                toml_fragment=build_default_topmark_toml_table(),
            )
        )

    for layer, source in zip(layers[1:], resolved_toml.sources, strict=True):
        exported_layers.append(
            _build_layer_export_table(
                layer=layer,
                toml_fragment=source.parsed.toml_fragment,
            )
        )

    export_doc: TomlTable = {
        "layers": as_toml_table_list(exported_layers),
    }
    return render_toml_table(export_doc)


def build_config_dump_human_report(
    *,
    config: Config,
    resolved_toml: ResolvedTopmarkTomlSources,
    show_config_layers: bool,
    styled: bool,
    verbosity_level: int,
) -> ConfigDumpHumanReport:
    """Prepare human-facing data for `topmark config dump`.

    This helper is Click-free: it performs TOML serialization for the
    flattened effective config and, when requested, also prepares a layered
    TOML provenance export.

    Args:
        config: Effective frozen configuration.
        resolved_toml: Resolved TOML sources used to build the optional layered
            provenance export.
        show_config_layers: If `True`, include a layered TOML provenance export
            before the flattened config dump.
        styled: Whether to style text output (OutputFormat.TEXT).
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Prepared config file list, flattened TOML text, and optional layered
        TOML provenance export.
    """
    # Build the optional inspection-oriented provenance document only when the
    # caller explicitly requests layered output.
    provenance_toml: str | None = None
    merged_toml: str = render_toml_table(
        config_to_topmark_toml_table(
            config,
            include_files=False,
        )
    )
    if show_config_layers:
        provenance_toml = _build_config_layers_provenance_toml(resolved_toml)

    return ConfigDumpHumanReport(
        config_files=_stringify_config_files(config),
        merged_toml=merged_toml,
        provenance_toml=provenance_toml,
        show_config_layers=show_config_layers,
        styled=styled,
        verbosity_level=verbosity_level,
    )
