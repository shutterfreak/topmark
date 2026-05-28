# topmark:header:start
#
#   project      : TopMark
#   file         : help.py
#   file_relpath : src/topmark/cli/help.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for Rich Click command help epilogs.

This module builds small Rich renderables used by `rich-click` help output.
It keeps command epilog formatting consistent while preserving plain Click for
command execution, context handling, validation, and shell completion.

The helpers are intentionally limited to human-facing command help. They should
not be used for machine-readable output, runtime reports, or pipeline rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, kw_only=True, slots=True)
class HelpExample:
    """Command-help example shown in a Rich Click epilog.

    Attributes:
        summary: Short human-readable explanation of the command.
        command_line: CLI command line to show below the description.
    """

    summary: str
    command_line: str


def render_examples_epilog(
    examples: Sequence[HelpExample],
    *,
    notes: Sequence[str] | None = None,
) -> Text:
    """Build a styled Rich Click epilog for examples and optional notes.

    Args:
        examples: Command examples to render in order.
        notes: Optional note lines rendered after the examples section.

    Returns:
        A Rich `Text` renderable suitable for use as a `rich-click` command
        epilog.
    """
    epilog = Text()

    if examples:
        epilog.append("Examples:\n", style="bold")
        for example in examples:
            epilog.append("  # ", style="dim")
            epilog.append(example.summary, style="dim")
            epilog.append("\n")
            epilog.append("  ")
            epilog.append(example.command_line, style="cyan")
            epilog.append("\n")

    if notes:
        if examples:
            epilog.append("\n")
        epilog.append("Notes:\n", style="bold")
        for note in notes:
            epilog.append("  • ", style="dim")
            epilog.append(note)
            epilog.append("\n")

    return epilog
