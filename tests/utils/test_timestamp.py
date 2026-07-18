# topmark:header:start
#
#   project      : TopMark
#   file         : test_timestamp.py
#   file_relpath : tests/utils/test_timestamp.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for UTC timestamp sources and formatting."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import topmark.utils.timestamp as timestamp_utils
from topmark.utils.timestamp import format_gnu_diff_timestamp
from topmark.utils.timestamp import format_iso8601_timestamp
from topmark.utils.timestamp import get_path_mtime_utc
from topmark.utils.timestamp import get_utc_now

if TYPE_CHECKING:
    from collections.abc import Callable


def test_get_utc_now_returns_aware_current_utc_datetime() -> None:
    """The current-time source should be bounded, aware, and explicitly UTC."""
    before: datetime = datetime.now(timezone.utc)
    value: datetime = get_utc_now()
    after: datetime = datetime.now(timezone.utc)

    assert before <= value <= after
    assert value.tzinfo is timezone.utc


def test_get_path_mtime_utc_returns_exact_aware_utc_datetime(
    tmp_path: Path,
) -> None:
    """Filesystem epoch timestamps should be converted independently of local time."""
    path: Path = tmp_path / "source.py"
    path.write_text("", encoding="utf-8")
    expected: datetime = datetime(
        2024,
        2,
        3,
        4,
        5,
        6,
        tzinfo=timezone.utc,
    )
    os.utime(path, (expected.timestamp(), expected.timestamp()))

    value: datetime = get_path_mtime_utc(path=path)

    assert value == expected
    assert value.tzinfo is timezone.utc


def test_get_path_mtime_utc_logs_and_uses_current_time_once_on_stat_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An mtime lookup failure should warn and use the clock fallback exactly once."""
    path: Path = tmp_path / "missing.py"
    fallback: datetime = datetime(
        2025,
        6,
        7,
        8,
        9,
        10,
        tzinfo=timezone.utc,
    )
    calls: list[None] = []

    def fixed_now() -> datetime:
        calls.append(None)
        return fallback

    monkeypatch.setattr(
        timestamp_utils,
        "get_utc_now",
        fixed_now,
    )
    caplog.set_level(logging.WARNING)

    assert get_path_mtime_utc(path=path) == fallback
    assert calls == [None]
    assert str(path) in caplog.text
    assert "Using 'now'" in caplog.text


def test_get_path_mtime_utc_propagates_unexpected_stat_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-filesystem failures should not be indiscriminately swallowed."""

    def unexpected_failure(
        self: Path,
        *,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        Path,
        "stat",
        unexpected_failure,
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        get_path_mtime_utc(path=tmp_path / "source.py")


@pytest.mark.parametrize(
    ("formatter", "expected"),
    [
        pytest.param(
            format_iso8601_timestamp,
            "2024-01-02T00:34:05.123456+00:00",
            id="iso-8601",
        ),
        pytest.param(
            format_gnu_diff_timestamp,
            "2024-01-02 00:34:05 +0000",
            id="gnu-diff",
        ),
    ],
)
def test_timestamp_formatters_convert_aware_offsets_to_utc(
    formatter: Callable[..., str],
    expected: str,
) -> None:
    """Explicit aware values should have deterministic UTC output."""
    dt: datetime = datetime(
        2024,
        1,
        2,
        6,
        4,
        5,
        123456,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    assert formatter(dt=dt) == expected


@pytest.mark.parametrize(
    ("formatter", "expected"),
    [
        pytest.param(
            format_iso8601_timestamp,
            "2026-02-21T19:16:49.056550+00:00",
            id="iso-8601",
        ),
        pytest.param(
            format_gnu_diff_timestamp,
            "2026-02-21 19:16:49 +0000",
            id="gnu-diff",
        ),
    ],
)
def test_timestamp_formatters_obtain_current_utc_time_once(
    formatter: Callable[..., str],
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitted values should use the centralized current-time source once."""
    fixed: datetime = datetime(
        2026,
        2,
        21,
        19,
        16,
        49,
        56550,
        tzinfo=timezone.utc,
    )
    calls: list[None] = []

    def fixed_now() -> datetime:
        calls.append(None)
        return fixed

    monkeypatch.setattr(
        timestamp_utils,
        "get_utc_now",
        fixed_now,
    )

    assert formatter() == expected
    assert calls == [None]
