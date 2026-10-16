# topmark:header:start
#
#   project      : TopMark
#   file         : test_action_pins.py
#   file_relpath : tests/tools/ci/test_action_pins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the offline GitHub Actions pin audit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.ci import audit_action_pins as pins

if TYPE_CHECKING:
    from pathlib import Path


SHA_ONE: str = "1" * 40
SHA_TWO: str = "2" * 40


def _write_workflow(
    root: Path,
    name: str,
    content: str,
) -> Path:
    """Write a workflow fixture and return its path."""
    path: Path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write raw UTF-8 bytes, preventing Windows text-mode newline expansion.
    path.write_bytes(content.encode("utf-8"))

    return path


def test_audit_ignores_local_actions_and_reports_consistent_external_uses(
    tmp_path: Path,
) -> None:
    """The audit only records external references and accepts matching pins."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        f"  uses: actions/checkout@{SHA_ONE} # v4.2.2\n  uses: ./.github/actions/local\n",
    )

    result: pins.AuditResult = pins.audit_repository(tmp_path)

    assert [use.target for use in result.uses] == [f"actions/checkout@{SHA_ONE}"]
    assert not result.has_failures
    assert "OK:" in pins.format_audit_report(result)


def test_fix_rewrites_lower_version_pin_and_preserves_line_endings(
    tmp_path: Path,
) -> None:
    """Automatic repair selects the uniquely highest version comment."""
    path: Path = _write_workflow(
        tmp_path,
        "ci.yml",
        f"  uses: actions/checkout@{SHA_ONE} # v4.1.0\r\n"
        f"  uses: actions/checkout@{SHA_TWO} # v4.2.0\r\n",
    )
    result: pins.AuditResult = pins.audit_repository(tmp_path)

    rewritten: tuple[pins.ActionUse, ...] = pins.fix_repository(tmp_path, result)

    assert [use.ref for use in rewritten] == [SHA_TWO]
    assert (
        path.read_bytes()
        == (
            f"  uses: actions/checkout@{SHA_TWO} # v4.2.0\r\n"
            f"  uses: actions/checkout@{SHA_TWO} # v4.2.0\r\n"
        ).encode()
    )
    assert not pins.audit_repository(tmp_path).has_failures


def test_ambiguous_divergence_cannot_be_fixed(
    tmp_path: Path,
) -> None:
    """Repair refuses refs without an unambiguous SemVer-like winner."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        f"  uses: actions/checkout@{SHA_ONE} # v4.2.0\n"
        f"  uses: actions/checkout@{SHA_TWO} # v4.2.0\n",
    )
    result: pins.AuditResult = pins.audit_repository(tmp_path)

    assert result.has_failures
    assert not result.can_fix
    with pytest.raises(ValueError, match="Cannot select preferred refs"):
        pins.fix_repository(tmp_path, result)


def test_reports_group_references_by_action_and_file(
    tmp_path: Path,
) -> None:
    """Summary and file reports retain sorted human-readable inventory data."""
    _write_workflow(tmp_path, "a.yml", f"  uses: actions/checkout@{SHA_ONE} # v4.2.2\n")
    _write_workflow(tmp_path, "b.yaml", f"  uses: actions/checkout@{SHA_ONE} # v4.2.2\n")
    result: pins.AuditResult = pins.audit_repository(tmp_path)

    report: str = pins.format_optional_reports(result, "all")

    assert "actions/checkout (2 references)" in report
    assert "across 2 files" in report
    assert ".github/workflows/a.yml" in report
    assert ".github/workflows/b.yaml" in report


def test_main_returns_failure_for_unfixable_divergence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI prints the audit and fails when repair is ambiguous."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        f"  uses: actions/checkout@{SHA_ONE}\n  uses: actions/checkout@{SHA_TWO}\n",
    )

    assert pins.main(["--root", str(tmp_path), "--fix"]) == 1
    assert "Automatic repair skipped" in capsys.readouterr().out
