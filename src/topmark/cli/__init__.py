# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark CLI package.

This package groups all Click command definitions and supporting utilities
for the TopMark command-line interface.

Examples:
    The console script entry point is defined in `pyproject.toml`:

    ```toml
    [project.scripts]
    topmark = "topmark.cli.main:cli"
    ```

All subcommands live in [`topmark.cli.commands`][topmark.cli.commands].
"""

from __future__ import annotations
