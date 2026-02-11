# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/emitters/text/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Small text-output (ANSI-capable) rendering utilities for the TopMark CLI.

This module hosts tiny helpers that are shared across the *TEXT* emitters. The helpers are
intentionally Click-free and Console-free: they operate on plain strings and return plain
strings.

Notes:
    - "Text" refers to TopMark's human-facing output format that *may* include ANSI styling.
    - Whether styling is enabled is decided by the CLI (color mode + output format) and passed
      down as a boolean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.core.presentation import Colorizer


def maybe_colorize(styler: Colorizer, text: str, *, enabled: bool) -> str:
    """Conditionally apply a styling function.

    This is a tiny helper used by TEXT emitters to avoid scattering `if color:` checks throughout
    rendering code.

    Args:
        styler: Callable that applies styling to a string (for example, a `chalk.*` function).
        text: Input text to render.
        enabled: When False, return `text` unchanged.

    Returns:
        Styled text when enabled; otherwise the original `text`.
    """
    return styler(text) if enabled else text
