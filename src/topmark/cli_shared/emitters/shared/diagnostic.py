# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostic.py
#   file_relpath : src/topmark/cli_shared/emitters/shared/diagnostic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared diagnostic preparation for human-facing CLI emitters.

This module contains Click-free helpers and small data shapes that convert
internal diagnostic objects into a presentation-friendly form for human output
formats (DEFAULT / MARKDOWN).

Scope:
    - Prepare stable, minimal "human" diagnostics (counts + rendered lines).
    - Avoid depending on machine-format schemas/payloads: those belong under
      `topmark/**/machine/*` and are used by JSON/NDJSON emitters.

Design:
    - The resulting shapes (`HumanDiagnosticCounts`, `HumanDiagnosticLine`) are
      used by both ANSI (DEFAULT) and Markdown emitters.
    - Helpers here do not print or perform Click I/O. They may normalize text,
      map levels, and count diagnostics.

Notes:
    If you need to change the *machine* diagnostic schema, do so in the
    [`topmark.diagnostic.machine`][topmark.diagnostic.machine] package instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.diagnostic.model import Diagnostic


@dataclass(frozen=True, slots=True)
class HumanDiagnosticLine:
    """A human-facing diagnostic line (Click-free).

    This is intentionally *not* a machine schema type. It exists so DEFAULT and
    MARKDOWN output can share a stable presentation model without depending on
    machine-format payload schemas.

    Attributes:
        level: Diagnostic level as a lowercase string (e.g. "info", "warning", "error").
        message: Diagnostic message text.
    """

    level: str
    message: str


@dataclass(frozen=True, slots=True)
class HumanDiagnosticCounts:
    """Aggregated per-level counts for human-facing config output.

    Attributes:
        info: Number of info-level diagnostics.
        warning: Number of warning-level diagnostics.
        error: Number of error-level diagnostics.
    """

    info: int
    warning: int
    error: int


def _level_to_str(level_obj: object) -> str:
    """Normalize diagnostic level objects to a stable string.

    Accepts either:
    - strings
    - Enum-like values with `.value`
    - anything else (falls back to `str()`)

    Args:
        level_obj: Level-like object.

    Returns:
        Normalized string level.
    """
    if isinstance(level_obj, str):
        return level_obj
    value: object = getattr(level_obj, "value", None)
    if isinstance(value, str):
        return value
    return str(level_obj)


def prepare_human_diagnostics(
    diagnostics: Iterable[Diagnostic],
) -> tuple[HumanDiagnosticCounts, list[HumanDiagnosticLine]]:
    """Convert internal diagnostics into human-facing counts and lines.

    Args:
        diagnostics: Iterable of internal Diagnostic objects.

    Returns:
        (counts, lines) tuple.
    """
    info = 0
    warning = 0
    error = 0
    lines: list[HumanDiagnosticLine] = []

    for d in diagnostics:
        level: str = _level_to_str(getattr(d, "level", "")).lower()
        msg: str = str(getattr(d, "message", ""))

        if level == "error":
            error += 1
        elif level == "warning":
            warning += 1
        else:
            # Treat unknown levels as "info" for human output stability
            info += 1
            if not level:
                level = "info"

        lines.append(HumanDiagnosticLine(level=level, message=msg))

    return HumanDiagnosticCounts(info=info, warning=warning, error=error), lines
