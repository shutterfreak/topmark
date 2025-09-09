# topmark:header:start
#
#   file         : console_helpers.py
#   file_relpath : src/topmark/cli/console_helpers.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Utilities for obtaining a program-output console independent of Click.

This module exposes :func:`get_console_safely` which returns the project’s
console for user-facing output when running under a Click context, and a
no-dependency stdlib fallback (`StdConsole`) when no context is active
(e.g., when the API is invoked directly from tests).
"""

import click

from topmark.cli.console_std import StdConsole
from topmark.cli_shared.console_api import ConsoleLike


def get_console_safely() -> ConsoleLike:
    """Return a ConsoleLike using the active Click context when available.

    If an active Click context exists and a console instance is stored in
    ``ctx.obj["console"]``, that console is returned. Otherwise, a
    :class:`~topmark.cli.console_std.StdConsole` is returned to avoid
    raising ``RuntimeError: There is no active click context`` when the
    library is used programmatically (e.g., via pytest).
    """
    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(getattr(ctx, "obj", None), dict) and "console" in ctx.obj:
        return ctx.obj["console"]
    return StdConsole()
