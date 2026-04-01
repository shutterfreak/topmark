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
from topmark.runtime.writer_options import WriterOptions
from topmark.toml.loaders import load_topmark_toml_source

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.core.logging import TopmarkLogger
    from topmark.runtime.writer_options import WriterOptions
    from topmark.toml.parse import ParsedTopmarkToml


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
    """One successfully loaded TopMark TOML source.

    Attributes:
        path: Resolved filesystem path of the TOML source.
        parsed: Split-parsed TOML source contents.
        kind: Discovery class of the source. Allowed values are `"user"`,
            `"discovered"`, and `"explicit"`.
    """

    path: Path
    parsed: ParsedTopmarkToml
    kind: TomlSourceKind


@dataclass(frozen=True, slots=True)
class ResolvedTopmarkTomlSources:
    """Resolved TOML-side state across discovered TopMark TOML sources.

    Attributes:
        sources: Loaded and split-parsed TopMark TOML source records in stable
            precedence order (lowest -> highest), excluding built-in defaults.
        writer_options: Resolved non-layered writer preferences using
            highest-precedence non-`None` wins.
        strict_config_checking: Resolved config-loading strictness using
            highest-precedence non-`None` wins, optionally overridden by the
            explicit function argument to `resolve_topmark_toml_sources()`.
    """

    sources: list[ResolvedTopmarkTomlSource]
    writer_options: WriterOptions | None
    strict_config_checking: bool | None


# ---- User-scoped discovery ----


def discover_user_config_file() -> Path | None:
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


def discover_local_config_files(start: Path) -> list[Path]:
    """Return config files discovered by walking upward from ``start``.

    Layered discovery semantics:
        * We traverse from the anchor directory up to the filesystem root and
        collect config files in **root-most → nearest** order.
        * In a given directory, we consider **both** `pyproject.toml` (with
        `[tool.topmark]`) and `topmark.toml`. When **both** are present, we
        append **`pyproject.toml` first and `topmark.toml` second** so that a
        later merge (nearest-last-wins) gives same-directory precedence to
        `topmark.toml`.
        * If a discovered TOML source sets ``root = true`` (top-level key in
        `topmark.toml`, or within `[tool.topmark]` for `pyproject.toml`), we
        stop traversing further up after collecting the current directory's
        files.

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
                    if parsed.discovery_options.root is True:
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


# ---- TOML-side resolution across discovered sources ----


def resolve_topmark_toml_sources(
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
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
        4. explicit `strict_config_checking` function argument, if provided

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit TOML source files to append after
            discovered sources. Later files have higher precedence than earlier
            ones.
        strict_config_checking: Optional explicit override for resolved config
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
        user_cfg_path: Path | None = discover_user_config_file()
        if user_cfg_path is not None:
            _append_loaded_source(source_entries, user_cfg_path, kind="user")

        for cfg_path in discover_local_config_files(anchor):
            _append_loaded_source(source_entries, cfg_path, kind="discovered")
    else:
        logger.debug("Skipping discovered TOML sources because no_config=True")

    for extra in extra_config_files or ():
        _append_loaded_source(source_entries, Path(extra), kind="explicit")

    resolved_writer: WriterOptions | None = _resolve_writer_options(source_entries)
    resolved_strict: bool | None = _resolve_strict_config_checking(
        source_entries,
        explicit_override=strict_config_checking,
    )

    return ResolvedTopmarkTomlSources(
        sources=source_entries,
        writer_options=resolved_writer,
        strict_config_checking=resolved_strict,
    )


def _append_loaded_source(
    dst: list[ResolvedTopmarkTomlSource],
    path: Path,
    *,
    kind: TomlSourceKind,
) -> None:
    """Load one TOML source and append it when split parsing succeeds."""
    resolved_path: Path = path.resolve()
    parsed: ParsedTopmarkToml | None = load_topmark_toml_source(resolved_path)
    if parsed is None:
        logger.debug(
            "Skipping unreadable or invalid TOML source during resolution: %s", resolved_path
        )
        return

    dst.append(
        ResolvedTopmarkTomlSource(
            path=resolved_path,
            parsed=parsed,
            kind=kind,
        )
    )


def _resolve_writer_options(
    sources: list[ResolvedTopmarkTomlSource],
) -> WriterOptions | None:
    """Resolve writer options using highest-precedence non-`None` wins."""
    resolved: WriterOptions | None = None
    for source in sources:
        writer_options: WriterOptions | None = source.parsed.writer_options
        if writer_options is not None and writer_options.file_write_strategy is not None:
            resolved = writer_options
    return resolved


def _resolve_strict_config_checking(
    sources: list[ResolvedTopmarkTomlSource],
    *,
    explicit_override: bool | None,
) -> bool | None:
    """Resolve config-loading strictness using precedence order."""
    resolved: bool | None = None
    for source in sources:
        value: bool | None = source.parsed.discovery_options.strict_config_checking
        if value is not None:
            resolved = value

    if explicit_override is not None:
        resolved = explicit_override

    return resolved
