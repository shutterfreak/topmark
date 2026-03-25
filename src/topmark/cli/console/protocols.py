# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/cli/console/protocols.py
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
from typing import runtime_checkable


@runtime_checkable
class ConsoleProtocol(Protocol):
    """Minimal protocol for user-facing CLI console output.

    Implementations may be backed by Click, Rich, or plain stdlib streams. The
    protocol intentionally stays small so commands depend only on core output
    behavior, not on framework-specific details.
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
