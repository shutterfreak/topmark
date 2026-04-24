# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli/console/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Console runtime support for the TopMark CLI.

This package contains the concrete console implementations, protocol types,
color-resolution helpers, and small runtime utilities used by CLI commands to
print user-facing output.

Responsibilities:
- Define the framework-agnostic console protocol used by commands.
- Provide the Click-backed console implementation and a stdlib fallback.
- Resolve terminal color behavior from CLI flags, environment, and output mode.
- Expose small runtime helpers such as active-console resolution and terminal
  width inspection.

This package is intentionally distinct from `topmark.presentation`, which owns
human-facing report preparation and pure TEXT / MARKDOWN rendering.
"""

from __future__ import annotations

from topmark.cli.console.click_console import ClickStyleKwargs
from topmark.cli.console.click_console import Console
from topmark.cli.console.color import ColorMode
from topmark.cli.console.color import resolve_color_mode
from topmark.cli.console.protocols import ConsoleProtocol
from topmark.cli.console.standard_console import StdConsole
from topmark.cli.console.utils import get_console_line_width

__all__ = (
    "ClickStyleKwargs",
    "ColorMode",
    "Console",
    "ConsoleProtocol",
    "StdConsole",
    "get_console_line_width",
    "resolve_color_mode",
)
