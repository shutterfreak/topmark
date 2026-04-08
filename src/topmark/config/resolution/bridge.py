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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.resolution.layers import ConfigLayer
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import merge_layers_globally
from topmark.toml.resolution import resolve_topmark_toml_sources
from topmark.toml.validation import add_toml_issues

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


# ---- Public TOML -> config bridge helpers ----


def build_config_draft_from_resolved_toml_sources(
    resolved: ResolvedTopmarkTomlSources,
) -> MutableConfig:
    """Merge resolved TOML sources into one mutable config draft.

    This helper consumes already-resolved TOML-side state and performs the
    config-layer construction and merge step without re-running TOML discovery.

    In addition to merging the layered config fragments, it replays whole-source
    TOML schema validation issues collected during TOML loading into the merged
    draft diagnostics. This ensures that strict config checking sees schema
    violations outside the layered-config subset, such as invalid top-level
    keys under `[tool.topmark]` or unknown keys in `[writer]`.

    Source-local config-loading options such as `strict_config_checking` are
    resolved on the TOML side. This helper only performs config-layer
    construction, merging, and diagnostic bridging.

    Args:
        resolved: Resolved TOML-side state for the current run.

    Returns:
        Merged mutable config draft built from the defaults layer plus all
        resolved layered TOML sources, with source-level TOML schema issues
        attached to its diagnostics.
    """
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)
    draft: MutableConfig = merge_layers_globally(layers)

    for source in resolved.sources:
        add_toml_issues(draft.diagnostics, source.parsed.validation_issues)

    return draft


def resolve_toml_sources_and_build_config_draft(
    *,
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
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
        strict_config_checking: Optional explicit override for TOML-side
            config-loading strictness during source resolution.
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
        strict_config_checking=strict_config_checking,
        no_config=no_config,
    )
    return resolved, build_config_draft_from_resolved_toml_sources(resolved)
