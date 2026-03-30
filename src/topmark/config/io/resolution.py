# topmark:header:start
#
#   project      : TopMark
#   file         : resolution.py
#   file_relpath : src/topmark/config/io/resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Layered configuration discovery and compatibility flattening for TopMark.

This module discovers configuration provenance layers in precedence order and
provides a compatibility path that merges those layers into a single effective
`MutableConfig` draft.

Responsibilities:
    - discover user-scoped and project-scoped config files
    - represent discovered sources as `ConfigLayer`
    - preserve TopMark's layered precedence rules
    - load TOML-backed config fragments into `MutableConfig`
    - flatten discovered layers into a compatibility `MutableConfig` draft

Typical precedence (lowest -> highest):
    1. built-in defaults
    2. user config
    3. project config files discovered upward from an anchor path
    4. explicitly provided extra config files

This module is intentionally separate from `topmark.config.model`:

- `topmark.config.model` defines the configuration data structures and merge
  behavior
- this module performs discovery, ordering, provenance tracking, and
  compatibility flattening across config sources

The result of compatibility flattening is a `MutableConfig` draft that can still
be adjusted by callers before being frozen into an immutable `Config`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_toml_file
from topmark.config.io.guards import get_pyproject_topmark_table
from topmark.config.io.loaders import load_toml_dict
from topmark.config.io.types import ConfigLayer
from topmark.config.io.types import ConfigLayerKind
from topmark.config.keys import Toml
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.io.types import TomlTable
    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


def _make_config_layer(
    *,
    origin: Path | str,
    kind: ConfigLayerKind,
    precedence: int,
    config: MutableConfig,
    scope_root: Path | None = None,
) -> ConfigLayer:
    """Return a normalized config provenance layer."""
    normalized_origin: Path | str = origin.resolve() if isinstance(origin, Path) else origin
    normalized_scope_root: Path | None = scope_root

    if normalized_scope_root is None and isinstance(normalized_origin, Path):
        normalized_scope_root = normalized_origin.parent.resolve()
    elif normalized_scope_root is not None:
        normalized_scope_root = normalized_scope_root.resolve()

    return ConfigLayer(
        origin=normalized_origin,
        scope_root=normalized_scope_root,
        precedence=precedence,
        kind=kind,
        config=config,
    )


def _load_layer_from_file(
    path: Path,
    *,
    kind: ConfigLayerKind,
    precedence: int,
) -> ConfigLayer | None:
    """Load a config provenance layer from a TOML-backed config file."""
    resolved_path: Path = path.resolve()
    config: MutableConfig | None = mutable_config_from_toml_file(resolved_path)
    if config is None:
        logger.debug("Skipping unreadable or invalid config layer file: %s", resolved_path)
        return None

    return _make_config_layer(
        origin=resolved_path,
        kind=kind,
        precedence=precedence,
        scope_root=resolved_path.parent,
        config=config,
    )


def _default_config_layer() -> ConfigLayer:
    """Return the built-in defaults as the first config provenance layer."""
    return _make_config_layer(
        origin="<defaults>",
        kind=ConfigLayerKind.DEFAULT,
        precedence=0,
        scope_root=None,
        config=mutable_config_from_defaults(),
    )


def _is_within_scope(path: Path, scope_root: Path) -> bool:
    """Return whether ``path`` is within the given layer scope root."""
    resolved_path: Path = path.resolve()
    resolved_scope_root: Path = scope_root.resolve()
    result: bool
    try:
        resolved_path.relative_to(resolved_scope_root)
        result = True
    except ValueError:
        result = False

    return result


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
        * If a discovered config sets ``root = true`` (top-level key in
        `topmark.toml`, or within `[tool.topmark]` for `pyproject.toml`), we
        stop traversing further up after collecting the current directory's
        files.

    Args:
        start: The Path instance where discovery starts.

    Returns:
        Discovered config file paths ordered for stable merging: root-most first,
        nearest last; within a directory, `pyproject.toml` is returned before
        `topmark.toml` so the latter has higher same-directory precedence.
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
                data: TomlTable = load_toml_dict(p)
                # load_toml_dict() does a best-effort discovery; it returns {} on errors.
                if data:
                    if name == "pyproject.toml":
                        topmark_tbl: TomlTable | None = get_pyproject_topmark_table(data)
                        if topmark_tbl is not None and bool(topmark_tbl.get(Toml.KEY_ROOT, False)):
                            root_stop_here = True
                    else:  # topmark.toml
                        if bool(data.get(Toml.KEY_ROOT, False)):
                            root_stop_here = True
                else:
                    # Best-effort discovery; ignore parse errors here.
                    logger.debug("Ignoring empty TOML dict from reading %s", p)
        if dir_entries:
            # Keep entries grouped per directory: [pyproject, topmark]
            per_dir.append(dir_entries)

        parent: Path = cur.parent
        if parent == cur:
            break
        if root_stop_here:
            logger.debug(
                "Stopping upward config discovery at %s due to %s=true",
                cur,
                Toml.KEY_ROOT,
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


def discover_config_layers(
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
    no_config: bool = False,
) -> list[ConfigLayer]:
    """Discover config provenance layers in stable precedence order.

    Layer order (lowest -> highest precedence):
        1. built-in defaults
        2. discovered user config
        3. discovered project config files (root-most -> nearest)
        4. explicit extra config files (in the order provided)

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to append after discovered
            layers. Later files have higher precedence than earlier ones.
        strict_config_checking: Reserved compatibility argument. Discovery does
            not currently materialize this runtime override as a provenance
            layer.
        no_config: If True, skip all discovered config layers (user + project)
            and only return built-in defaults plus any explicit extra config
            files.

    Returns:
        Config provenance layers ordered from lowest to highest precedence.
    """
    # Avoid premature modeling of runtime-only overrides as layers:
    del strict_config_checking

    layers: list[ConfigLayer] = []
    precedence: int = 0

    default_layer: ConfigLayer = _default_config_layer()
    layers.append(default_layer)
    logger.debug(
        "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
        default_layer.kind,
        default_layer.precedence,
        default_layer.origin,
        default_layer.scope_root,
    )

    input_path_list: list[Path] = list(input_paths) if input_paths is not None else []
    anchor: Path = input_path_list[0] if input_path_list else Path.cwd()
    if anchor.is_file():
        anchor = anchor.parent
    anchor = anchor.resolve()
    logger.debug("Config layer discovery anchor: %s", anchor)

    precedence = 1

    if not no_config:
        user_cfg_path: Path | None = discover_user_config_file()
        if user_cfg_path is not None:
            user_layer: ConfigLayer | None = _load_layer_from_file(
                user_cfg_path,
                kind=ConfigLayerKind.USER,
                precedence=precedence,
            )
            if user_layer is not None:
                layers.append(user_layer)
                logger.debug(
                    "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
                    user_layer.kind,
                    user_layer.precedence,
                    user_layer.origin,
                    user_layer.scope_root,
                )
                precedence += 1

        discovered: list[Path] = discover_local_config_files(anchor)
        for cfg_path in discovered:
            discovered_layer: ConfigLayer | None = _load_layer_from_file(
                cfg_path,
                kind=ConfigLayerKind.DISCOVERED,
                precedence=precedence,
            )
            if discovered_layer is not None:
                layers.append(discovered_layer)
                logger.debug(
                    "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
                    discovered_layer.kind,
                    discovered_layer.precedence,
                    discovered_layer.origin,
                    discovered_layer.scope_root,
                )
                precedence += 1
    else:
        logger.debug("Skipping discovered config layers because no_config=True")

    for extra in extra_config_files or ():
        explicit_layer: ConfigLayer | None = _load_layer_from_file(
            Path(extra),
            kind=ConfigLayerKind.EXPLICIT,
            precedence=precedence,
        )
        if explicit_layer is not None:
            layers.append(explicit_layer)
            logger.debug(
                "Added config layer: kind=%s precedence=%d origin=%s scope_root=%s",
                explicit_layer.kind,
                explicit_layer.precedence,
                explicit_layer.origin,
                explicit_layer.scope_root,
            )
            precedence += 1

    return layers


def merge_layers_globally(layers: Iterable[ConfigLayer]) -> MutableConfig:
    """Merge discovered config provenance layers into one compatibility draft."""
    layer_list: list[ConfigLayer] = list(layers)
    logger.debug("Merging %d config layer(s) into compatibility draft", len(layer_list))

    if not layer_list:
        return mutable_config_from_defaults()

    merged: MutableConfig = layer_list[0].config
    for layer in layer_list[1:]:
        merged = merged.merge_with(layer.config)

    return merged


def select_applicable_layers(
    layers: Iterable[ConfigLayer],
    path: Path,
) -> list[ConfigLayer]:
    """Return config layers whose scope applies to the given file path.

    Global layers (``scope_root is None``) always apply. File-backed layers apply
    only when the target path is within their declared scope root.

    Args:
        layers: Candidate config provenance layers.
        path: Target file path for which applicability should be evaluated.

    Returns:
        Applicable layers in their original precedence order.
    """
    resolved_path: Path = path.resolve()
    layer_list: list[ConfigLayer] = list(layers)
    applicable: list[ConfigLayer] = []

    for layer in layer_list:
        scope_root: Path | None = layer.scope_root
        if scope_root is None or _is_within_scope(resolved_path, scope_root):
            applicable.append(layer)

    logger.debug(
        "Selected %d/%d applicable config layer(s) for %s",
        len(applicable),
        len(layer_list),
        resolved_path,
    )
    return applicable


def build_effective_config_for_path(
    layers: Iterable[ConfigLayer],
    path: Path,
) -> MutableConfig:
    """Build the effective mutable config for a specific file path.

    This helper selects the config provenance layers whose scope applies to the
    target path, then merges them in stable precedence order using the existing
    `MutableConfig.merge_with` compatibility policy.

    Args:
        layers: Candidate config provenance layers.
        path: Target file path for which to build the effective config.

    Returns:
        The merged mutable config draft applicable to ``path``.
    """
    applicable: list[ConfigLayer] = select_applicable_layers(layers, path)
    draft: MutableConfig = merge_layers_globally(applicable)
    logger.debug(
        "Built effective config for %s from %d applicable layer(s)",
        path.resolve(),
        len(applicable),
    )
    return draft


def load_resolved_config(
    input_paths: Iterable[Path] | None = None,
    extra_config_files: Iterable[Path] | None = None,
    strict_config_checking: bool | None = None,
    no_config: bool = False,
) -> MutableConfig:
    """Discover and merge configuration layers into a mutable draft.

    Merge order (lowest -> highest precedence):
        1. built-in defaults
        2. discovered user config
        3. discovered project config files (root-most -> nearest)
        4. explicit extra config files (in the order provided)

    This helper is responsible only for layered config discovery and merge. It
    does **not** apply CLI/API override intent such as write mode, stdin mode,
    include/exclude filters, or header-formatting overrides; those belong in the
    dedicated override layer.

    Args:
        input_paths: Optional discovery anchors. The first path is used to pick
            the project-discovery starting directory. If it points to a file,
            its parent directory is used. If omitted, discovery falls back to
            the current working directory.
        extra_config_files: Explicit config files to merge after discovered
            layers. Later files override earlier ones.
        strict_config_checking: Optional runtime override for strict config
            checking on the resulting draft.
        no_config: If True, skip all discovered config layers (user + project)
            and only use built-in defaults plus any explicit extra config files.

    Returns:
        A mutable configuration draft ready for later override application and
        eventual freezing.
    """
    layers: list[ConfigLayer] = discover_config_layers(
        input_paths=input_paths,
        extra_config_files=extra_config_files,
        strict_config_checking=None,
        no_config=no_config,
    )
    draft: MutableConfig = merge_layers_globally(layers)

    if strict_config_checking is not None:
        draft.strict_config_checking = strict_config_checking

    return draft
