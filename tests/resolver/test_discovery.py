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

from tests.helpers.config import make_frozen_config
from topmark.config.types import PatternGroup
from topmark.resolution.discovery import FileSelectionProbeResult
from topmark.resolution.discovery import FileSelectionReason
from topmark.resolution.discovery import FileSelectionStatus
from topmark.resolution.files import probe_explicit_file_selection

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig


def test_file_selection_status_and_reason_values_are_stable_machine_strings() -> None:
    """Discovery probe enums should expose stable string values."""
    assert FileSelectionStatus.SELECTED.value == "selected"
    assert FileSelectionStatus.FILTERED.value == "filtered"
    assert FileSelectionStatus.NOT_FOUND.value == "not_found"

    assert FileSelectionReason.SELECTED.value == "selected"
    assert FileSelectionReason.EXCLUDED_BY_PATH_FILTER.value == "excluded_by_path_filter"
    assert FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER.value == "excluded_by_file_type_filter"
    assert FileSelectionReason.EXCLUDED_BY_DISCOVERY_FILTER.value == "excluded_by_discovery_filter"
    assert FileSelectionReason.NOT_A_FILE.value == "not_a_file"
    assert FileSelectionReason.NOT_FOUND.value == "not_found"


def test_probe_explicit_file_selection_omits_selected_file(tmp_path: Path) -> None:
    """Explicit inputs already selected for probing should not be reported."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[file],
    )

    assert results == ()


def test_probe_explicit_file_selection_reports_generic_filtered_file(tmp_path: Path) -> None:
    """Existing files with no clear filter cause should use generic filtered reason."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.EXCLUDED_BY_DISCOVERY_FILTER


def test_probe_explicit_file_selection_reports_path_filtered_file(tmp_path: Path) -> None:
    """Existing files excluded by path filters should report path-filter reason."""
    ignored_dir: Path = tmp_path / "ignored"
    ignored_dir.mkdir()
    file: Path = ignored_dir / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(
        files=[str(file)],
        exclude_patterns=["ignored/"],
    )

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.EXCLUDED_BY_PATH_FILTER


def test_probe_explicit_file_selection_reports_include_filtered_file(
    tmp_path: Path,
) -> None:
    """Existing files outside include filters should report path-filter reason."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(
        files=[str(file)],
        include_pattern_groups=[
            PatternGroup(
                patterns=("docs/**/*.md",),
                base=tmp_path.resolve(),
            ),
        ],
    )

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.EXCLUDED_BY_PATH_FILTER


def test_probe_explicit_file_selection_reports_file_type_filtered_file(tmp_path: Path) -> None:
    """Existing files excluded by file-type filters should report file-type reason."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(
        files=[str(file)],
        include_file_types={"markdown"},
    )

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER


def test_probe_explicit_file_selection_reports_exclude_file_type_filtered_file(
    tmp_path: Path,
) -> None:
    """Existing files excluded by exclude_file_types should report file-type reason."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    cfg: FrozenConfig = make_frozen_config(
        files=[str(file)],
        exclude_file_types={"python"},
    )

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER


def test_probe_explicit_file_selection_reports_missing_file(tmp_path: Path) -> None:
    """Missing explicit inputs should be reported as not found."""
    file: Path = tmp_path / "missing.py"
    cfg: FrozenConfig = make_frozen_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == file
    assert result.status == FileSelectionStatus.NOT_FOUND
    assert result.reason == FileSelectionReason.NOT_FOUND


def test_probe_explicit_file_selection_skips_reported_missing_literal(
    tmp_path: Path,
) -> None:
    """Missing explicit inputs already reported by resolution should be skipped."""
    file: Path = tmp_path / "missing.py"
    cfg: FrozenConfig = make_frozen_config(files=[str(file)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
        missing_literals=[file],
    )

    assert results == ()


def test_probe_explicit_file_selection_reports_directory(tmp_path: Path) -> None:
    """Explicit directories omitted from selected files should be reported as not files."""
    directory: Path = tmp_path / "data"
    directory.mkdir()
    cfg: FrozenConfig = make_frozen_config(files=[str(directory)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    result: FileSelectionProbeResult = results[0]
    assert result.path == directory
    assert result.status == FileSelectionStatus.FILTERED
    assert result.reason == FileSelectionReason.NOT_A_FILE


def test_probe_explicit_file_selection_omits_directory_with_selected_descendant(
    tmp_path: Path,
) -> None:
    """Explicit directories with selected descendants are expansion sources."""
    directory: Path = tmp_path / "data"
    directory.mkdir()
    file: Path = directory / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(files=[str(directory)])

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[file],
    )

    assert results == ()


def test_explicit_directory_with_selected_sibling_is_reported_not_a_file(
    tmp_path: Path,
) -> None:
    """Explicit directories should not be hidden by selected non-descendants."""
    directory: Path = tmp_path / "data"
    directory.mkdir()
    sibling: Path = tmp_path / "sibling.py"
    sibling.write_text("x", encoding="utf-8")

    cfg: FrozenConfig = make_frozen_config(files=[str(directory)])
    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[sibling],
    )

    assert len(results) == 1
    assert results[0].path == directory
    assert results[0].status == FileSelectionStatus.FILTERED
    assert results[0].reason == FileSelectionReason.NOT_A_FILE


def test_probe_explicit_file_selection_reports_excluded_file_type(
    tmp_path: Path,
) -> None:
    """Explicit files matching excluded file types should report file-type reason."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(
        files=[str(file)],
        exclude_file_types={"python"},
    )

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    assert results[0].path == file
    assert results[0].status == FileSelectionStatus.FILTERED
    assert results[0].reason == FileSelectionReason.EXCLUDED_BY_FILE_TYPE_FILTER


def test_probe_explicit_file_selection_keeps_non_matching_exclude_file_type_reason_generic(
    tmp_path: Path,
) -> None:
    """Exclude file-type filters should not explain non-matching files."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")
    cfg: FrozenConfig = make_frozen_config(
        files=[str(file)],
        exclude_file_types={"markdown"},
    )

    results: tuple[FileSelectionProbeResult, ...] = probe_explicit_file_selection(
        cfg,
        selected_files=[],
    )

    assert len(results) == 1
    assert results[0].path == file
    assert results[0].status == FileSelectionStatus.FILTERED
    assert results[0].reason == FileSelectionReason.EXCLUDED_BY_DISCOVERY_FILTER
