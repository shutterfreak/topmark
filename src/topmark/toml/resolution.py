# topmark:header:start
#
#   project      : TopMark
#   file         : resolution.py
#   file_relpath : src/topmark/toml/resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark TOML source discovery helpers.

This module discovers TopMark-relevant TOML settings files in stable
same-directory and upward-traversal precedence order. It is responsible only
for finding candidate TOML sources; it does not deserialize layered config into
`MutableConfig`, construct `ConfigLayer` objects, or flatten resolved settings
into a compatibility draft.

Responsibilities:
    - discover user-scoped TopMark TOML sources
    - discover project/local TOML sources by walking upward from an anchor path
    - preserve same-directory precedence between `pyproject.toml` and
      `topmark.toml`
    - honor per-directory `root = true` stop markers while discovering sources

Typical discovery precedence (lowest -> highest, once later loaded/resolved):
    1. built-in defaults
    2. user-scoped TOML source
    3. project/local TOML sources discovered upward from an anchor path
    4. explicitly provided extra TOML sources

The actual layered config merge and effective per-path config construction live
in [`topmark.config.resolution`][topmark.config.resolution].
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.core.logging import get_logger
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_toml_table
from topmark.toml.pyproject import extract_pyproject_topmark_table

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable


logger: TopmarkLogger = get_logger(__name__)


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
                data: TomlTable | None = load_toml_table(p)
                # load_toml_dict() does a best-effort discovery; it returns {} on errors.
                if data:
                    if name == "pyproject.toml":
                        topmark_tbl: TomlTable | None = extract_pyproject_topmark_table(data)
                        if topmark_tbl is not None and bool(topmark_tbl.get(Toml.KEY_ROOT, False)):
                            root_stop_here = True
                    else:  # topmark.toml
                        if bool(data.get(Toml.KEY_ROOT, False)):
                            root_stop_here = True
                else:
                    # Best-effort discovery; ignore parse errors here.
                    logger.debug("Ignoring empty / undefined TOML dict from reading %s", p)
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
