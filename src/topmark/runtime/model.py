# topmark:header:start
#
#   project      : TopMark
#   file         : model.py
#   file_relpath : src/topmark/runtime/model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Execution-only runtime models.

This package holds values that describe invocation intent for a single
TopMark run. These values do not participate in layered config discovery,
per-path effective config resolution, or file-backed merge semantics.

The initial runtime split introduces `RunOptions` as the authoritative home
for execution-only concerns such as apply mode, stdin handling, output
routing, file-write strategy, and run timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from topmark.utils.timestamp import get_utc_now

if TYPE_CHECKING:
    from datetime import datetime

    from topmark.config.types import FileWriteStrategy
    from topmark.config.types import OutputTarget


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Execution-only options for a single TopMark run.

    This value carries invocation intent that does not participate in layered
    config discovery or per-path effective config resolution.

    Attributes:
        apply_changes: Whether the run should write changes (`True`) or preview
            only (`False`).
        output_target: Where output should be emitted for this run.
        file_write_strategy: How file writes should be performed when
            `output_target` targets files.
        stdin_mode: Whether content is being provided on stdin for this run.
        stdin_filename: Synthetic filename associated with stdin content, used
            when header generation requires a file identity.
        prune_views: Whether heavy views should be trimmed after the run while
            preserving summary-level results.
        started_at: Timestamp captured once for the whole run.
    """

    apply_changes: bool | None = None
    output_target: OutputTarget | None = None
    file_write_strategy: FileWriteStrategy | None = None
    stdin_mode: bool = False
    stdin_filename: str | None = None
    prune_views: bool = True

    started_at: datetime = field(default_factory=get_utc_now)
