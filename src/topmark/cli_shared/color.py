# topmark:header:start
#
#   project      : TopMark
#   file         : color.py
#   file_relpath : src/topmark/cli_shared/color.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Click-independent color helpers for TopMark.

This module provides utility functions that are shared across CLI frontends
but do not depend on Click or console instances, including:

- ColorMode enum.
- Color-mode resolution based on CLI flags, environment, and output format.

These helpers are deliberately kept Click-free so they can be reused from
both command-line entry points and other potential frontends or tests.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


class ColorMode(str, Enum):
    """User intent for colorized terminal output.

    Attributes:
        AUTO: Enable color only when appropriate (typically when stdout is a TTY).
        ALWAYS: Force-enable color regardless of TTY status.
        NEVER: Disable color entirely.

    Typical usage:
        - Parse `--color=auto|always|never` as `ColorMode`.
        - Pass the parsed value to `resolve_color_mode()` along with the current
          output format (e.g., `"json"` or `"ndjson"`) to obtain a final `bool`
          indicating whether to emit ANSI styles.

    Example:
        >>> resolve_color_mode(cli_mode=ColorMode.AUTO, output_format=None)
        True  # on an interactive terminal
        >>> resolve_color_mode(cli_mode=ColorMode.AUTO, output_format="json")
        False  # machine formats are always colorless
    """

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


def resolve_color_mode(
    *,
    color_mode_override: ColorMode | None,
    output_format: str | None,  # "default" | "json" | "ndjson" | None
    stdout_isatty: bool | None = None,
) -> bool:
    """Determine whether color output should be enabled.

    Decision precedence:
        1. **Machine formats**: If `output_format` is `"json"` or `"ndjson"`, return False.
        2. **CLI override**: If `color_mode_override` is `ALWAYS` → True; if `NEVER` → False.
        3. **Environment**:
            - `FORCE_COLOR` (set and not equal to `"0"`) → True
            - `NO_COLOR` (set to any value) → False
        4. **Auto**: If none of the above decide, return `stdout.isatty()`.

    Args:
        color_mode_override: Parsed `ColorMode` value from `--color`;
            `None` means “not provided”.
        output_format: Structured output mode; `"json"` or `"ndjson"` suppress color.
        stdout_isatty: Optional override for TTY detection. When `None`, the function
            calls `sys.stdout.isatty()` and falls back to `False` on error.

    Returns:
        True if ANSI color should be enabled; False otherwise.

    Examples:
        >>> resolve_color_mode(cli_mode=ColorMode.NEVER, output_format=None)
        False
        >>> resolve_color_mode(cli_mode=None, output_format="ndjson")
        False
        >>> resolve_color_mode(cli_mode=None, output_format=None, stdout_isatty=True)
        True
    """
    # 1) Machine formats never use color
    if output_format and output_format.lower() in {"json", "ndjson"}:
        return False

    # 2) CLI overrides
    if color_mode_override == ColorMode.ALWAYS:
        return True
    if color_mode_override == ColorMode.NEVER:
        return False

    # 3) Env overrides
    force_color: str | None = os.getenv("FORCE_COLOR")
    if force_color and force_color != "0":
        return True
    if os.getenv("NO_COLOR") is not None:
        return False

    # 4) Auto: TTY?
    if stdout_isatty is None:
        try:
            stdout_isatty = sys.stdout.isatty()
        except OSError:
            stdout_isatty = False
    return bool(stdout_isatty)
