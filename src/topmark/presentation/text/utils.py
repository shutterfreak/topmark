# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/presentation/text/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared presentation utilities for TEXT.

This module provides helpers to render text fragments.

Scope:
- Pure string rendering only (no I/O, no Click/Rich console usage).
- Safe to import from any frontend (CLI, API tests, etc.).

The helpers here are intentionally small and composable; command-specific
formatting belongs in the command's presentation module.
"""

from __future__ import annotations

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.constants import TOML_BLOCK_END
from topmark.constants import TOML_BLOCK_START
from topmark.core.presentation import StyleRole

# Config helpers


def render_toml_text(
    *,
    title: str,
    toml_text: str,
    verbosity_level: int,
    styled: bool,
) -> str:
    """Render a TOML snippet with optional banner and BEGIN/END markers.

    Used by config commands in the default (ANSI) output format.

    Args:
        title: Title line shown above the block when verbosity > 0.
        toml_text: The TOML content to render.
        verbosity_level: Effective verbosity; 0 disables banners.
        styled: Whether to render the TOML with styles.

    Returns:
        Rendered TOML text as plain string.
    """
    heading_title_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=styled)
    toml_marker_styler: TextStyler = style_for_role(StyleRole.MARKER_LINE, styled=styled)

    parts: list[str] = []

    if verbosity_level > 0:
        parts.append(
            heading_title_styler(
                title,
            )
        )

        parts.append(
            toml_marker_styler(
                TOML_BLOCK_START,
            )
        )

    parts.append(toml_text)

    if verbosity_level > 0:
        parts.append(
            toml_marker_styler(
                TOML_BLOCK_END,
            )
        )

    return "\n".join(parts)
