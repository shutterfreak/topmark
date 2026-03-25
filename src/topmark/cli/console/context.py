# topmark:header:start
#
#   project      : TopMark
#   file         : context.py
#   file_relpath : src/topmark/cli/console/context.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolve the active CLI console with a safe stdlib fallback.

This module provides `resolve_console()`, which returns the console stored in
an active Click context when available, and otherwise falls back to a
stdlib-based [`StdConsole`][topmark.cli.console.standard_console.StdConsole].
This avoids `RuntimeError` when TopMark code is invoked programmatically
outside Click, for example from tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.console.standard_console import StdConsole
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli.console.protocols import ConsoleProtocol


def resolve_console() -> ConsoleProtocol:
    """Return the active CLI console when available.

    If an active Click context exists and a console instance is stored in
    `ctx.obj[ArgKey.CONSOLE]`, that console is returned. Otherwise, a
    [`StdConsole`][topmark.cli.console.standard_console.StdConsole] is returned
    so programmatic use outside Click remains safe.
    """
    ctx: click.Context | None = click.get_current_context(silent=True)
    if (
        ctx is not None
        and isinstance(getattr(ctx, "obj", None), dict)
        and ArgKey.CONSOLE in ctx.obj
    ):
        console: ConsoleProtocol = ctx.obj[ArgKey.CONSOLE]
        return console
    return StdConsole()
