# topmark:header:start
#
#   project      : TopMark
#   file         : events.py
#   file_relpath : src/topmark/pipeline/events.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline events."""

from __future__ import annotations

from enum import Enum


class StreamEventKind(str, Enum):
    """Stable stream event kinds."""

    RUN_STARTED = "run_started"
    FILE_RESULT = "file_result"
    RUN_COMPLETED = "run_completed"
