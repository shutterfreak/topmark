# topmark:header:start
#
#   project      : TopMark
#   file         : path.py
#   file_relpath : src/topmark/utils/path.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Filesystem path utilities.

This module contains helpers for working with filesystem paths while preserving
stable behavior across case-sensitive and case-insensitive filesystems.
"""

from __future__ import annotations

from pathlib import Path


def canonicalize_existing_path(path: Path) -> Path:
    """Return a path using canonical filesystem casing.

    The path is expected to exist and refer to a filesystem object.

    The returned path refers to the same filesystem object as ``path`` but, on
    case-insensitive filesystems, uses the directory-entry spelling stored on
    disk rather than the spelling used by the caller.

    Args:
        path: Existing filesystem path.

    Returns:
        A path using canonical filesystem casing when it can be determined.
    """
    # The path must exist; `resolve(strict=True)` establishes filesystem identity
    # before reconstructing canonical directory-entry casing.
    resolved: Path = path.resolve(strict=True)

    parts: tuple[str, ...] = resolved.parts
    if not parts:
        return resolved

    current: Path = Path(parts[0])

    for part in parts[1:]:
        try:
            entry_name: str = next(
                (
                    candidate.name
                    for candidate in current.iterdir()
                    if candidate.name.casefold() == part.casefold()
                ),
                part,
            )
        except OSError:
            return resolved

        current = current / entry_name

    return current


def format_machine_path(path: Path) -> str:
    """Serialize a path for processing machine-readable output.

    Machine-readable processing payloads use POSIX separators on all platforms
    so JSON and NDJSON output remain stable across operating systems.
    """
    return path.as_posix()
