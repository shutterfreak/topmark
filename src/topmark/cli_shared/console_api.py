# topmark:header:start
#
#   project      : TopMark
#   file         : console_api.py
#   file_relpath : src/topmark/cli_shared/console_api.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Framework-agnostic console interface for program output.

This protocol defines the small surface used by CLI commands to emit
user-facing output, separate from internal logging.
"""

from __future__ import annotations

from typing import Protocol


class ConsoleLike(Protocol):
    """Minimal interface for a console used by CLI commands.

    Implementations may use Click, Rich, or plain stdlib streams. The purpose
    is to decouple program output from the logging subsystem.
    """

    def print(self, text: str = "", *, nl: bool = True) -> None:
        """Write a message to stdout."""
        ...

    def warn(self, text: str, *, nl: bool = True) -> None:
        """Write a warning message to stderr."""
        ...

    def error(self, text: str, *, nl: bool = True) -> None:
        """Write an error message to stderr."""
        ...

    def styled(self, text: str, **style_kwargs: object) -> str:
        """Return a styled string (no-op if styling is disabled)."""
        ...
