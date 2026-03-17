# topmark:header:start
#
#   project      : TopMark
#   file         : timestamp.py
#   file_relpath : src/topmark/utils/timestamp.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Timestamp helpers used across TopMark.

This module centralizes timestamp *sources* and *string formatting* so that:

- internal timestamps are consistently represented in UTC;
- machine outputs can use ISO-8601 strings; and
- unified diff headers can use GNU diff / git-style timestamps.

Naming convention:
- `get_*` functions return `datetime` objects (UTC).
- `format_*` functions return strings in a specific, documented format.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)


def get_utc_now() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def get_path_mtime_utc(*, path: Path) -> datetime:
    """Return the file's modification time as an aware UTC datetime.

    Falls back to `get_utc_now()` when the mtime cannot be read.

    Args:
        path: Path to the file.

    Returns:
        The file's `st_mtime` as an aware UTC datetime, or `get_utc_now()` on failure.
    """
    try:
        ts: float = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except OSError as e:
        logger.warning("Could not access mtime for %s: %s. Using 'now'.", path, e)
        return get_utc_now()


def format_iso8601_timestamp(*, dt: datetime | None = None) -> str:
    """Return an ISO-8601 timestamp string in UTC.

    If `dt` is not set, uses the current time.

    All timestamps are converted to UTC offset.

    Args:
        dt: An optional `datetime` (use now if not specified).

    Returns:
        ISO-8601 timestamp string in UTC (e.g. `2026-02-21T19:16:49.056550+00:00`).
    """
    value: datetime = get_utc_now() if dt is None else dt.astimezone(timezone.utc)
    return value.isoformat()


_GNU_DIFF_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S %z"


def format_gnu_diff_timestamp(*, dt: datetime | None = None) -> str:
    """Return a GNU diff / git-style timestamp string in UTC.

    This format is suitable for unified diff header date fields.

    If `dt` is not set, uses the current time.

    All timestamps are converted to UTC offset.

    Args:
        dt: An optional `datetime` (use now if not specified).

    Returns:
        A string representing the GNU diff timestamp (e.g., '2026-02-21 19:16:49 +0000').
    """
    value: datetime = get_utc_now() if dt is None else dt.astimezone(timezone.utc)
    return value.strftime(_GNU_DIFF_TIMESTAMP_FMT)
