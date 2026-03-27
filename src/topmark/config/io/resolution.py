# topmark:header:start
#
#   project      : TopMark
#   file         : resolution.py
#   file_relpath : src/topmark/config/io/resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Layered configuration discovery and resolution for TopMark.

This module resolves the effective mutable configuration draft by combining
multiple configuration sources in precedence order.

Responsibilities:
    - discover user-scoped and project-scoped config files
    - apply TopMark's layered precedence rules
    - load TOML-backed config fragments into `MutableConfig`
    - merge those fragments into a single resolved draft

Typical precedence (lowest -> highest):
    1. built-in defaults
    2. user config
    3. project config files discovered upward from an anchor path
    4. explicitly provided extra config files

This module is intentionally separate from `topmark.config.model`:

- `topmark.config.model` defines the configuration data structures and merge
  behavior
- this module performs discovery, ordering, and orchestration across sources

The result of resolution is a `MutableConfig` draft that can still be adjusted
by callers before being frozen into an immutable `Config`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_toml_file
from topmark.config.io.guards import get_pyproject_topmark_table
from topmark.config.io.loaders import load_toml_dict
from topmark.config.keys import Toml
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.io.types import TomlTable
    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


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
    # 1) Start from defaults
    draft: MutableConfig = mutable_config_from_defaults()

    # Determine discovery anchor
    anchor: Path = list(input_paths)[0] if input_paths else Path.cwd()
    if anchor.is_file():
        anchor = anchor.parent

    # Only set strict config checking if not None
    if strict_config_checking is not None:
        draft.strict_config_checking = strict_config_checking

    # 2) Config file discovery (unless `no_config` disables discovered layers)
    if not no_config:
        # 2a) Merge user config (if present)
        user_cfg_path: Path | None = discover_user_config_file()
        if user_cfg_path is not None:
            user_cfg: MutableConfig | None = mutable_config_from_toml_file(user_cfg_path)
            if user_cfg is not None:
                draft = draft.merge_with(user_cfg)

        # 2b) Discover project configs upward from the anchor directory and
        # merge them in root-most -> nearest order.
        discovered: list[Path] = discover_local_config_files(anchor)
        # `discover_local_config_files()` already returns the correct stable
        # merge order: root-most -> nearest, and within a directory
        # `pyproject.toml` before `topmark.toml`.
        for cfg_path in discovered:
            mc: MutableConfig | None = mutable_config_from_toml_file(cfg_path)
            if mc is not None:
                draft = draft.merge_with(mc)

    # 3) Merge extra config files (e.g., --config), in the given order
    for extra in extra_config_files or ():  # explicit files override discovered ones
        mc = mutable_config_from_toml_file(Path(extra))
        if mc is not None:
            draft = draft.merge_with(mc)

    return draft
