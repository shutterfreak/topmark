# topmark:header:start
#
#   project      : TopMark
#   file         : presentation.py
#   file_relpath : src/topmark/core/presentation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Semantic presentation primitives for human-facing rendering.

This module defines a small, stable vocabulary of *semantic* style roles and a lightweight enum base
that can carry such roles.

The key goal is to keep **core** code free of any concrete presentation backend (ANSI, Rich,
yachalk, etc.) while still allowing it to attach meaningful styling intent to domain concepts.

Core modules should depend only on:

- `StyleRole`: semantic roles such as ERROR/WARNING/OK/CHANGED.
- `StyledStrEnum`: an enum whose `.value` is a plain `str` plus an attached semantic role via
  `.role`.

The CLI (or any other renderer) is responsible for mapping `StyleRole` values to actual presentation
(color, bold, icons, etc.).

Design notes:
    * Keep the `StyleRole` vocabulary small and stable.
    * Prefer mapping richer domain concepts onto `StyleRole` rather than introducing per-module
      style enums.
    * Keep enum values as plain strings for deterministic serialization.
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import Self


class StyleRole(str, Enum):
    """Semantic styling role for human-facing rendering.

    `StyleRole` expresses *meaning* (severity, outcome, emphasis) without prescribing a concrete
    presentation (color/bold). The CLI (or any other renderer) is responsible for mapping roles to
    an actual style backend.

    Notes:
        Keep this vocabulary small and stable. Prefer mapping richer domain concepts (e.g.,
        `DiagnosticLevel`, `Cluster`, `*Status`) onto these roles rather than introducing per-module
        style enums.
    """

    # Generic severities
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    # Generic outcomes / states
    OK = "ok"
    MUTED = "muted"
    EMPHASIS = "emphasis"

    # Change semantics (often used by check/strip pipelines)
    UNCHANGED = "unchanged"
    WOULD_CHANGE = "would_change"
    CHANGED = "changed"

    # Other common buckets
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    BLOCKED_POLICY = "blocked_policy"
    PENDING = "pending"

    # Unified diffs
    DIFF_HEADER = "diff_header"
    DIFF_META = "diff_meta"
    DIFF_ADD = "diff_add"
    DIFF_DEL = "diff_del"
    DIFF_LINE_NO = "diff_line_no"

    # Other style roles
    HEADING_TITLE = "heading_title"
    MARKER_LINE = "marker_line"
    CONFIG_FILE = "config_file"

    # No style
    NO_STYLE = "no_style"


# --- Semantic string enum for backend-agnostic styling -------------------------------------------


class StyledStrEnum(str, Enum):
    """Enum whose value is a display string and that carries a semantic `StyleRole`.

    This is a backend-agnostic enum helper: core code attaches semantic meaning (`StyleRole`)
    without depending on any renderer. Core code can attach semantic meaning (e.g.,
    `ERROR`/`WARNING`/`OK`) without importing terminal styling libraries. Renderers (CLI, rich,
    etc.) can map `StyleRole` to concrete presentation.

    Notes:
        Keep the enum value (`.value`) as a plain string for stable serialization.
        The semantic role is exposed via `.role`.
    """

    _role: StyleRole

    def __new__(cls, text: str, role: StyleRole) -> Self:
        """Create a `StyledStrEnum` instance.

        Args:
            text: The text value.
            role: The style role.

        Returns:
            The newly created enum member.
        """
        obj: StyledStrEnum = str.__new__(cls, text)
        obj._value_ = text
        obj._role = role
        return obj

    @property
    def role(self) -> StyleRole:
        """Return the semantic `StyleRole` attached to this enum member."""
        return self._role
