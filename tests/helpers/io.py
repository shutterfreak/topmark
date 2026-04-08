# topmark:header:start
#
#   project      : TopMark
#   file         : io.py
#   file_relpath : tests/helpers/io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Small shared I/O helpers for tests.

This module is intentionally tiny and hosts pure file-reading helpers that are
useful across test areas without pulling pytest fixtures or larger helper
modules into scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


# ---- File reading helpers ----


def read_text(path: Path) -> str:
    """Read a UTF-8 file and return its text contents."""
    return path.read_text(encoding="utf-8")
