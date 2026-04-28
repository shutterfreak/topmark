# topmark:header:start
#
#   project      : TopMark
#   file         : test_discovery.py
#   file_relpath : tests/resolver/test_discovery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for discovery-level probe explanations.

These tests exercise `probe_explicit_file_selection()` directly. They keep
file discovery explanations separate from file-type resolution probe tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.config import make_config
from topmark.resolution.discovery import FileSelectionProbeResult
from topmark.resolution.discovery import FileSelectionReason
from topmark.resolution.discovery import FileSelectionStatus
from topmark.resolution.files import probe_explicit_file_selection

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config


def test_probe_explicit_file_selection_omits_selected_file(tmp_path: Path) -> None:
    """Explicit inputs already selected for probing should not be reported."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: Config = make_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[file],
    )

    assert results == ()


def test_probe_explicit_file_selection_reports_filtered_file(tmp_path: Path) -> None:
    """Existing files omitted from selected files should be reported as filtered."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: Config = make_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.EXCLUDED_BY_DISCOVERY_FILTER


def test_probe_explicit_file_selection_reports_missing_file(tmp_path: Path) -> None:
    """Missing explicit inputs should be reported as not found."""
    file: Path = tmp_path / "missing.py"
    cfg: Config = make_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.NOT_FOUND
    assert result.reason == FileSelectionReason.NOT_FOUND


def test_probe_explicit_file_selection_reports_directory(tmp_path: Path) -> None:
    """Explicit directories omitted from selected files should be reported as not files."""
    directory: Path = tmp_path / "data"
    directory.mkdir()
    cfg: Config = make_config(files=[str(directory)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == directory
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.NOT_A_FILE
