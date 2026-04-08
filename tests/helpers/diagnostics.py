# topmark:header:start
#
#   project      : TopMark
#   file         : diagnostics.py
#   file_relpath : tests/helpers/diagnostics.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared assertion helpers for diagnostics and captured warnings.

This module contains small reusable helpers for tests that need to compare
messages recorded in `MutableConfig.diagnostics` with warnings captured via
pytest's `caplog` fixture.

Keeping these helpers in a dedicated module avoids duplicating message-extract
and assertion boilerplate across TOML-, config-, and API-layer tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

    from topmark.config.model import MutableConfig

# ---- Shared diagnostics-related helpers ----


def _diag_messages(draft: MutableConfig) -> list[str]:
    """Return all diagnostic messages currently recorded on `draft`."""
    return [d.message for d in draft.diagnostics]


def _caplog_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return all messages captured in the current pytest log fixture."""
    return [r.message for r in caplog.records]


def assert_warned_and_diagnosed(
    *,
    caplog: pytest.LogCaptureFixture,
    draft: MutableConfig,
    needle: str,
    min_count: int = 1,
) -> None:
    """Assert a warning substring appears in logs and `draft.diagnostics`.

    Args:
        caplog: Pytest log capture fixture.
        draft: Parsed draft config with diagnostics attached.
        needle: Substring expected to appear in warning messages.
        min_count: Minimum number of matching messages expected in *each*
            sink (logs and diagnostics). Defaults to 1.
    """
    caplog_msgs: list[str] = _caplog_messages(caplog)
    diag_msgs: list[str] = _diag_messages(draft)

    log_hits: int = sum(1 for m in caplog_msgs if needle in m)
    diag_hits: int = sum(1 for m in diag_msgs if needle in m)

    assert log_hits >= min_count, (
        f"Expected at least {min_count} log message(s) containing: {needle!r}.\n"
        f"Found: {log_hits}.\nCaptured logs:\n- " + "\n- ".join(caplog_msgs)
    )
    assert diag_hits >= min_count, (
        f"Expected at least {min_count} diagnostic(s) containing: {needle!r}.\n"
        f"Found: {diag_hits}.\nDiagnostics:\n- " + "\n- ".join(diag_msgs)
    )


def assert_not_warned(
    *,
    caplog: pytest.LogCaptureFixture,
    needle: str,
) -> None:
    """Assert that no captured log message contains `needle`."""
    caplog_msgs: list[str] = _caplog_messages(caplog)
    assert not any(needle in m for m in caplog_msgs), (
        f"Did not expect log message containing: {needle!r}.\n"
        f"Captured logs:\n- " + "\n- ".join(caplog_msgs)
    )
