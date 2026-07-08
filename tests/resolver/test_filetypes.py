# topmark:header:start
#
#   project      : TopMark
#   file         : test_filetypes.py
#   file_relpath : tests/resolver/test_filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for direct file type resolution contracts.

These tests exercise `topmark.resolution.filetypes` helpers directly. They
intentionally avoid the CLI and pipeline step layers so candidate filtering,
scoring, ordering, and content-gating contracts can be validated independently
from command output and pipeline status mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.filetypes.model import ContentGate
from topmark.processors.base import HeaderProcessor
from topmark.resolution.filetypes import candidate_order_key
from topmark.resolution.filetypes import get_file_type_candidates_for_path
from topmark.resolution.filetypes import probe_resolution_for_path
from topmark.resolution.probe import ResolutionProbeStatus

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import EffectiveRegistries
    from topmark.filetypes.model import FileType
    from topmark.resolution.filetypes import FileTypeCandidate
    from topmark.resolution.probe import ResolutionProbeCandidate
    from topmark.resolution.probe import ResolutionProbeResult


def test_candidate_filter_accepts_local_and_qualified_file_type_identifiers(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Candidate filters should accept public local and qualified identifiers."""
    file: Path = tmp_path / "example.shared"
    file.write_text("shared\n", encoding="utf-8")

    alpha_ft: FileType = make_file_type(
        local_key="alpha",
        extensions=[".shared"],
    )
    beta_ft: FileType = make_file_type(
        local_key="beta",
        extensions=[".shared"],
    )
    filetypes: dict[str, FileType] = {
        "alpha": alpha_ft,
        "beta": beta_ft,
    }
    processors: dict[str, HeaderProcessor] = {}

    with effective_registries(filetypes, processors):
        included_candidates: list[FileTypeCandidate] = get_file_type_candidates_for_path(
            file,
            include_file_types={alpha_ft.local_key, beta_ft.qualified_key},
        )
        excluded_candidates: list[FileTypeCandidate] = get_file_type_candidates_for_path(
            file,
            include_file_types={alpha_ft.local_key, beta_ft.qualified_key},
            exclude_file_types={beta_ft.qualified_key},
        )

    assert {candidate.file_type.qualified_key for candidate in included_candidates} == {
        alpha_ft.qualified_key,
        beta_ft.qualified_key,
    }
    assert [candidate.file_type.qualified_key for candidate in excluded_candidates] == [
        alpha_ft.qualified_key
    ]


def test_probe_content_gate_never_does_not_call_content_matcher(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """ContentGate.NEVER should preserve name matches without probing content."""
    file: Path = tmp_path / "example.cfg"
    file.write_text("cfg\n", encoding="utf-8")
    matcher_calls: list[Path] = []

    def content_matcher(path: Path) -> bool:
        matcher_calls.append(path)
        return True

    cfg_ft: FileType = make_file_type(
        local_key="config",
        extensions=[".cfg"],
        content_matcher=content_matcher,
        content_gate=ContentGate.NEVER,
    )
    filetypes: dict[str, FileType] = {"config": cfg_ft}
    processors: dict[str, HeaderProcessor] = {"config": HeaderProcessor()}

    with effective_registries(filetypes, processors):
        probe: ResolutionProbeResult = probe_resolution_for_path(file)

    assert matcher_calls == []
    assert probe.status == ResolutionProbeStatus.RESOLVED
    assert probe.selected_file_type is not None
    assert probe.selected_file_type.qualified_key == cfg_ft.qualified_key
    assert len(probe.candidates) == 1
    candidate: ResolutionProbeCandidate = probe.candidates[0]
    assert candidate.qualified_key == cfg_ft.qualified_key
    assert candidate.match.extension is True
    assert candidate.match.content_probe_allowed is False
    assert candidate.match.content_match is False
    assert candidate.match.content_error is None


def test_candidate_order_prefers_filename_then_deterministic_identifier_ties(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Candidate ordering should prefer specificity and stable identifier ties."""
    named_file: Path = tmp_path / "pyproject.toml"
    named_file.write_text("[project]\n", encoding="utf-8")
    filename_ft: FileType = make_file_type(
        local_key="pyproject",
        filenames=["pyproject.toml"],
    )
    extension_ft: FileType = make_file_type(
        local_key="toml",
        extensions=[".toml"],
    )

    with effective_registries(
        {
            "toml": extension_ft,
            "pyproject": filename_ft,
        },
        {},
    ):
        specificity_candidates: list[FileTypeCandidate] = sorted(
            get_file_type_candidates_for_path(named_file),
            key=candidate_order_key,
        )

    assert [candidate.file_type.qualified_key for candidate in specificity_candidates] == [
        filename_ft.qualified_key,
        extension_ft.qualified_key,
    ]
    assert specificity_candidates[0].score > specificity_candidates[1].score

    tied_file: Path = tmp_path / "example.tie"
    tied_file.write_text("tie\n", encoding="utf-8")
    later_ft: FileType = make_file_type(
        namespace="pytest-b",
        local_key="later",
        extensions=[".tie"],
    )
    earlier_ft: FileType = make_file_type(
        namespace="pytest-a",
        local_key="earlier",
        extensions=[".tie"],
    )

    with effective_registries(
        {
            "later": later_ft,
            "earlier": earlier_ft,
        },
        {},
    ):
        tied_candidates: list[FileTypeCandidate] = sorted(
            get_file_type_candidates_for_path(tied_file),
            key=candidate_order_key,
        )

    assert [candidate.score for candidate in tied_candidates] == [
        tied_candidates[0].score,
        tied_candidates[0].score,
    ]
    assert [candidate.file_type.qualified_key for candidate in tied_candidates] == [
        earlier_ft.qualified_key,
        later_ft.qualified_key,
    ]
