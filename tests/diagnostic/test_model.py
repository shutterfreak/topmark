# topmark:header:start
#
#   project      : TopMark
#   file         : test_model.py
#   file_relpath : tests/diagnostic/test_model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Diagnostic model contract tests."""

from __future__ import annotations

from typing import cast

import pytest

from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import MutableDiagnosticLog


def test_diagnostic_stats_get_rejects_unknown_level() -> None:
    """DiagnosticStats.get should reject unsupported level-like values."""
    stats = DiagnosticStats(n_info=1, n_warning=2, n_error=3)

    with pytest.raises(ValueError, match="Unsupported diagnostic level"):
        stats.get(cast("DiagnosticLevel", "notice"))


def test_diagnostic_stats_triage_summary_respects_error_threshold() -> None:
    """Error-threshold summaries should stop after errors."""
    stats = DiagnosticStats(n_info=3, n_warning=2, n_error=1)

    assert stats.triage_summary(DiagnosticLevel.ERROR) == "1 error"


def test_diagnostic_stats_triage_summary_respects_warning_threshold() -> None:
    """Warning-threshold summaries should include errors and warnings only."""
    stats = DiagnosticStats(n_info=3, n_warning=2, n_error=1)

    assert stats.triage_summary(DiagnosticLevel.WARNING) == "1 error, 2 warnings"


def test_diagnostic_stats_triage_summary_handles_warning_only_threshold() -> None:
    """Warning-threshold summaries should work when no errors are present."""
    stats = DiagnosticStats(n_info=3, n_warning=2, n_error=0)

    assert stats.triage_summary(DiagnosticLevel.WARNING) == "2 warnings"


def test_diagnostic_stats_triage_summary_returns_empty_string_without_matches() -> None:
    """Empty stats should render an empty triage summary."""
    stats = DiagnosticStats(n_info=0, n_warning=0, n_error=0)

    assert stats.triage_summary() == ""


def test_mutable_diagnostic_log_has_info_reflects_info_entries() -> None:
    """MutableDiagnosticLog.has_info should track whether info entries exist."""
    log = MutableDiagnosticLog()

    assert not log.has_info

    log.add(
        Diagnostic(
            level=DiagnosticLevel.INFO,
            message="Detail",
        )
    )

    assert log.has_info
