# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli_shared/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Click-independent CLI helpers for TopMark.

This module provides utility functions that are shared across CLI frontends
but do not depend on Click or console instances, including:

- OutputFormat and ColorMode enums.
- Color-mode resolution based on CLI flags, environment, and output format.
- File writing / unlinking helpers used by the pipeline.
- Markdown table rendering for documentation-style output.
- Human-friendly callable formatting.

These helpers are deliberately kept Click-free so they can be reused from
both command-line entry points and other potential frontends or tests.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from inspect import getmodule
from pathlib import Path
from typing import TYPE_CHECKING, Any

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import UpdatedView


logger: TopmarkLogger = get_logger(__name__)


class OutputFormat(str, Enum):
    """Output format for CLI rendering.

    Attributes:
        DEFAULT: Human-friendly text output; may include ANSI color if enabled.
        JSON: A single JSON document (machine-readable). See the
            `Machine output` developer docs for the schema.
        NDJSON: One JSON object per line (newline-delimited JSON; machine-readable).
        MARKDOWN: A Markdown document.

    Notes:
        - Machine formats (``JSON`` and ``NDJSON``) must not include ANSI color
          or diffs.
        - Use with [`topmark.cli.cli_types.EnumChoiceParam`][] to parse
          ``--output-format`` from Click.
    """

    DEFAULT = "default"
    JSON = "json"
    NDJSON = "ndjson"
    MARKDOWN = "markdown"


class ColorMode(Enum):
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
    cli_mode: ColorMode | None,
    output_format: str | None,  # "default" | "json" | "ndjson" | None
    stdout_isatty: bool | None = None,
) -> bool:
    """Determine whether color output should be enabled.

    Decision precedence:
        1. **Machine formats**: If `output_format` is `"json"` or `"ndjson"`, return False.
        2. **CLI override**: If `cli_mode` is `ALWAYS` → True; if `NEVER` → False.
        3. **Environment**:
            - `FORCE_COLOR` (set and not equal to `"0"`) → True
            - `NO_COLOR` (set to any value) → False
        4. **Auto**: If none of the above decide, return `stdout.isatty()`.

    Args:
        cli_mode (ColorMode | None): Parsed `ColorMode` value from `--color`;
            `None` means “not provided”.
        output_format (str | None): Structured output mode; `"json"` or `"ndjson"` suppress color.
        stdout_isatty (bool | None): Optional override for TTY detection. When `None`, the function
            calls `sys.stdout.isatty()` and falls back to `False` on error.

    Returns:
        bool: True if ANSI color should be enabled; False otherwise.

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
    if cli_mode == ColorMode.ALWAYS:
        return True
    if cli_mode == ColorMode.NEVER:
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
        except Exception:
            stdout_isatty = False
    return bool(stdout_isatty)


# TODO: check if still used (is implemented in pipeline now)
def write_updates(
    results: list[ProcessingContext],
    *,
    should_write: Callable[[ProcessingContext], bool],
) -> tuple[int, int]:
    """Write updated file contents back to disk according to a predicate.

    Args:
        results (list[ProcessingContext]): Processing contexts to consider for writing.
        should_write (Callable[[ProcessingContext], bool]): A predicate that returns True
            if the file should be written.

    Returns:
        tuple[int, int]: A tuple `(written, failed)` with the number of files written
            and the number of failures.

    Notes:
        - The function writes `updated_file_lines` as a single string with the default
          UTF‑8 encoding.
        - Any exceptions per file are logged and counted as failures.
        - Files are written with `newline=""` to avoid platform newline translation.
    """
    written: int = 0
    failed: int = 0
    for r in results:
        try:
            updated_view: UpdatedView | None = r.views.updated
            if should_write(r) and updated_view is not None and updated_view.lines:
                # Write exactly what the pipeline produced:
                #  - `updated_file_lines` are keepends=True lines with the desired newline style
                #  - We open with newline="" to disable any \n translation on output
                data: str = "".join(updated_view.lines)
                with Path(r.path).open("w", encoding="utf-8", newline="") as fh:
                    fh.write(data)
                written += 1
        except Exception as e:
            logger.error("Failed to write %s: %s", r.path, e)
            failed += 1

    return written, failed


def safe_unlink(path: Path | None) -> None:
    """Attempt to delete a file, ignoring any errors.

    Args:
        path (Path | None): Path to delete, or None (no-op).

    Notes:
        - Any errors during deletion are logged and ignored.
    """
    if path and path.exists():
        try:
            path.unlink()
        except Exception as e:
            logger.error("Failed to delete %s: %s", path, e)


# --- Markdown rendering helpers ---------------------------------------------


def render_markdown_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    align: Mapping[int, str] | None = None,
) -> str:
    """Render a GitHub‑flavoured Markdown table with padded columns.

    Args:
        headers (Sequence[str]): Column headers.
        rows (Sequence[Sequence[str]]): A sequence of row sequences (each row same length
            as ``headers``).
        align (Mapping[int, str] | None): Optional mapping of column index to alignment:
            ``"left"`` (default), ``"right"``, or ``"center"``.

    Returns:
        str: The Markdown table as a single string (ending with a newline).

    Notes:
        - Widths are computed from the visible string lengths of headers and cells.
        - Alignment uses Markdown syntax: ``:---`` (left), ``:---:`` (center), ``---:`` (right).
        - This function is Click‑free and suitable for reuse in any frontend.

    Raises:
        ValueError: If any row length differs from the number of headers.
    """
    if not headers:
        return ""
    ncols: int = len(headers)
    for r in rows:
        if len(r) != ncols:
            raise ValueError("All rows must have the same number of columns as headers")

    # Compute column widths
    widths: list[int] = [len(str(h)) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    def _pad(text: str, w: int) -> str:
        return f"{text:<{w}}"

    # Header line
    header_line: str = " | ".join(_pad(str(headers[i]), widths[i]) for i in range(ncols))

    # Separator line with alignment markers
    def _sep_for(i: int) -> str:
        style: str = (align or {}).get(i, "left").lower()
        w: int = max(1, widths[i])
        if style == "right":
            return "-" * (w - 1) + ":" if w > 1 else ":"
        if style == "center":
            return ":" + ("-" * (w - 2) if w > 2 else "-") + ":"
        # left/default
        return "-" * w

    sep_line: str = " | ".join(_sep_for(i) for i in range(ncols))

    # Data lines
    data_lines: list[str] = [
        " | ".join(_pad(str(r[i]), widths[i]) for i in range(ncols)) for r in rows
    ]

    return (
        "| "
        + header_line
        + " |\n"
        + "| "
        + sep_line
        + " |\n"
        + "\n".join("| " + line + " |" for line in data_lines)
        + "\n"
    )


def format_callable_pretty(obj: Any) -> str:
    """Return a human-friendly (module.qualname) for any callable.

    Handles functions, bound methods, callable instances, and partials. Falls
    back to the callable's class name when needed, and uses ``inspect.getmodule``
    as a last resort to resolve the module name.

    Args:
        obj (Any): The callable object to describe.

    Returns:
        str: A string like ``"(package.module.QualifiedName)"`` or ``"(QualifiedName)"``
            if the module cannot be resolved.
    """
    mod_name: str | None = getattr(obj, "__module__", None)
    call_name: str | None = getattr(obj, "__qualname__", None)

    if call_name is None:
        call_name = getattr(obj, "__name__", None)
    if call_name is None:
        call_name = type(obj).__name__

    if not mod_name:
        mod = getmodule(obj)
        if mod is not None and getattr(mod, "__name__", None):
            mod_name = mod.__name__

    return f"({mod_name}.{call_name})" if mod_name else f"({call_name})"
