# topmark:header:start
#
#   project      : TopMark
#   file         : _helpers.py
#   file_relpath : tests/resolution/files/_helpers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for file-list resolution tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import topmark.resolution.files as file_resolver_mod

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from topmark.config.model import FrozenConfig


def py_content_matcher(path: Path) -> bool:
    """Return whether path should be treated as a Python test file."""
    return path.suffix == ".py"


def text_content_matcher(path: Path) -> bool:
    """Return whether path should be treated as a text test file."""
    return path.suffix in {".txt", ".md"}


class DummyType:
    """Minimal dummy file type for testing.

    Args:
        name: The identifier of the file type.
        predicate: A callable that returns True if a path matches this type.
    """

    def __init__(self, name: str, predicate: Callable[[Path], bool]) -> None:
        self.name: str = name
        self._pred: Callable[[Path], bool] = predicate

    def matches(self, path: Path) -> bool:
        """Check if a given path matches this dummy file type.

        Args:
            path: Path to test.

        Returns:
            True if the path matches, False otherwise.
        """
        return self._pred(path)


def write(p: Path, text: str = "") -> Path:
    """Write text to a file, creating parent directories if needed."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def resolve_selected(config: FrozenConfig) -> list[Path]:
    """Resolve files and return only the selected processing candidates."""
    return list(file_resolver_mod.resolve_file_list_with_diagnostics(config).selected)
