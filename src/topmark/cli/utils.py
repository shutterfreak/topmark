# topmark:header:start
#
#   file         : utils.py
#   file_relpath : src/topmark/cli/utils.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI utility helpers for TopMark.

This module contains small utilities that are shared across CLI commands:

- `default_header_overrides()`: Builds a dict of default header fields using TopMark’s
  own pyproject metadata (license, copyright).
- Color handling utilities:
  - `ColorMode`: Enum describing user intent for colorized output.
  - `resolve_color_mode()`: Decides whether color should be enabled, based on a
    combination of CLI flags, environment variables, output format, and TTY detection.

Color decision precedence:
1) Machine formats (`json`, `ndjson`) are always **colorless**.
2) Explicit CLI color (`--color=always|never|auto`) if provided.
3) Environment variables:
   - `FORCE_COLOR` (any non-empty value except `"0"`) forces color.
   - `NO_COLOR` (set to any value) disables color.
4) Fallback to `auto` (enable color only when stdout is a TTY).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from enum import Enum

from yachalk import chalk

from topmark.config import Config
from topmark.constants import PYPROJECT_TOML_PATH, TOPMARK_VERSION
from topmark.pipeline.context import ProcessingContext


def default_header_overrides(*, info: str, file_label: str = "topmark.toml") -> dict[str, str]:
    """Build default header field overrides from TopMark’s own metadata.

    Looks up TopMark’s `pyproject.toml` for the `license` and `copyright`
    fields and combines them with the supplied `info` and `file_label`.

    Args:
      info: Short informational string to include in the generated header
        (e.g., “Built-in defaults” or a provenance note).
      file_label: Value to use for the `file` field in the generated header
        (defaults to “topmark.toml”).

    Returns:
      A dictionary of header fields (e.g.,
        `{"file": ..., "version": ..., "info": ..., "license": ..., "copyright": ...}`).
      Only present keys are included; when a field is missing in `pyproject.toml`,
      it is omitted from the result.

    Notes:
      - `version` is populated from the running TopMark’s version.
      - Missing metadata in `pyproject.toml` does not raise; it is simply omitted.
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


class OutputFormat(Enum):
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
    """Decide whether color output should be enabled.

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
def classify_outcome(r: "ProcessingContext") -> tuple[str, str, Callable[[str], str]]:
    """Classify a :class:`ProcessingContext` for summary rendering.

    Args:
      r: Processing context for a single file.

    Returns:
      A tuple ``(key, label, color_fn)`` where ``key`` is a stable identifier,
      ``label`` is a short human-readable description, and ``color_fn`` is a
      callable (from ``yachalk``) used to colorize the label in human output.
    """
    # Import locally to avoid any import cycles at module import time.
    from topmark.pipeline.context import (
        ComparisonStatus,
        FileStatus,
        GenerationStatus,
        HeaderStatus,
    )

    if r.status.file is not FileStatus.RESOLVED:
        return (f"file:{r.status.file.name}", f"file {r.status.file.value}", r.status.file.color)
    if r.status.header is HeaderStatus.MISSING:
        return ("insert", "would insert header", chalk.green)
    if r.status.header is HeaderStatus.DETECTED:
        if r.status.comparison is ComparisonStatus.UNCHANGED:
            return ("ok", "up-to-date", chalk.green)
        if r.status.comparison is ComparisonStatus.CHANGED:
            return ("replace", "would replace header", chalk.yellow_bright)
        return ("compare_error", "cannot compare", chalk.red)
    if r.status.header in {HeaderStatus.EMPTY, HeaderStatus.MALFORMED}:
        return (
            f"header:{r.status.header.name.lower()}",
            f"header {r.status.header.value}",
            r.status.header.color,
        )
    if r.status.generation is GenerationStatus.NO_FIELDS:
        return ("no_fields", "no fields to render", chalk.yellow)
    return ("other", "other", chalk.gray)


def count_by_outcome(
    results: list["ProcessingContext"],
) -> dict[str, tuple[int, str, Callable[[str], str]]]:
    """Count results per classification key.

    Keeps the first-seen label and color for each key.

    Args:
      results: A list of processing contexts.

    Returns:
      A mapping from outcome key to a tuple ``(count, label, color_fn)``.
    """
    counts: dict[str, tuple[int, str, Callable[[str], str]]] = {}
    for r in results:
        key, label, color = classify_outcome(r)
        n, _, _ = counts.get(key, (0, label, color))
        counts[key] = (n + 1, label, color)
    return counts
