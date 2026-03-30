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
    - `PatternSource`: immutable reference to a file containing patterns
      (e.g., include/exclude lists) together with the base directory used to
      interpret relative entries inside that file.

Design notes:
    - Keep side effects out of this module; it should stay dependency-free
      (stdlib only) to remain safe for low-level imports.
    - Prefer structural typing ([`ConfigMapping`][topmark.api.types.ConfigMapping])
      for CLI/API inputs so the config layer remains decoupled from any specific CLI framework.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pathspec import PathSpec

from topmark.core.enum_mixins import KeyedStrEnum
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from topmark.core.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


# --- Centralized helper for compiling gitwildmatch PathSpec ---


@functools.lru_cache(maxsize=256)
def _compile_gitignore_pathspec_cached(patterns: tuple[str, ...]) -> PathSpec:
    """Compile gitignore-style patterns into a cached `PathSpec`.

    Args:
        patterns: Pattern tuple (hashable cache key).

    Returns:
        Compiled `PathSpec` matcher.
    """
    # `PathSpec.from_lines` accepts an iterable; we materialize to a list for
    # stable iteration and to support one-shot iterables.
    return PathSpec.from_lines("gitignore", patterns)


def compile_gitignore_pathspec(patterns: Iterable[str]) -> PathSpec:
    """Compile gitignore-style patterns into a `PathSpec`.

    This centralizes `PathSpec.from_lines(GitIgnoreBasicPattern, ...)` usage so all pattern
    compilation shares the same semantics.

    Note:
        Internally this function uses an LRU cache keyed by the pattern tuple.

    Args:
        patterns: Iterable of gitignore-style patterns.

    Returns:
        Compiled `PathSpec` matcher.
    """
    return _compile_gitignore_pathspec_cached(tuple(patterns))


# ------------------ Pattern source reference ------------------
@dataclass(frozen=True)
class PatternSource:
    """Reference to a pattern or file list declared in a config source.

    This value object captures both the absolute path to the referenced file
    and the *base directory* used to interpret the file's contents when it
    contains relative patterns (e.g., a gitignore-style file).

    Attributes:
        path: Absolute path to the referenced file (e.g., ".gitignore").
        base: Absolute directory used as the matching base for the file's patterns. Typically
            equals ``path.parent``.
    """

    path: Path
    base: Path


@dataclass(frozen=True)
class PatternGroup:
    """A group of gitignore-style patterns with an interpretation base directory.

    This is used for pattern arrays declared *in configuration files* (e.g.
    `[files].include_patterns` / `[files].exclude_patterns`). Each declaring config file
    contributes its own group so patterns are evaluated relative to the directory of the
    declaring file.

    The `to_pathspec()` method compiles these patterns as gitignore-style matchers.

    Attributes:
        patterns: The raw patterns exactly as declared.
        base: Absolute directory used as the matching base for these patterns.
    """

    patterns: tuple[str, ...]
    base: Path

    def is_empty(self) -> bool:
        """Return True if this group contains no patterns."""
        return not self.patterns

    def to_pathspec(self) -> PathSpec:
        """Compile and return a PathSpec for these patterns."""
        return _compile_gitignore_pathspec_cached(self.patterns)


class OutputTarget(KeyedStrEnum):
    """Available targets for writing processed file content."""

    FILE = ("file", "Write to file", ("FILE",))
    STDOUT = ("stdout", "Write to STDOUT", ("STDOUT",))


class FileWriteStrategy(KeyedStrEnum):
    """Available strategies for writing file content.

    The enum `.value` is the stable machine key used in config and JSON.
    The human label lives in `.label`.
    """

    ATOMIC = ("atomic", "Safe atomic writer (default)", ("ATOMIC", "safe", "default"))
    INPLACE = ("inplace", "Fast in-place writer", ("IN_PLACE", "INPLACE", "in_place", "fast"))
