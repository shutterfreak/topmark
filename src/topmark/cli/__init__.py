# topmark:header:start
#
#   file         : __init__.py
#   file_relpath : src/topmark/cli/__init__.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark CLI package.

This package groups all Click command definitions and supporting utilities
for the TopMark command-line interface.

Typical usage:
    The console script entry point is defined in ``pyproject.toml`` as::

        [project.scripts]
        topmark = "topmark.cli.main:cli"

All subcommands live in [`topmark.cli.commands`][].
"""

from .main import cli

__all__ = ["cli"]
