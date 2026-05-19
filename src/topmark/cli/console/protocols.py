# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/cli/console/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Framework-agnostic console protocol for user-facing CLI output.

This module defines the small behavioral surface used by CLI commands and
presentation emitters to write user-facing text through explicit console
objects. It deliberately stays separate from internal logging and avoids
coupling command code to Click, Rich, or stdlib stream implementations.
"""

from __future__ import annotations

from typing import Protocol
from typing import TypeGuard
from typing import runtime_checkable


@runtime_checkable
class ConsoleProtocol(Protocol):
    """Minimal behavioral protocol for user-facing CLI console output.

    Implementations may be backed by Click, Rich, or plain stdlib streams. The
    protocol intentionally stays small so commands depend only on core output
    behavior, not on framework-specific details. Console instances are created
    during CLI state initialization and passed explicitly to commands and
    emitters; this protocol does not imply ownership of global stdout/stderr.
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


def is_console_protocol(value: object) -> TypeGuard[ConsoleProtocol]:
    """Return whether ``value`` exposes the console protocol methods.

    This helper performs a lightweight runtime guard for dynamically supplied
    console objects. It intentionally checks only that the expected methods are
    callable; static type checkers remain responsible for validating signatures.
    """
    return (
        callable(getattr(value, "print", None))
        and callable(getattr(value, "warn", None))
        and callable(getattr(value, "error", None))
    )
