# topmark:header:start
#
#   project      : TopMark
#   file         : file.py
#   file_relpath : src/topmark/utils/file.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File utilities for TopMark."""

from __future__ import annotations

import os
from pathlib import Path

from topmark.config.logging import TopmarkLogger, get_logger

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
