# topmark:header:start
#
#   project      : TopMark
#   file         : console.py
#   file_relpath : tests/helpers/console.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Console helpers for tests.

This module provides small helpers for exercising code that writes through
TopMark's console protocol without introducing test-only protocol doubles.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from topmark.cli.console.standard_console import StdConsole


@dataclass(frozen=True)
class CapturedConsole:
    """A stdlib-backed console with captured stdout and stderr streams.

    Attributes:
        console: Console implementation under test.
        out: Captured stdout stream.
        err: Captured stderr stream.
    """

    console: StdConsole
    out: io.StringIO
    err: io.StringIO


def make_captured_console() -> CapturedConsole:
    """Create a `StdConsole` backed by in-memory text streams.

    Returns:
        Captured console bundle containing the console and both streams.
    """
    out = io.StringIO()
    err = io.StringIO()
    return CapturedConsole(
        console=StdConsole(out=out, err=err),
        out=out,
        err=err,
    )
