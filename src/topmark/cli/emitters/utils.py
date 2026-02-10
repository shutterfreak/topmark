# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/emitters/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI emitter utilities.

Small formatting helpers used by the human-facing CLI emitters.

This module is intentionally lightweight and should not perform configuration discovery, file I/O,
or other command logic. Prefer to keep computation in
[`topmark.cli_shared.emitters.shared`][topmark.cli_shared.emitters.shared] preparers and pass the
results to format-specific emitters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.constants import TOML_BLOCK_END, TOML_BLOCK_START

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


def emit_toml_block(
    *,
    console: ConsoleLike,
    title: str,
    toml_text: str,
    verbosity_level: int,
) -> None:
    """Emit a TOML snippet with optional banner and BEGIN/END markers.

    Used by config commands in the default (ANSI) output format.

    Args:
        console: Console instance for printing styled output.
        title: Title line shown above the block when verbosity > 0.
        toml_text: The TOML content to render.
        verbosity_level: Effective verbosity; 0 disables banners.
    """
    if verbosity_level > 0:
        console.print(
            console.styled(
                title,
                bold=True,
                underline=True,
            )
        )
        console.print(
            console.styled(
                TOML_BLOCK_START,
                fg="cyan",
                dim=True,
            )
        )

    console.print(
        console.styled(
            toml_text,
            fg="cyan",
        )
    )

    if verbosity_level > 0:
        console.print(
            console.styled(
                TOML_BLOCK_END,
                fg="cyan",
                dim=True,
            )
        )
