# topmark:header:start
#
#   file         : utils.py
#   file_relpath : src/topmark/cli_shared/utils.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI utility helpers for TopMark.

This module provides utility functions shared across CLI commands, including
header defaults extraction, color handling, and summary rendering.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence

from yachalk import chalk

from topmark.config import Config
from topmark.config.logging import get_logger
from topmark.constants import PYPROJECT_TOML_PATH, TOPMARK_VERSION

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.pipeline.context import ProcessingContext


logger = get_logger(__name__)


def default_header_overrides(*, info: str, file_label: str = "topmark.toml") -> dict[str, str]:
    """Build default header field overrides from TopMark’s own metadata.

    Looks up TopMark’s ``pyproject.toml`` for the ``license`` and ``copyright``
    fields and combines them with the supplied ``info`` and ``file_label``.

    Args:
      info (str): Short informational string to include in the generated header
        (for example, ``"Built-in defaults"``).
      file_label (str, optional): Value to use for the ``file`` field in the
        generated header. Defaults to ``"topmark.toml"``.

    Returns:
      dict[str, str]: Mapping of header fields suitable for rendering.

    Notes:
      - ``version`` is populated from the running TopMark version.
      - Missing metadata in ``pyproject.toml`` does not raise; it is omitted.
    """
    overrides: dict[str, str] = {
        "file": file_label,
        "version": TOPMARK_VERSION,
        "info": info,
    }
    cfg = Config.from_toml_file(PYPROJECT_TOML_PATH)
    if cfg:
        lic = cfg.field_values.get("license")
        cpr = cfg.field_values.get("copyright")
        if lic:
            overrides["license"] = lic
        if cpr:
            overrides["copyright"] = cpr
    return overrides


class OutputFormat(str, Enum):
    """Output format for CLI rendering.

    Members:
      DEFAULT: Human-friendly text output; may include ANSI color if enabled.
      JSON: A single JSON array of per-file objects (machine-readable).
      NDJSON: One JSON object per line (newline-delimited JSON; machine-readable).

    Notes:
      - Machine formats (``JSON`` and ``NDJSON``) must not include ANSI color or diffs.
      - Use with :class:`EnumParam` to parse ``--format`` from Click.
    """

    DEFAULT = "default"
    JSON = "json"
    NDJSON = "ndjson"
    MARKDOWN = "markdown"


class ColorMode(Enum):
    """User intent for colorized terminal output.

    Members:
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
      cli_mode: Parsed `ColorMode` value from `--color`; `None` means “not provided”.
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
    if cli_mode == ColorMode.ALWAYS:
        return True
    if cli_mode == ColorMode.NEVER:
        return False

    # 3) Env overrides
    force_color = os.getenv("FORCE_COLOR")
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


# --- CLI presentation helpers -------------------------------------------------
def classify_outcome(r: ProcessingContext) -> tuple[str, str, Callable[[str], str]]:
    """Classify a single file’s processing result into a summary bucket.

    This function converts a file’s `HeaderProcessingStatus` (available on
    `ProcessingContext.status`) into a stable, human‑facing bucket used by the
    CLI summary. It returns `(key, label, color_fn)` where:

    - `key` is a **stable identifier** suitable for aggregation (see below),
    - `label` is the **user‑visible** description printed in the summary, and
    - `color_fn` is a `yachalk` styling function to colorize the label in text mode.

    ### Buckets (stable contract)

    The following identifiers and labels are considered part of the CLI contract and
    are used by tests:

    **Strip pipeline** (`topmark strip`):
    - `strip:ready` → "would strip header"
    - `strip:none`  → "no header" (or "no changes to strip" in rare cases)

    **Default pipeline** (`topmark`):
    - `insert`      → "would insert header"
    - `update`      → "would update header"
    - `ok`          → "up-to-date"
    - `no_fields`   → "no fields to render"
    - `header:empty` / `header:malformed` → "header (empty|malformed)"
    - `compare_error` → "cannot compare"

    > Notes:
    > - Tests should match labels **loosely** (e.g., substrings) to allow minor
    >   wording adjustments without breaking the public contract.
    > - JSON/NDJSON output does not include ANSI color; only the human format uses
    >   `color_fn`.

    Precedence:
      - If the comparison result is UNCHANGED, this always takes precedence and the file
        is classified as compliant ("ok", "up-to-date"), regardless of other header or strip status.

    Args:
      r (ProcessingContext): Processing context for a single file.

    Returns:
      tuple[str, str, Callable[[str], str]]: A tuple ``(key, label, color_fn)`` where
      ``key`` is a stable identifier, ``label`` is a human-readable description, and
      ``color_fn`` is a function from ``yachalk`` used to colorize the label.
    """
    # Import locally to avoid any import cycles at module import time.
    from topmark.pipeline.context import (
        ComparisonStatus,
        FileStatus,
        GenerationStatus,
        HeaderStatus,
        StripStatus,
    )

    logger.debug("status: %s", r.status)

    if r.status.file is not FileStatus.RESOLVED:
        return (f"file:{r.status.file.name}", f"file {r.status.file.value}", r.status.file.color)

    # Highest precedence: if comparison says UNCHANGED, treat as compliant
    if r.status.comparison is ComparisonStatus.UNCHANGED:
        return ("ok", "up-to-date", chalk.green)

    # If the stripper step participated, prefer strip-centric labels.
    if r.status.strip is StripStatus.READY:
        # We computed updated_file_lines that remove the header.
        return ("strip:ready", "would strip header", chalk.yellow)

    if r.status.strip is StripStatus.NOT_NEEDED:
        # Nothing to strip — refine message based on what scanner/comparer saw.
        if r.status.header is HeaderStatus.MISSING:
            # No header present in the original file.
            return ("strip:none", "no header", chalk.green)
        # Fallback for strip pipeline where nothing changed.
        return ("strip:none", "no changes to strip", chalk.green)

    # If generation produced no fields, prefer a dedicated bucket over insert/missing
    if r.status.generation is GenerationStatus.NO_FIELDS:
        return ("no_fields", "no fields to render", chalk.yellow)

    # Non-strip pipelines (or stripper didn't run): use standard classification.
    if r.status.header is HeaderStatus.MISSING:
        if r.status.generation is GenerationStatus.PENDING:
            return ("strip:none", "no header", chalk.green)
        return ("insert", "would insert header", chalk.green)
    if r.status.header is HeaderStatus.DETECTED:
        if r.status.comparison is ComparisonStatus.CHANGED:
            return ("update", "would update header", chalk.yellow_bright)
        return ("compare_error", "cannot compare", chalk.red)
    if r.status.header in {HeaderStatus.EMPTY, HeaderStatus.MALFORMED}:
        return (
            f"header:{r.status.header.name.lower()}",
            f"header {r.status.header.value}",
            r.status.header.color,
        )
    return ("other", "other", chalk.gray)


def count_by_outcome(
    results: list[ProcessingContext],
) -> dict[str, tuple[int, str, Callable[[str], str]]]:
    """Count results by classification key.

    Keeps the first-seen label and color for each key.

    Args:
      results (list[ProcessingContext]): Processing contexts to classify and count.

    Returns:
      dict[str, tuple[int, str, Callable[[str], str]]]: Mapping from classification
      key to ``(count, label, color_fn)``.
    """
    counts: dict[str, tuple[int, str, Callable[[str], str]]] = {}
    for r in results:
        key, label, color = classify_outcome(r)
        n, _, _ = counts.get(key, (0, label, color))
        counts[key] = (n + 1, label, color)
    return counts


def write_updates(
    results: list[ProcessingContext],
    *,
    should_write: Callable[[ProcessingContext], bool],
) -> tuple[int, int]:
    """Write updated file contents back to disk according to a predicate.

    Args:
      results: Processing contexts to consider for writing.
      should_write: A predicate that returns True if the file should be written.

    Returns:
      A tuple `(written, failed)` with the number of files written and the number of failures.

    Notes:
      - The function writes `updated_file_lines` as a single string with the default UTF‑8 encoding.
      - Any exceptions per file are logged and counted as failures.
    """
    written = failed = 0
    for r in results:
        try:
            if should_write(r) and r.updated_file_lines is not None:
                Path(str(r.path)).write_text("".join(r.updated_file_lines), encoding="utf-8")
                written += 1
        except Exception as e:
            logger.error("Failed to write %s: %s", r.path, e)
            failed += 1

    return written, failed


def safe_unlink(path: Path | None) -> None:
    """Attempt to delete a file, ignoring any errors.

    Args:
      path: Path to delete, or None (no-op).

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
      headers: Column headers.
      rows: A sequence of row sequences (each row same length as ``headers``).
      align: Optional mapping of column index to alignment: ``"left"`` (default),
        ``"right"``, or ``"center"``.

    Returns:
      The Markdown table as a single string (ending with a newline).

    Notes:
      - Widths are computed from the visible string lengths of headers and cells.
      - Alignment uses Markdown syntax: ``:---`` (left), ``:---:`` (center), ``---:`` (right).
      - This function is Click‑free and suitable for reuse in any frontend.
    """
    if not headers:
        return ""
    ncols = len(headers)
    for r in rows:
        if len(r) != ncols:
            raise ValueError("All rows must have the same number of columns as headers")

    # Compute column widths
    widths = [len(str(h)) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    def _pad(text: str, w: int) -> str:
        return f"{text:<{w}}"

    # Header line
    header_line = " | ".join(_pad(str(headers[i]), widths[i]) for i in range(ncols))

    # Separator line with alignment markers
    def _sep_for(i: int) -> str:
        style = (align or {}).get(i, "left").lower()
        w = max(1, widths[i])
        if style == "right":
            return "-" * (w - 1) + ":" if w > 1 else ":"
        if style == "center":
            return ":" + ("-" * (w - 2) if w > 2 else "-") + ":"
        # left/default
        return "-" * w

    sep_line = " | ".join(_sep_for(i) for i in range(ncols))

    # Data lines
    data_lines = [" | ".join(_pad(str(r[i]), widths[i]) for i in range(ncols)) for r in rows]

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
