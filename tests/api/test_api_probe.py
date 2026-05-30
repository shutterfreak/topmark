# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_probe.py
#   file_relpath : tests/api/test_api_probe.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public API tests for `topmark.api.probe()`.

These tests exercise the stable public probe DTOs without importing internal
resolver enums, pipeline contexts, or registry implementation details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api

if TYPE_CHECKING:
    from pathlib import Path


def test_probe_empty_explicit_dir_is_reported_as_filtered(tmp_path: Path) -> None:
    """Empty explicit directories are preserved as filtered probe results."""
    result: api.ProbeRunResult = api.probe(
        [tmp_path],
    )

    assert result.had_errors is False
    assert len(result.files) == 1

    file_result: api.ProbeFileResult = result.files[0]
    assert file_result.path == tmp_path
    assert file_result.status == "filtered"
    assert file_result.reason == "excluded_by_discovery_filter"
    assert file_result.selected_file_type is None
    assert file_result.selected_processor is None
    assert file_result.candidates == ()
    assert result.summary == {"filtered": 1}


def test_probe_python_file_resolves_with_stable_candidate_shape(tmp_path: Path) -> None:
    """A Python file resolves through public probe DTOs and candidate fields."""
    target: Path = tmp_path / "sample.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    result: api.ProbeRunResult = api.probe(
        [target],
        include_file_types=["python"],
    )

    assert result.had_errors is False
    assert len(result.files) == 1

    file_result: api.ProbeFileResult = result.files[0]
    assert isinstance(file_result, api.ProbeFileResult)
    assert file_result.path == target
    assert file_result.status == "resolved"
    assert file_result.reason in {
        "selected_highest_score",
        "selected_by_tie_break",
    }
    assert file_result.selected_file_type == "python"
    assert file_result.selected_processor is not None
    assert file_result.candidates

    selected_candidates: tuple[api.ProbeCandidateInfo, ...] = tuple(
        candidate for candidate in file_result.candidates if candidate.selected
    )
    assert len(selected_candidates) == 1

    selected: api.ProbeCandidateInfo = selected_candidates[0]
    assert isinstance(selected, api.ProbeCandidateInfo)
    assert selected.file_type == "python"
    assert selected.qualified_key
    assert selected.rank >= 1
    assert selected.score >= 0
    assert "extension" in selected.matched_by


def test_probe_unsupported_explicit_file_uses_public_strings(tmp_path: Path) -> None:
    """Unsupported explicit files are reported without leaking internal objects."""
    target: Path = tmp_path / "notes.xyz"
    target.write_text("TopMark notes\n", encoding="utf-8")

    result: api.ProbeRunResult = api.probe(
        [target],
    )

    assert result.had_errors is False
    assert len(result.files) == 1

    file_result: api.ProbeFileResult = result.files[0]
    assert file_result.path == target
    assert file_result.status in {
        "unsupported",
        "filtered",
    }
    assert isinstance(file_result.reason, str)
    assert file_result.selected_file_type is None
    assert file_result.selected_processor is None
    assert file_result.candidates == ()


def test_probe_missing_explicit_path_reports_error(tmp_path: Path) -> None:
    """Missing explicit paths are preserved in probe results and mark the run erroneous."""
    missing: Path = tmp_path / "missing.py"

    result: api.ProbeRunResult = api.probe(
        [missing],
    )

    assert result.had_errors is True
    assert len(result.files) == 1

    file_result: api.ProbeFileResult = result.files[0]
    assert file_result.path == missing

    assert file_result.status == "error"
    assert file_result.reason == "not found"
    assert len(result.files) == 1

    assert file_result.selected_file_type is None
    assert file_result.selected_processor is None
    assert file_result.candidates == ()


def test_probe_explicit_input_filtered_by_file_type_is_reported(tmp_path: Path) -> None:
    """Explicit inputs filtered before probing still receive probe-shaped results."""
    python_file: Path = tmp_path / "sample.py"
    toml_file: Path = tmp_path / "pyproject.toml"
    python_file.write_text("print('hello')\n", encoding="utf-8")
    toml_file.write_text("[tool.example]\nname = 'demo'\n", encoding="utf-8")

    result: api.ProbeRunResult = api.probe(
        [python_file, toml_file],
        include_file_types=["python"],
    )

    by_path: dict[Path, api.ProbeFileResult] = {
        file_result.path: file_result for file_result in result.files
    }

    assert python_file in by_path
    assert toml_file in by_path
    assert by_path[python_file].status == "resolved"
    assert by_path[toml_file].status == "filtered"
    assert by_path[toml_file].reason == "excluded_by_file_type_filter"
    assert by_path[toml_file].candidates == ()
    assert result.summary.get("filtered", 0) >= 1


# Directories that expand to selected files are not probe results.
def test_probe_directory_with_selected_children_omits_directory_result(
    tmp_path: Path,
) -> None:
    """Directories that expand to selected files are not probe results."""
    directory: Path = tmp_path / "project"
    directory.mkdir()

    python_file: Path = directory / "example.py"
    python_file.write_text("print('hello')\n", encoding="utf-8")

    markdown_file: Path = directory / "README.md"
    markdown_file.write_text("# Example\n", encoding="utf-8")

    html_file: Path = directory / "index.html"
    html_file.write_text("<h1>Example</h1>\n", encoding="utf-8")

    result: api.ProbeRunResult = api.probe(
        [directory],
        include_file_types=[
            "python",
            "markdown",
            "toml",
        ],
        exclude_file_types=[
            "html",
        ],
    )

    assert result.had_errors is False

    by_path: dict[Path, api.ProbeFileResult] = {
        file_result.path: file_result for file_result in result.files
    }
    assert set(by_path) == {python_file, markdown_file}
    assert by_path[python_file].status == "resolved"
    assert by_path[markdown_file].status == "resolved"
    assert directory not in by_path
    assert result.summary == {"resolved": 2}
