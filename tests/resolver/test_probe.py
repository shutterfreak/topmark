# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe.py
#   file_relpath : tests/resolver/test_probe.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for resolution probe result construction.

These tests exercise `probe_resolution_for_path()` directly. They intentionally
avoid the CLI and pipeline step layers so the probe result contract can be
validated independently from command output and pipeline status mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.processors.base import HeaderProcessor
from topmark.resolution.filetypes import probe_resolution_for_path
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeStatus

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import EffectiveRegistries
    from topmark.filetypes.model import FileType
    from topmark.resolution.probe import ResolutionProbeCandidate
    from topmark.resolution.probe import ResolutionProbeResult


def _selected_candidate_count(probe: ResolutionProbeResult) -> int:
    """Return the number of candidates marked as selected.

    Args:
        probe: Resolution probe result to inspect.

    Returns:
        Number of selected candidates in the probe result.
    """
    return sum(1 for candidate in probe.candidates if candidate.selected)


def test_probe_python_file_resolves_with_selected_file_type_and_processor(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """A supported file should produce selected file type and processor details."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    py_ft: FileType = make_file_type(
        local_key="python",
        extensions=[".py"],
    )
    filetypes: dict[str, FileType] = {"python": py_ft}
    processors: dict[str, HeaderProcessor] = {"python": HeaderProcessor()}

    with effective_registries(filetypes, processors):
        probe: ResolutionProbeResult = probe_resolution_for_path(file)

    assert probe.status == ResolutionProbeStatus.RESOLVED
    assert probe.reason == ResolutionProbeReason.SELECTED_HIGHEST_SCORE
    assert probe.selected_file_type is not None
    assert probe.selected_file_type.qualified_key == py_ft.qualified_key
    assert probe.selected_file_type.local_key == "python"
    assert probe.selected_file_type.score is not None
    assert probe.selected_processor is not None
    assert probe.candidates
    assert _selected_candidate_count(probe) == 1

    selected_candidates: list[ResolutionProbeCandidate] = [
        candidate for candidate in probe.candidates if candidate.selected
    ]
    selected_candidate: ResolutionProbeCandidate = selected_candidates[0]
    assert selected_candidate.qualified_key == py_ft.qualified_key
    assert selected_candidate.tie_break_rank == 1
    assert selected_candidate.match.extension is True
    assert selected_candidate.match.content_probe_allowed is False
    assert selected_candidate.match.content_match is False


def test_probe_unknown_extension_reports_unsupported_without_candidates(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """A file with no matching file type should produce an unsupported probe."""
    file: Path = tmp_path / "example.unknown"
    file.write_text("unclassified\n", encoding="utf-8")

    filetypes: dict[str, FileType] = {}
    processors: dict[str, HeaderProcessor] = {}

    with effective_registries(filetypes, processors):
        probe: ResolutionProbeResult = probe_resolution_for_path(file)

    assert probe.status == ResolutionProbeStatus.UNSUPPORTED
    assert probe.reason == ResolutionProbeReason.NO_CANDIDATES
    assert probe.selected_file_type is None
    assert probe.selected_processor is None
    assert probe.candidates == ()


def test_probe_candidates_are_ranked_and_have_single_selected_winner(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Probe candidates should be deterministically ranked with one winner."""
    file: Path = tmp_path / "README.md"
    file.write_text("# Project\n", encoding="utf-8")

    markdown_ft: FileType = make_file_type(
        local_key="markdown",
        extensions=[".md"],
    )
    readme_ft: FileType = make_file_type(
        local_key="readme",
        filenames=["README.md"],
    )
    filetypes: dict[str, FileType] = {
        "markdown": markdown_ft,
        "readme": readme_ft,
    }
    processors: dict[str, HeaderProcessor] = {
        "markdown": HeaderProcessor(),
        "readme": HeaderProcessor(),
    }

    with effective_registries(filetypes, processors):
        probe: ResolutionProbeResult = probe_resolution_for_path(file)

    assert probe.status == ResolutionProbeStatus.RESOLVED
    assert len(probe.candidates) == 2
    assert _selected_candidate_count(probe) == 1

    ranks: list[int] = [candidate.tie_break_rank for candidate in probe.candidates]
    assert ranks == [1, 2]

    scores: list[int] = [candidate.score for candidate in probe.candidates]
    assert scores == sorted(scores, reverse=True)

    assert probe.candidates[0].selected is True
    assert probe.selected_file_type is not None
    assert probe.candidates[0].qualified_key == probe.selected_file_type.qualified_key
