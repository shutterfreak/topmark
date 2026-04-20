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
flattened config-validation diagnostic messages with warnings captured via
pytest's `caplog` fixture.

Keeping these helpers in a dedicated module avoids duplicating message-extract
and assertion boilerplate across TOML-, config-, and API-layer tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final
from typing import Literal
from typing import TypeAlias

from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import DiagnosticStats

if TYPE_CHECKING:
    import pytest

    from topmark.config.model import MutableConfig
    from topmark.config.validation import FrozenValidationLogs
    from topmark.config.validation import ValidationLogs


NonEmptyExpectation: TypeAlias = Literal[">0"]
NON_EMPTY: Final[NonEmptyExpectation] = ">0"
DiagnosticCountExpectation: TypeAlias = int | NonEmptyExpectation | None


# ---- Shared diagnostics-related helpers ----


def _diag_messages(draft: MutableConfig) -> list[str]:
    """Return flattened diagnostic messages currently derivable from `draft`."""
    return [d.message for d in draft.validation_logs.flattened()]


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
    """Assert a warning substring appears in logs and flattened draft diagnostics.

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


# ---- Diagnostics stats helpers ----


def _assert_count_expectation(
    *,
    label: str,
    actual_total: int,
    expected: DiagnosticCountExpectation,
) -> None:
    """Assert one count expectation shared by diagnostics test helpers.

    Supported expectations:
        - `None`: skip this assertion.
        - a non-negative integer: require the observed count to equal that value.
        - `NON_EMPTY`: require the observed count to be greater than zero.

    Args:
        label: Human-readable label used in assertion messages.
        actual_total: Observed count.
        expected: Expected count behavior.

    Raises:
        AssertionError: If the observed count does not satisfy the expectation.
        ValueError: If `expected` is not `None`, a non-negative integer, or
            `NON_EMPTY`.
    """
    if expected is None:
        return
    if isinstance(expected, int) and expected >= 0:
        assert actual_total == expected, (
            f"Expected {expected} diagnostics for {label}, found {actual_total}"
        )
        return
    if expected == NON_EMPTY:
        assert actual_total > 0, f"Expected >0 diagnostics for {label}, found {actual_total}"
        return
    raise ValueError(
        f"expected must be None, a non-negative integer, or {NON_EMPTY!r} for {label} assertions"
    )


def _assert_diagnostic_level_stats(
    *,
    level: DiagnosticLevel,
    stats: DiagnosticStats,
    expected: DiagnosticCountExpectation,
) -> None:
    """Assert one diagnostic-level count expectation."""
    _assert_count_expectation(
        label=f"diagnostic level {level.value!r}",
        actual_total=stats.get(level),
        expected=expected,
    )


def _assert_diagnostic_total_stats(
    *,
    stats: DiagnosticStats,
    expected: DiagnosticCountExpectation,
) -> None:
    """Assert one total-diagnostic count expectation."""
    _assert_count_expectation(
        label="diagnostic totals",
        actual_total=stats.total,
        expected=expected,
    )


def assert_diagnostic_level_stats(
    *,
    stats: DiagnosticStats,
    expected_info: DiagnosticCountExpectation = None,
    expected_warning: DiagnosticCountExpectation = None,
    expected_error: DiagnosticCountExpectation = None,
    expected_total: DiagnosticCountExpectation = None,
) -> None:
    """Assert flat diagnostic counts by severity level and/or total.

    Supported expectations per field:
        - `None`: skip the field.
        - a non-negative integer: require this exact count for the field.
        - `NON_EMPTY`: require the field to contain at least one diagnostic.

    Args:
        stats: Aggregated diagnostic stats to inspect.
        expected_info: Expectation for info diagnostics.
        expected_warning: Expectation for warning diagnostics.
        expected_error: Expectation for error diagnostics.
        expected_total: Expectation for the total diagnostic count.
    """
    if (
        expected_total is None
        and expected_info is None
        and expected_warning is None
        and expected_error is None
    ):
        return

    if expected_info is not None:
        _assert_diagnostic_level_stats(
            level=DiagnosticLevel.INFO,
            stats=stats,
            expected=expected_info,
        )

    if expected_warning is not None:
        _assert_diagnostic_level_stats(
            level=DiagnosticLevel.WARNING,
            stats=stats,
            expected=expected_warning,
        )

    if expected_error is not None:
        _assert_diagnostic_level_stats(
            level=DiagnosticLevel.ERROR,
            stats=stats,
            expected=expected_error,
        )

    if expected_total is not None:
        _assert_diagnostic_total_stats(
            stats=stats,
            expected=expected_total,
        )


# ---- Validation stage diagnostics stats helpers ----


def _assert_stage_total(
    *,
    stage_name: str,
    actual_total: int,
    expected: DiagnosticCountExpectation,
) -> None:
    """Assert one validation-stage total expectation."""
    _assert_count_expectation(
        label=f"validation stage {stage_name!r}",
        actual_total=actual_total,
        expected=expected,
    )


def assert_validation_stage_totals(
    logs: ValidationLogs | FrozenValidationLogs,
    *,
    toml: DiagnosticCountExpectation = None,
    config: DiagnosticCountExpectation = None,
    runtime: DiagnosticCountExpectation = None,
) -> None:
    """Assert total diagnostic counts for staged validation logs.

    This helper is intentionally small and focused on totals for staged
    validation logs. It supports three expectation modes per stage:

    - `None`: do not check this stage.
    - a non-negative integer: require this exact count for the stage.
    - `NON_EMPTY`: assert the stage contains at least one diagnostic.

    Args:
        logs: Mutable or frozen staged validation logs to inspect.
        toml: Expectation for the TOML-source stage.
        config: Expectation for the merged-config stage.
        runtime: Expectation for the runtime-applicability stage.
    """
    _assert_stage_total(
        stage_name="toml_source",
        actual_total=logs.toml_source.stats().total,
        expected=toml,
    )
    _assert_stage_total(
        stage_name="merged_config",
        actual_total=logs.merged_config.stats().total,
        expected=config,
    )
    _assert_stage_total(
        stage_name="runtime_applicability",
        actual_total=logs.runtime_applicability.stats().total,
        expected=runtime,
    )
