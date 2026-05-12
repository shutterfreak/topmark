# topmark:header:start
#
#   project      : TopMark
#   file         : bridge.py
#   file_relpath : src/topmark/config/resolution/bridge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Bridge helpers between TOML source resolution and config draft construction.

This module defines the small public bridge between TOML-side source
resolution (`topmark.toml.resolution`) and config-side draft construction.
It performs no per-path applicability checks and no runtime override
application.

Its diagnostics role is to replay source-level TOML validation issues into the
merged config draft's TOML-source validation stage so later staged
config/preflight validation sees the full config-loading diagnostic picture.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import tomlkit

from topmark.config.resolution.layers import ConfigLayer
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import merge_layers_globally
from topmark.config.resolution.synthetic import BUILTIN_DEFAULTS_TOML_SOURCE
from topmark.config.resolution.synthetic import BUNDLED_TEMPLATE_TOML_SOURCE
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.core.typing_guards import as_object_dict
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.toml.defaults import build_default_topmark_toml_table
from topmark.toml.defaults import load_default_topmark_template_toml_text
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.resolution import ResolvedTopmarkTomlSource
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.resolution import resolve_topmark_toml_sources
from topmark.toml.typing_guards import toml_table_from_mapping
from topmark.toml.validation import add_toml_issues

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlTable


# ---- Public TOML -> config bridge helpers ----


def build_mutable_config_from_resolved_toml_sources(
    resolved: ResolvedTopmarkTomlSources,
) -> MutableConfig:
    """Merge resolved TOML sources into one mutable config draft.

    This helper consumes already-resolved TOML-side state and performs the
    config-layer construction and merge step without re-running TOML discovery.

    In addition to merging the layered config fragments, it replays whole-source
    TOML schema validation issues collected during TOML loading into the merged
    draft's TOML-source validation stage. This ensures that the effective
    strictness derived from `strict` sees schema issues outside
    the layered-config subset, such as invalid top-level keys under
    `[tool.topmark]`, unknown keys in `[writer]`, or TOML-layer missing-section
    INFO diagnostics.

    Source-local config-loading options such as `strict` are
    resolved on the TOML side. This helper only performs config-layer
    construction, merging, and diagnostic aggregation; it does not re-run TOML
    schema validation.

    Args:
        resolved: Resolved TOML-side state for the current run.

    Returns:
        Merged mutable config draft built from the defaults layer plus all
        resolved layered TOML sources, with source-level TOML schema issues
        replayed into its TOML-source validation stage for later staged
        config/preflight validation.
    """
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)
    draft: MutableConfig = merge_layers_globally(layers)

    for source in resolved.sources:
        add_toml_issues(
            draft.validation_logs.toml_source,
            source.validation_issues,
        )
        for diagnostic in source.load_diagnostics:
            draft.validation_logs.toml_source.add(diagnostic)

    return draft


def resolve_toml_sources_and_build_mutable_config(
    *,
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict: bool | None = None,
    no_config: bool = False,
) -> tuple[ResolvedTopmarkTomlSources, MutableConfig]:
    """Resolve TOML sources once and build the merged config draft from them.

    This helper is the preferred bridge between TOML-side source resolution and
    config-layer merge for callers that need both the resolved TOML-side state
    and the merged mutable config draft.

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to merge after discovered
            layers. Later files override earlier ones.
        strict: Optional explicit override for the TOML-side
            strictness preference that later governs staged
            config-loading/preflight validation.
        no_config: If `True`, skip all discovered config layers (user +
            project) and only use built-in defaults plus any explicit extra
            config files.

    Returns:
        A tuple containing the resolved TOML-side state and the merged mutable
        config draft built from it.
    """
    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=input_paths,
        extra_config_files=extra_config_files,
        strict=strict,
        no_config=no_config,
    )
    return resolved, build_mutable_config_from_resolved_toml_sources(resolved)


def _resolve_single_builtin_toml_table_and_build_mutable_config(
    *,
    table: TomlTable,
    source_path: Path | SyntheticConfigSource,
    load_diagnostics: MutableDiagnosticLog | None = None,
) -> tuple[ResolvedTopmarkTomlSources, MutableConfig]:
    """Resolve one bundled TOML table and build its config draft.

    Args:
        table: Parsed TopMark TOML table to load, validate, and resolve.
        source_path: Real path or synthetic source marker used in diagnostics
            and provenance to identify the bundled TOML source.
        load_diagnostics: Optional diagnostics collected while loading the
            bundled resource before TOML table parsing.

    Returns:
        Tuple containing the resolved TOML-side state and merged mutable config
        draft built from the bundled source.
    """
    diagnostics: MutableDiagnosticLog = load_diagnostics or MutableDiagnosticLog()
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        table,
        source_path=source_path if isinstance(source_path, Path) else None,
        from_pyproject=False,
    )

    source = ResolvedTopmarkTomlSource(
        path=source_path,
        parsed=parsed,
        kind="explicit",
        validation_issues=parsed.validation_issues if parsed is not None else (),
        load_diagnostics=diagnostics.freeze(),
    )
    resolved = ResolvedTopmarkTomlSources(
        sources=[source],
        writer_options=parsed.writer_options if parsed is not None else None,
        strict=parsed.config_loading_options.strict if parsed is not None else None,
    )
    return resolved, build_mutable_config_from_resolved_toml_sources(resolved)


def resolve_default_template_and_build_mutable_config() -> tuple[
    ResolvedTopmarkTomlSources,
    MutableConfig,
]:
    """Resolve the bundled init template and build its config draft.

    This helper is intended for machine-readable `topmark config init` output.
    Human output should continue to render the bundled template text directly
    so comments and formatting are preserved.

    Returns:
        Tuple containing the resolved TOML-side state and mutable config draft
        built from the bundled init template.
    """
    diagnostics: MutableDiagnosticLog = MutableDiagnosticLog()
    text, err = load_default_topmark_template_toml_text()
    if err is not None:
        diagnostics.add_error(str(err))

    doc: tomlkit.TOMLDocument = tomlkit.parse(text)
    table: TomlTable = toml_table_from_mapping(as_object_dict(doc.unwrap()))
    return _resolve_single_builtin_toml_table_and_build_mutable_config(
        table=table,
        source_path=BUNDLED_TEMPLATE_TOML_SOURCE,
        load_diagnostics=diagnostics,
    )


def resolve_default_table_and_build_mutable_config() -> tuple[
    ResolvedTopmarkTomlSources,
    MutableConfig,
]:
    """Resolve the built-in default TOML table and build its config draft.

    This helper is intended for machine-readable `topmark config defaults`
    output. It uses the code-defined canonical default TOML table rather than
    the annotated starter template used by `topmark config init`.

    Returns:
        Tuple containing the resolved TOML-side state and mutable config draft
        built from the canonical default TOML table.
    """
    return _resolve_single_builtin_toml_table_and_build_mutable_config(
        table=build_default_topmark_toml_table(),
        source_path=BUILTIN_DEFAULTS_TOML_SOURCE,
    )
