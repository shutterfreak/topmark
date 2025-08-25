# topmark:header:start
#
#   file         : file.py
#   file_relpath : src/topmark/utils/file.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header manager utilities for TopMark."""

import os
from pathlib import Path

from topmark.config.logging import get_logger

logger = get_logger(__name__)


def compute_relpath(file_path: Path, root_path: Path) -> Path:
    """Compute the relative path from root_path to file_path.

    Args:
        file_path (Path): The file path to compute the relative path for.
        root_path (Path): The root path to compute the relative path from.

    Returns:
        Path: The relative path from root_path to file_path.
    """
    # Ensure the file_path is resolved to its absolute path
    resolved_path = file_path.resolve()

    # Determine root directory for relative path computation
    resolved_root = (root_path or Path.cwd()).resolve()

    try:
        # Direct subpath case
        return resolved_path.relative_to(resolved_root)
    except ValueError:
        # Not a direct subpath — safe fallback using os.path.relpath
        return Path(os.path.relpath(resolved_path, start=resolved_root))
