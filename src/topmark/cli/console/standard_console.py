# topmark:header:start
#
#   project      : TopMark
#   file         : standard_console.py
#   file_relpath : src/topmark/cli/console/standard_console.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stdlib-based console implementation used outside Click contexts."""

from __future__ import annotations

import sys
from typing import TextIO

from topmark.cli.console.protocols import ConsoleProtocol


class StdConsole(ConsoleProtocol):
    """Simple console implementation backed by stdlib text streams.

    Args:
        enable_color: Ignored for this implementation. Present only to keep the
            constructor shape aligned with the Click-backed console.
        out: Stream for normal output. Defaults to `sys.stdout`.
        err: Stream for warning/error output. Defaults to `sys.stderr`.
    """

    def __init__(
        self, *, enable_color: bool = False, out: TextIO | None = None, err: TextIO | None = None
    ) -> None:
        self.enable_color: bool = enable_color
        self.out: TextIO = out or sys.stdout
        self.err: TextIO = err or sys.stderr

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
