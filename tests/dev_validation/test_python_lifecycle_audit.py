# topmark:header:start
#
#   project      : TopMark
#   file         : test_python_lifecycle_audit.py
#   file_relpath : tests/dev_validation/test_python_lifecycle_audit.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for lifecycle-audit source parsing and issue decisions."""

from __future__ import annotations

from datetime import date

from tools.ci.audit_python_lifecycle import Decision
from tools.ci.audit_python_lifecycle import Status
from tools.ci.audit_python_lifecycle import decisions
from tools.ci.audit_python_lifecycle import parse_rcs
from tools.ci.audit_python_lifecycle import parse_status


def test_parser_ignores_unreleased_series() -> None:
    """Feature and future rows are not final releases."""
    source = (
        "<tr><td>3.16</td><td></td><td>feature</td><td>2027-10-01</td><td></td></tr>"
        "<tr><td>3.15</td><td></td><td>bugfix</td><td>2026-10-09</td><td>2031-10</td></tr>"
    )
    assert parse_status(source, date(2026, 10, 10)) == (
        Status("3.15", "bugfix", "2026-10-09", "2031-10"),
    )


def test_rc_and_final_share_one_marker() -> None:
    """An RC issue becomes the final-release issue for the same series."""
    rc: Decision = decisions(">=3.10,<3.16", "", (), {"3.16": "3.16.0rc2"})[0]
    final: Decision = decisions(
        ">=3.10,<3.16", "", (Status("3.16", "bugfix", "2027-10-01", "2032-10"),), {}
    )[0]
    assert rc.marker == final.marker == "topmark-python-lifecycle:release-3.16"
    assert "prepare" in rc.title and "final release" in final.title


def test_rc_parser_keeps_newest_candidate() -> None:
    """Only RC releases, not beta releases, are selected."""
    assert parse_rcs('<a href="3.16.0rc1/"><a href="3.16.0rc3/"><a href="3.17.0b1/">') == {
        "3.16": "3.16.0rc3"
    }
