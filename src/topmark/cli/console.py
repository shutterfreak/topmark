# topmark:header:start
#
#   project      : TopMark
#   file         : console.py
#   file_relpath : src/topmark/cli/console.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Console abstraction for user-facing program output.

This module provides a `Console` class that separates CLI output from
internal logging. Use this for messages intended for end users, while
reserving `logging` for diagnostics.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO, TypedDict

import click

from topmark.cli_shared.console_api import ConsoleLike


# This TypedDict is for documentation and type-checking on the *caller* side.
class StyleKwargs(TypedDict, total=False):
    """Keyword arguments accepted by click.style()."""

    fg: str
    bg: str
    bold: bool
    dim: bool
    underline: bool
    blink: bool
    reverse: bool
    strikethrough: bool
    # Ensure all valid arguments from click.style() are included here


class ClickConsole(ConsoleLike):
    """Program-output console, independent from the logger.

    Args:
        enable_color (bool): If True, enables ANSI color codes in the output.
            Otherwise, all output is plain text.
        out (TextIO | None): The text stream to use for standard output.
            Defaults to `sys.stdout`.
        err (TextIO | None): The text stream to use for error output.
            Defaults to `sys.stderr`.

    Attributes:
        enable_color (bool): Whether to emit ANSI color codes.
        out (TextIO | None): Stream for standard output (defaults to sys.stdout).
        err (TextIO | None): Stream for error output (defaults to sys.stderr).
    """

    enable_color: bool
    out: TextIO | None
    err: TextIO | None

    def __init__(
        self,
        *,
        enable_color: bool = True,
        out: TextIO | None = None,
        err: TextIO | None = None,
    ) -> None:
        self.enable_color = enable_color
        self.out = out or sys.stdout
        self.err = err or sys.stderr

    def print(self, text: str = "", *, nl: bool = True) -> None:
        """Write a message to stdout.

        Args:
            text (str): Message text.
            nl (bool): If True, append a newline.
        """
        click.echo(text, nl=nl, file=self.out, color=self.enable_color)

    def warn(self, text: str, *, nl: bool = True) -> None:
        """Write a warning message to stderr.

        Args:
            text (str): Warning text.
            nl (bool): If True, append a newline.
        """
        click.secho(text, nl=nl, file=self.err, color=self.enable_color, fg="yellow")

    def error(self, text: str, *, nl: bool = True) -> None:
        """Write an error message to stderr.

        Args:
            text (str): Error text.
            nl (bool): If True, append a newline.
        """
        click.secho(text, nl=nl, file=self.err, color=self.enable_color, fg="bright_red")

    def styled(self, text: str, **style_kwargs: Any) -> str:
        """Return a styled string using click.style.

        Args:
            text (str): Text to style.
            **style_kwargs (Any): Subset of keyword arguments supported by click.style.
                Expected keys are defined in the StyleKwargs TypedDict.

        Returns:
            str: The styled text (or plain text if color is disabled).
        """
        if not self.enable_color:
            return text
        return click.style(text, **style_kwargs)
