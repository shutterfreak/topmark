# topmark:header:start
#
#   project      : TopMark
#   file         : resolution.py
#   file_relpath : src/topmark/toml/resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark TOML source discovery and per-run TOML resolution helpers.

This module discovers TopMark-relevant TOML settings files in stable
same-directory and upward-traversal precedence order, then optionally resolves
those sources into a per-run TOML result.

Responsibilities:
    - discover user-scoped TopMark TOML sources
    - discover project/local TOML sources by walking upward from an anchor path
    - preserve same-directory precedence between `pyproject.toml` and
      `topmark.toml`
    - honor per-directory `root = true` stop markers while discovering sources
    - load discovered TOML sources through split parse
    - resolve non-layered TOML settings such as writer preferences and config
      loading strictness using precedence rules

Typical discovery precedence (lowest -> highest, once later resolved):
    1. built-in defaults
    2. user-scoped TOML source
    3. project/local TOML sources discovered upward from an anchor path
    4. explicitly provided extra TOML sources

This module is intentionally separate from
[`topmark.config.resolution`][topmark.config.resolution]. That module owns
layered config provenance layers and `MutableConfig` merge behavior; this
module owns TOML-source discovery and TOML-side per-run resolution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal
from typing import TypeAlias

from topmark.core.logging import get_logger
from topmark.diagnostic.model import DiagnosticLog
from topmark.toml.loaders import load_topmark_toml_source

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.resolution.synthetic import SyntheticConfigSource
    from topmark.core.logging import TopmarkLogger
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.runtime.writer_options import WriterOptions
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.validation import TomlValidationIssue


logger: TopmarkLogger = get_logger(__name__)

TomlSourceKind: TypeAlias = Literal["user", "discovered", "explicit"]
"""Discovery kind for one resolved TopMark TOML source.

Allowed values:
    - `"user"`: discovered from the user-scoped config location
    - `"discovered"`: found by upward project/local TOML discovery
    - `"explicit"`: provided explicitly by the caller
"""


@dataclass(frozen=True, slots=True)
class ResolvedTopmarkTomlSource:
    """One TopMark TOML source participating in per-run resolution.

    A source may be syntactically invalid or unreadable. Such sources are still
    preserved as resolved source records so TOML-source diagnostics can be
    replayed into staged config validation. Only successfully parsed sources
    contribute layered config fragments and TOML-side settings such as writer
    options or `strict`.

    Attributes:
        path: Resolved filesystem path of the TOML source.
        parsed: Split-parsed TOML source contents, or `None` when loading or
            parsing failed.
        kind: Discovery class of the source. Allowed values are `"user"`,
            `"discovered"`, and `"explicit"`.
        validation_issues: TOML schema validation issues associated with this
            source. For failed loads this is empty because no TOML schema
            validation could run.
        load_diagnostics: Diagnostics produced while loading or parsing the TOML
            source. This is normally empty for successfully parsed sources and
            contains a synthetic error for unreadable or invalid TOML files.
    """

    path: Path | SyntheticConfigSource
    parsed: ParsedTopmarkToml | None
    kind: TomlSourceKind
    validation_issues: tuple[TomlValidationIssue, ...]
    load_diagnostics: FrozenDiagnosticLog


@dataclass(frozen=True, slots=True)
class ResolvedTopmarkTomlSources:
    """Resolved TOML-side state across discovered TopMark TOML sources.

    Attributes:
        sources: Loaded and split-parsed TopMark TOML source records in stable
            precedence order (lowest -> highest), excluding built-in defaults.
        writer_options: Resolved non-layered writer preferences using
            highest-precedence non-`None` wins.
        strict: Resolved config-loading strictness using
            highest-precedence non-`None` wins, optionally overridden by the
            explicit function argument to `resolve_topmark_toml_sources()`.
    """

    sources: list[ResolvedTopmarkTomlSource]
    writer_options: WriterOptions | None
    strict: bool | None


# ---- Shared helpers ----


def _append_loaded_source(
    dst: list[ResolvedTopmarkTomlSource],
    path: Path,
    *,
    kind: TomlSourceKind,
) -> None:
    """Load one TOML source and append it with preserved source diagnostics."""
    resolved_path: Path = path.resolve()
    parsed: ParsedTopmarkToml | None = load_topmark_toml_source(resolved_path)
    if parsed is None:
        logger.debug(
            "Preserving unreadable or invalid TOML source during resolution: %s", resolved_path
        )
        diagnostics = DiagnosticLog()
        diagnostics.add_error(f"Unable to load or parse TOML source: {resolved_path}")
        dst.append(
            ResolvedTopmarkTomlSource(
                path=resolved_path,
                parsed=None,
                kind=kind,
                validation_issues=(),
                load_diagnostics=diagnostics.freeze(),
            )
        )
        return

    dst.append(
        ResolvedTopmarkTomlSource(
            path=resolved_path,
            parsed=parsed,
            kind=kind,
            validation_issues=parsed.validation_issues,
            load_diagnostics=DiagnosticLog().freeze(),
        )
    )


# ---- User-scoped discovery ----


def _discover_user_config_file() -> Path | None:
    """Return the first existing user-scoped TopMark config file.

    Lookup order:
        1. `$XDG_CONFIG_HOME/topmark/topmark.toml` (or `~/.config/...` fallback)
        2. legacy `~/.topmark.toml`

    Returns:
        The first existing user config path, or `None` if no user-scoped config
        file is present.
    """
    xdg: str | None = os.environ.get("XDG_CONFIG_HOME")
    base: Path = Path(xdg) if xdg else Path.home() / ".config"
    xdg_path: Path = base / "topmark" / "topmark.toml"
    legacy: Path = Path.home() / ".topmark.toml"
    for p in (xdg_path, legacy):
        if p.exists() and p.is_file():
            return p
    return None


# ---- Project/local upward discovery ----


def _discover_local_config_files(start: Path) -> list[Path]:
    """Return config files discovered by walking upward from ``start``.

    Layered discovery semantics:
        * We traverse from the anchor directory up to the filesystem root and
        collect config files in **root-most → nearest** order.
        * In a given directory, we consider **both** `pyproject.toml` (with
        `[tool.topmark]`) and `topmark.toml`. When **both** are present, we
        append **`pyproject.toml` first and `topmark.toml` second** so that a
        later merge (nearest-last-wins) gives same-directory precedence to
        `topmark.toml`.
        * If a discovered TOML source sets ``root = true`` in the `[config]`
        table (or in `[tool.topmark.config]` for `pyproject.toml`), we stop
        traversing further up after collecting the current directory's files.

    Args:
        start: The Path instance where discovery starts.

    Returns:
        Discovered TopMark TOML source paths ordered for stable later
        resolution: root-most first, nearest last; within a directory,
        `pyproject.toml` is returned before `topmark.toml` so the latter has
        higher same-directory precedence.
    """
    # Collect per-directory entries preserving same-dir precedence (pyproject → topmark)
    per_dir: list[list[Path]] = []
    cur: Path = start.resolve()  # Resolve symlinks and get absolute path
    seen: set[Path] = set()

    # Ensure we start from a directory anchor
    if cur.is_file():
        cur = cur.parent

    # Walk up to filesystem root, recording entries per directory
    while True:
        root_stop_here = False
        dir_entries: list[Path] = []

        # Same-directory precedence: add `pyproject.toml` first, then
        # `topmark.toml`, so later merge order gives `topmark.toml` the final say
        # within the same directory.
        for name in ("pyproject.toml", "topmark.toml"):
            p: Path = cur / name
            if p.exists() and p.is_file() and p not in seen:
                dir_entries.append(p)
                seen.add(p)
                logger.debug("Discovered config file: %s", p)
                # Check whether this directory declares itself as the config
                # discovery root. If so, we still keep the current directory's
                # entries, then stop traversing further upward.
                parsed: ParsedTopmarkToml | None = load_topmark_toml_source(p)
                if parsed is not None:
                    if parsed.source_options.root is True:
                        root_stop_here = True
                else:
                    # Best-effort discovery; ignore unreadable or malformed TOML
                    # sources here and continue traversing upward.
                    logger.debug(
                        "Ignoring unreadable or invalid TOML source during discovery: %s",
                        p,
                    )
        if dir_entries:
            # Keep entries grouped per directory: [pyproject, topmark]
            per_dir.append(dir_entries)

        parent: Path = cur.parent
        if parent == cur:
            break
        if root_stop_here:
            logger.debug(
                "Stopping upward TOML source discovery at %s due to root=true",
                cur,
            )
            break
        cur = parent

    # Flatten per-directory lists in root -> current order while preserving the
    # within-directory precedence (`pyproject.toml` then `topmark.toml`).
    ordered: list[Path] = []
    for dir_list in reversed(per_dir):  # root-most first
        # Within a directory: pyproject then topmark (tool file overrides)
        ordered.extend(dir_list)  # pyproject then topmark within the directory

    return ordered


# ---- Resolve TOML-side settings ----


def _resolve_writer_options(
    sources: list[ResolvedTopmarkTomlSource],
) -> WriterOptions | None:
    """Resolve writer options using highest-precedence non-`None` wins."""
    resolved: WriterOptions | None = None
    for source in sources:
        if source.parsed is None:
            continue
        writer_options: WriterOptions | None = source.parsed.writer_options
        if writer_options is not None and writer_options.file_write_strategy is not None:
            resolved = writer_options
    return resolved


def _resolve_strict(
    sources: list[ResolvedTopmarkTomlSource],
    *,
    explicit_override: bool | None,
) -> bool | None:
    """Resolve config-loading strictness using precedence order."""
    resolved: bool | None = None
    for source in sources:
        if source.parsed is None:
            continue
        value: bool | None = source.parsed.config_loading_options.strict
        if value is not None:
            resolved = value

    if explicit_override is not None:
        resolved = explicit_override

    return resolved


# ---- TOML-side resolution across discovered sources ----


def resolve_topmark_toml_sources(
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict: bool | None = None,
    no_config: bool = False,
) -> ResolvedTopmarkTomlSources:
    """Discover, load, and resolve TopMark TOML sources for one run.

    This helper resolves TOML-side settings only. It does not construct
    `ConfigLayer` objects and does not merge layered config into a
    `MutableConfig`.

    Precedence order (lowest -> highest):
        1. user-scoped TOML source
        2. discovered project/local TOML sources (root-most -> nearest)
        3. explicit extra TOML sources (in the order provided)
        4. explicit `strict` function argument, if provided

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit TOML source files to append after
            discovered sources. Later files have higher precedence than earlier
            ones.
        strict: Optional explicit override for resolved config
            loading strictness.
        no_config: If `True`, skip all discovered TOML sources (user + project)
            and only consider explicit extra TOML sources.

    Returns:
        The resolved TOML-side state across all successfully loaded sources.
    """
    source_entries: list[ResolvedTopmarkTomlSource] = []

    input_path_list: list[Path] = list(input_paths) if input_paths is not None else []
    anchor: Path = input_path_list[0] if input_path_list else Path.cwd()
    if anchor.is_file():
        anchor = anchor.parent
    anchor = anchor.resolve()

    if not no_config:
        user_cfg_path: Path | None = _discover_user_config_file()
        if user_cfg_path is not None:
            _append_loaded_source(source_entries, user_cfg_path, kind="user")

        for cfg_path in _discover_local_config_files(anchor):
            _append_loaded_source(source_entries, cfg_path, kind="discovered")
    else:
        logger.debug("Skipping discovered TOML sources because no_config=True")

    for extra in extra_config_files or ():
        _append_loaded_source(source_entries, Path(extra), kind="explicit")

    resolved_writer: WriterOptions | None = _resolve_writer_options(source_entries)
    resolved_strict: bool | None = _resolve_strict(
        source_entries,
        explicit_override=strict,
    )

    return ResolvedTopmarkTomlSources(
        sources=source_entries,
        writer_options=resolved_writer,
        strict=resolved_strict,
    )
