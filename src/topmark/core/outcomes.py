# topmark:header:start
#
#   project      : TopMark
#   file         : outcomes.py
#   file_relpath : src/topmark/core/outcomes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable outcome primitives shared by API, pipeline, and presentation layers.

This module is intentionally low-level: it defines the public outcome enum,
its deterministic display/aggregation order, and the fallback reason text used
when no more specific bucket reason is available.

Keeping these primitives in `topmark.core` avoids import cycles between the
pipeline outcome classifier and the public API DTO layer. Higher-level modules
may re-export or reference these values, but this module must remain free of
pipeline, API-command, CLI, and presentation imports.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

NO_REASON_PROVIDED: Final[str] = "(no reason provided)"
"""Outcome reason when no reason provided."""


class Outcome(str, Enum):
    """Stable per-file outcome bucket used by the public API.

    Values mirror the high-level outcome categories exposed by the CLI and API.
    Consumers should prefer `Outcome` (and `Outcome.value`) for programmatic
    decisions rather than relying on human-facing labels.
    """

    PENDING = "pending"
    ERROR = "error"
    # File skipped (not processed)
    SKIPPED = "skipped"
    # File already complies
    UNCHANGED = "unchanged"
    # A change was detected but not applied
    WOULD_CHANGE = "would change"
    WOULD_INSERT = "would insert"
    WOULD_UPDATE = "would update"
    WOULD_STRIP = "would strip"
    # Changes have been applied
    CHANGED = "changed"
    INSERTED = "inserted"
    UPDATED = "updated"
    STRIPPED = "stripped"


OUTCOME_ORDER: Final[tuple[Outcome, ...]] = (
    Outcome.PENDING,
    Outcome.SKIPPED,
    Outcome.UNCHANGED,
    Outcome.WOULD_CHANGE,
    Outcome.WOULD_INSERT,
    Outcome.WOULD_UPDATE,
    Outcome.WOULD_STRIP,
    Outcome.CHANGED,
    Outcome.INSERTED,
    Outcome.UPDATED,
    Outcome.STRIPPED,
    Outcome.ERROR,
)
