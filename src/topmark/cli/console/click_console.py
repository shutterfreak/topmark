# topmark:header:start
#
#   project      : TopMark
#   file         : click_console.py
#   file_relpath : src/topmark/cli/console/click_console.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Click-backed console implementation for TopMark CLI output.

This module provides the primary concrete console used by CLI commands for
user-facing output. It is intentionally separate from the logging subsystem.
"""

from __future__ import annotations

import sys
from typing import TextIO
from typing import TypedDict

import click

from topmark.cli.console.protocols import ConsoleProtocol


# This TypedDict is for documentation and type-checking on the *caller* side.
class ClickStyleKwargs(TypedDict, total=False):
    """Documented subset of keyword arguments accepted by `click.style()`."""

    fg: str
    bg: str
    bold: bool
    dim: bool
    underline: bool
    blink: bool
    reverse: bool
    strikethrough: bool
    # Ensure all valid arguments from click.style() are included here


class Console(ConsoleProtocol):
    """Program-output console, independent from the logger.

    Args:
        enable_color: If True, enables ANSI color codes in the output. Otherwise, all output is
            plain text.
        out: The text stream to use for standard output. Defaults to `sys.stdout`.
        err: The text stream to use for error output. Defaults to `sys.stderr`.

    Attributes:
        enable_color: Whether to emit ANSI color codes.
        out: Stream for standard output (defaults to sys.stdout).
        err: Stream for error output (defaults to sys.stderr).
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
        click.secho(text, nl=nl, file=self.err, color=self.enable_color, fg="yellow")

    def error(self, text: str, *, nl: bool = True) -> None:
        """Write an error message to stderr.

        Args:
            text: Error text.
            nl: If True, append a newline.
        """
        click.secho(text, nl=nl, file=self.err, color=self.enable_color, fg="bright_red")
