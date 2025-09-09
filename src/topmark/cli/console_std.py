# topmark:header:start
#
#   file         : console_std.py
#   file_relpath : src/topmark/cli/console_std.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stdlib-based console implementation (no Click)."""

import sys
from typing import TextIO

from topmark.cli_shared.console_api import ConsoleLike


class StdConsole(ConsoleLike):
    """Simple console without colors."""

    def __init__(
        self, *, enable_color: bool = False, out: TextIO | None = None, err: TextIO | None = None
    ) -> None:
        """Initialize a StdConsole instance.

        Args:
            enable_color: Ignored for this implementation. Present only to keep
                the signature compatible with other ConsoleLike implementations.
            out: Stream for normal output. Defaults to sys.stdout.
            err: Stream for error/warning output. Defaults to sys.stderr.
        """
        self.enable_color = enable_color
        self.out = out or sys.stdout
        self.err = err or sys.stderr

    def print(self, text: str = "", *, nl: bool = True) -> None:
        """Write a message to stdout."""
        self.out.write(text + ("\n" if nl else ""))

    def warn(self, text: str, *, nl: bool = True) -> None:
        """Write a warning message to stderr."""
        self.err.write(text + ("\n" if nl else ""))

    def error(self, text: str, *, nl: bool = True) -> None:
        """Write an error message to stderr."""
        self.err.write(text + ("\n" if nl else ""))

    def styled(self, text: str, **style_kwargs: object) -> str:
        """Return a styled string (no-op if styling is disabled)."""
        return text
