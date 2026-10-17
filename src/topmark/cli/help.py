# topmark:header:start
#
#   project      : TopMark
#   file         : help.py
#   file_relpath : src/topmark/cli/help.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for Rich Click command help output.

This module builds small Rich renderables used by `rich-click` help output.

The helpers are intentionally limited to human-facing command help. They should
not be used for machine-readable output, runtime reports, or pipeline rendering.
Click remains the authoritative runtime, validation, context, and shell
completion layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import ParamSpec
from typing import TypeVar
from typing import cast

import click
import rich_click
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence


_P = ParamSpec("_P")
_R = TypeVar("_R")


@dataclass(frozen=True, kw_only=True, slots=True)
class HelpExample:
    """Command-help example shown in a Rich Click epilog.

    Attributes:
        summary: Short human-readable explanation of the command.
        command_line: CLI command line to show below the description.
    """

    summary: str
    command_line: str


def _rich_click_decorator(name: str) -> object:
    """Resolve a rich-click decorator behind the local typing boundary."""
    return cast("object", getattr(rich_click, name))


def rich_click_option_panel(
    name: str,
    *,
    options: list[str],
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Return a typed adapter for rich-click's option-panel decorator.

    rich-click exposes ``Unknown`` through its decorator annotations. Keep that
    third-party typing boundary here so command definitions retain their exact
    callable signatures.

    Args:
        name: User-facing panel title.
        options: Canonical option spellings displayed in the panel.

    Returns:
        A decorator that preserves the decorated callable's signature.
    """
    factory = cast("Callable[..., object]", _rich_click_decorator("option_panel"))
    decorator = factory(name, options=options)
    return cast("Callable[[Callable[_P, _R]], Callable[_P, _R]]", decorator)


def documented_paths_argument(
    help_text: str,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Return a typed rich-click argument decorator for processing paths.

    Args:
        help_text: Human-facing description of the positional ``PATHS`` input.

    Returns:
        A decorator that preserves the decorated callable's signature.
    """
    factory = cast("Callable[..., object]", _rich_click_decorator("argument"))
    decorator = factory(
        "paths",
        nargs=-1,
        type=click.UNPROCESSED,
        help=help_text,
    )
    return cast("Callable[[Callable[_P, _R]], Callable[_P, _R]]", decorator)


def render_examples_epilog(
    examples: Sequence[HelpExample],
    *,
    notes: Sequence[str] | None = None,
    reference_url: str | None = None,
) -> Text:
    """Build a styled Rich Click epilog for examples and optional notes.

    Args:
        examples: Command examples to render in order.
        notes: Optional note lines rendered after the examples section.
        reference_url: Optional version-aware URL for the command's complete reference.

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

    if reference_url:
        if examples or notes:
            epilog.append("\n")
        epilog.append("Full reference:\n", style="bold")
        epilog.append("  ")
        epilog.append(reference_url, style="cyan underline")
        epilog.append("\n")

    return epilog
