# topmark:header:start
#
#   file         : console.py
#   file_relpath : src/topmark/cli_shared/console.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Console abstraction for user-facing program output.

This module provides a `Console` class that separates CLI output from
internal logging. Use this for messages intended for end users, while
reserving `logging` for diagnostics.
"""

import sys
from typing import Any, TextIO, TypedDict

import click


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


class Console:
    """Program-output console, independent from the logger.

    Attributes:
        enable_color (bool): Whether to emit ANSI color codes.
        out (TextIO): Stream for standard output (defaults to sys.stdout).
        err (TextIO): Stream for error output (defaults to sys.stderr).
    """

    def __init__(
        self, *, enable_color: bool = True, out: TextIO | None = None, err: TextIO | None = None
    ) -> None:
        """Initializes the Console.

        Args:
            enable_color: If True, enables ANSI color codes in the output.
                Otherwise, all output is plain text.
            out: The text stream to use for standard output.
                Defaults to `sys.stdout`.
            err: The text stream to use for error output.
                Defaults to `sys.stderr`.
        """
        self.enable_color = enable_color
        self.out = out or sys.stdout
        self.err = err or sys.stderr

    def print(self, text: str = "", *, nl: bool = True) -> None:
        """Write a message to stdout.

        Args:
            text: Message text.
            nl: If True, append a newline.
        """
        click.echo(text, nl=nl, file=self.out, color=self.enable_color)

    def warn(self, text: str, *, nl: bool = True) -> None:
        """Write a warning message to stderr.

        Args:
            text: Warning text.
            nl: If True, append a newline.
        """
        click.echo(text, nl=nl, file=self.err, color=self.enable_color)

    def error(self, text: str, *, nl: bool = True) -> None:
        """Write an error message to stderr.

        Args:
            text: Error text.
            nl: If True, append a newline.
        """
        click.echo(text, nl=nl, file=self.err, color=self.enable_color)

    def styled(self, text: str, **style_kwargs: Any) -> str:
        """Return a styled string using click.style.

        Args:
            text: Text to style.
            **style_kwargs: Subset of keyword arguments supported by click.style.
                            Expected keys are defined in the StyleKwargs TypedDict.

        Returns:
            str: The styled text (or plain text if color is disabled).
        """
        if not self.enable_color:
            return text
        return click.style(text, **style_kwargs)
