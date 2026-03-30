# topmark:header:start
#
#   project      : TopMark
#   file         : file.py
#   file_relpath : src/topmark/utils/file.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File utilities for TopMark.

This module contains small, dependency-free helpers for file/path handling and
presentation logic shared across the CLI, API and core.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


def compute_relpath(file_path: Path, root_path: Path) -> Path:
    """Compute the relative path from root_path to file_path.

    Args:
        file_path: The file path to compute the relative path for.
        root_path: The root path to compute the relative path from.

    Returns:
        The relative path from root_path to file_path.
    """
    # Ensure the file_path is resolved to its absolute path
    resolved_path: Path = file_path.resolve()

    # Determine root directory for relative path computation
    resolved_root: Path = (root_path or Path.cwd()).resolve()

    try:
        # Direct subpath case
        return resolved_path.relative_to(resolved_root)
    except ValueError:
        # Not a direct subpath — safe fallback using os.path.relpath
        return Path(os.path.relpath(resolved_path, start=resolved_root))


def rebase_glob_patterns(
    patterns: Iterable[str],
    *,
    from_base: Path,
    to_base: Path,
) -> tuple[list[str], list[str]]:
    """Rebase glob-like patterns declared relative to one base directory to another.

    This is intended for *presentation* (e.g. `topmark config dump`) when configuration
    patterns were declared relative to a config file directory (`from_base`) but we want to
    display them as they would be interpreted from the current working directory
    (`to_base`).

    The transformation is best-effort:
      - Empty/whitespace-only patterns are skipped.
      - Negation patterns starting with '!' keep their negation.
      - Patterns starting with '/' are treated as "anchored to the base". During rebasing,
        the leading '/' is dropped and the pattern is re-anchored under the computed prefix.

    Args:
        patterns: Input patterns (may include negation '!' and anchored '/' prefixes).
        from_base: The directory the patterns were originally intended to be relative to.
        to_base: The directory the returned patterns should be relative to.

    Returns:
        A tuple of:
            - The rebased patterns (POSIX-style separators).
            - Warning strings describing any issues (empty if none).
    """
    warnings: list[str] = []

    try:
        prefix: str = os.path.relpath(str(from_base), start=str(to_base))
    except ValueError as exc:
        warnings.append(
            "Could not rebase patterns from "
            f"{from_base!r} to {to_base!r} (different filesystem roots?): {exc}. "
            "Leaving patterns unchanged."
        )
        return list(patterns), warnings

    # Let other exceptions bubble (they indicate a bug / unexpected invariant violation).

    prefix = prefix.replace(os.sep, "/")
    if prefix == ".":
        prefix = ""

    rebased: list[str] = []
    for raw in patterns:
        s: str = raw.strip()
        if not s:
            continue

        neg: str = ""
        if s.startswith("!"):
            neg = "!"
            s = s[1:]

        anchored: bool = s.startswith("/")
        if anchored:
            s = s[1:]

        if not prefix:
            # When bases coincide, emit a clean pattern string (drop any leading '/').
            rebased.append(f"{neg}{s}")
            continue

        rebased.append(f"{neg}{prefix}/{s}")

    return rebased, warnings


def safe_unlink(path: Path | None) -> None:
    """Attempt to delete a file, ignoring any errors.

    Args:
        path: Path to delete, or None (no-op).

    Notes:
        - Any errors during deletion are logged and ignored.
    """
    if path and path.exists():
        try:
            path.unlink()
        except OSError as e:
            logger.error("Failed to delete %s: %s", path, e)
