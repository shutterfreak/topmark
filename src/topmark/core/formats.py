# topmark:header:start
#
#   project      : TopMark
#   file         : formats.py
#   file_relpath : src/topmark/core/formats.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared output format definitions used across TopMark frontends.

This module centralizes the `OutputFormat` enum so CLI commands, machine emitters,
and other frontends can agree on the same format vocabulary without introducing `Click`
or console dependencies.

Machine formats (JSON, NDJSON) are intended to be stable and colorless
"""

from __future__ import annotations

from enum import Enum


class OutputFormat(str, Enum):
    """Output format for CLI rendering.

    Attributes:
        TEXT: Human-friendly text output; may include ANSI color if enabled.
        MARKDOWN: A Markdown document.
        JSON: A single JSON document (machine-readable). See the
            `Machine output` developer docs for the schema.
        NDJSON: One JSON object per line (newline-delimited JSON; machine-readable).

    Notes:
        - Machine formats (``JSON`` and ``NDJSON``) must not include ANSI color
          or diffs.
        - Use with [`topmark.cli.cli_types.EnumChoiceParam`][] to parse
          ``--output-format`` from Click.
    """

    # Human formats:
    TEXT = "text"
    MARKDOWN = "markdown"

    # Machine formats:
    JSON = "json"
    NDJSON = "ndjson"


def is_machine_format(fmt: OutputFormat | None) -> bool:
    """Return True for formats intended for machine consumption.

    Args:
        fmt: the output format to be checked.

    Returns:
        `True` if the format provided is a machine format, else `False`.
    """
    return fmt in {OutputFormat.JSON, OutputFormat.NDJSON}
