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

from topmark.config.resolution.synthetic import SyntheticConfigSource


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


def canonical_processing_path(path: Path) -> Path:
    """Return the canonical processing path for an existing filesystem target.

    Existing filesystem inputs are identified by their resolved processing
    target. Symlink spelling is therefore not preserved for processing identity
    or for generated filesystem-related header metadata.

    Args:
        path: Existing filesystem path selected for processing.

    Returns:
        The canonical processing path for the selected filesystem target.
    """
    return canonicalize_existing_path(path)


# ---- POSIX path representation ----


def format_posix_path(path: Path) -> str:
    """Return a POSIX-style string representation of a filesystem path.

    Args:
        path: Path to serialize.

    Returns:
        POSIX-style path string.
    """
    return path.as_posix()


def format_machine_path(path: Path) -> str:
    """Serialize a filesystem path for machine-readable output.

    All machine-readable TopMark payloads use POSIX separators on all platforms
    so JSON and NDJSON output remain stable across operating systems.

    Args:
        path: Path to serialize.

    Returns:
        POSIX-style path string for machine-readable output.
    """
    return format_posix_path(path)


def format_header_metadata_path(path: Path) -> str:
    """Serialize a filesystem path for generated TopMark header metadata.

    Header metadata is written into source files and should remain stable across
    operating systems. Use POSIX separators for relative and absolute path
    fields generated in TopMark headers.

    Args:
        path: Path to serialize.

    Returns:
        POSIX-style path string for generated header metadata.
    """
    return format_posix_path(path)


def format_config_source_path(source: Path | SyntheticConfigSource) -> str:
    """Format real and synthetic config source identifiers for TOML export.

    Synthetic config sources use bracketed identifiers such as
    `<built-in topmark defaults>`. These should remain stable identifiers in
    exported output rather than being normalized relative to the current working
    directory.

    Args:
        source: Real filesystem path or synthetic config source identifier.

    Returns:
        POSIX-style path string for real filesystem paths, or the stable label
        for synthetic config sources.
    """
    return source.label if isinstance(source, SyntheticConfigSource) else format_posix_path(source)
