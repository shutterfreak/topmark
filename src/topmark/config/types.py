# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/config/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Lightweight config types and aliases.

This module hosts stable, import-friendly definitions that other config modules
can depend on without risk of circular imports.

Exports:
    - `ArgsLike`: structural mapping type for CLI/API argument dicts.
    - `PatternSource`: immutable reference to a file containing patterns
      (e.g., include/exclude lists) together with the base directory used to
      interpret relative entries inside that file.

Design notes:
    - Keep side effects out of this module; it should stay dependency-free
      (stdlib only) to remain safe for low-level imports.
    - Prefer structural typing (``Mapping[str, Any]``) for CLI/API inputs so the
      config layer remains decoupled from any specific CLI framework.
"""

from __future__ import annotations

# For runtime type checks, prefer collections.abc
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.logging import TopmarkLogger

# ArgsLike: generic mapping accepted by config loaders (works for CLI namespaces and API dicts).
ArgsLike = Mapping[str, Any]
# We use ArgsLike (Mapping[str, Any]) instead of a CLI-specific namespace to
# keep the config layer decoupled from the CLI. The implementation uses .get()
# and key lookups, so Mapping is the right structural type. This allows the
# CLI to pass its namespace and the API/tests to pass plain dicts.

logger: TopmarkLogger = get_logger(__name__)


# ------------------ Pattern source reference ------------------
@dataclass(frozen=True)
class PatternSource:
    """Reference to a pattern or file list declared in a config source.

    This value object captures both the absolute path to the referenced file
    and the *base directory* used to interpret the file's contents when it
    contains relative patterns (e.g., a gitignore-style file).

    Attributes:
        path (Path): Absolute path to the referenced file (e.g., ".gitignore").
        base (Path): Absolute directory used as the matching base for the file's
            patterns. Typically equals ``path.parent``.
    """

    path: Path
    base: Path


class OutputTarget(str, Enum):
    """Available targets for writing processed file content."""

    FILE = "Write to file"
    STDOUT = "Write to STDOUT"

    @classmethod
    def from_name(cls, key_name: str | None) -> OutputTarget | None:
        """Finds the OutputTarget member by its case-insensitive name (e.g., 'file', 'stdout').

        Args:
            key_name (str | None): The string name of the member (e.g., "file") or None.

        Returns:
            OutputTarget | None: The matching OutputTarget member or None
                if the key is None or unmatched.
        """
        if key_name is None:
            return None

        # 1. Convert input to uppercase to match Enum member names (FILE, STDOUT)
        target_name: str = key_name.upper()

        # 2. Use the Enum's __members__ dictionary for a safe, direct lookup
        return cls.__members__.get(target_name)


class FileWriteStrategy(str, Enum):
    """Available strategies for writing file content."""

    ATOMIC = "Safe atomic writer (default)"
    IN_PLACE = "Fast in-place writer"

    @classmethod
    def from_name(cls, key_name: str | None) -> FileWriteStrategy | None:
        """Finds the FileWriteStrategy member by its case-insensitive name.

        Args:
            key_name (str | None): The string name of the member (e.g., 'atomic', 'in_place')
                or None.

        Returns:
            FileWriteStrategy | None: The matching FileWriteStrategy member or None
                if the key is None or unmatched.
        """
        if key_name is None:
            return None

        # 1. Convert input to uppercase to match Enum member names (ATOMIC, IN_PLACE)
        target_name: str = key_name.upper()

        # 2. Use the Enum's __members__ dictionary for a safe, direct lookup
        #    cls.__members__ maps string names to Enum instances.
        return cls.__members__.get(target_name)
