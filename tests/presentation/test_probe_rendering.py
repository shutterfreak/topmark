# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_rendering.py
#   file_relpath : tests/presentation/test_probe_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for human-facing probe presentation renderers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.result import ProbeCandidateSnapshot
from topmark.pipeline.result import ProbeMatchSnapshot
from topmark.presentation.markdown.probe import render_probe_output_markdown
from topmark.presentation.shared.pipeline import ProbeCommandHumanReport
from topmark.presentation.shared.probe import format_probe_match_signals
from topmark.presentation.text.probe import render_probe_output_text
from topmark.resolution.probe import ResolutionProbeCandidate
from topmark.resolution.probe import ResolutionProbeMatchSignals
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeResult
from topmark.resolution.probe import ResolutionProbeSelection
from topmark.resolution.probe import ResolutionProbeStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.reduction import ProcessingReduction
    from topmark.pipeline.result import ProcessingResult


def _candidate(
    *,
    qualified_key: str = "topmark:python",
    local_key: str = "python",
    score: int = 10,
    selected: bool = True,
    rank: int = 1,
    content_error: str | None = None,
) -> ResolutionProbeCandidate:
    """Return a deterministic probe candidate."""
    return ResolutionProbeCandidate(
        qualified_key=qualified_key,
        namespace="topmark",
        local_key=local_key,
        score=score,
        selected=selected,
        tie_break_rank=rank,
        match=ResolutionProbeMatchSignals(
            extension=True,
            filename=False,
            pattern=False,
            content_probe_allowed=True,
            content_match=content_error is None,
            content_error=content_error,
        ),
    )


def _selection(
    *,
    qualified_key: str = "topmark:python",
    local_key: str = "python",
    score: int | None = 10,
) -> ResolutionProbeSelection:
    """Return a deterministic probe selection."""
    return ResolutionProbeSelection(
        qualified_key=qualified_key,
        namespace="topmark",
        local_key=local_key,
        score=score,
    )


def _processor_selection() -> ResolutionProbeSelection:
    """Return a deterministic processor selection."""
    return _selection(
        qualified_key="topmark:pound",
        local_key="pound",
        score=None,
    )


def _probe_result(
    path: Path,
    *,
    status: ResolutionProbeStatus = ResolutionProbeStatus.RESOLVED,
    reason: ResolutionProbeReason = ResolutionProbeReason.SELECTED_HIGHEST_SCORE,
    candidates: tuple[ResolutionProbeCandidate, ...] | None = None,
    selected_file_type: ResolutionProbeSelection | None = None,
    selected_processor: ResolutionProbeSelection | None = None,
    use_default_file_type: bool = True,
    use_default_processor: bool = True,
) -> ResolutionProbeResult:
    """Return a deterministic resolver probe result."""
    return ResolutionProbeResult(
        path=path,
        status=status,
        reason=reason,
        candidates=candidates if candidates is not None else (_candidate(),),
        selected_file_type=_selection()
        if selected_file_type is None and use_default_file_type
        else selected_file_type,
        selected_processor=_processor_selection()
        if selected_processor is None and use_default_processor
        else selected_processor,
    )


def _probe_context(
    path: Path,
    *,
    probe: ResolutionProbeResult | None,
) -> ProcessingContext:
    """Create a context reduced as a probe processing result."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.run_options = RunOptions(pipeline_kind="probe")
    ctx.resolution_probe = probe
    return ctx


def _result(ctx: ProcessingContext) -> ProcessingResult:
    """Reduce one probe context to a durable processing result."""
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    return reduction.results[0]


def _report(
    *,
    view_results: Sequence[ProcessingResult],
    verbosity_level: int,
) -> ProbeCommandHumanReport:
    """Build a shared probe presentation report."""
    return ProbeCommandHumanReport(
        verbosity_level=verbosity_level,
        styled=False,
        pipeline_kind="probe",
        file_list_total=len(view_results),
        view_results=view_results,
    )


def test_shared_probe_match_signal_formatter_includes_content_errors() -> None:
    """Shared probe helper should keep TEXT and Markdown match signals consistent."""
    candidate = ProbeCandidateSnapshot(
        qualified_key="topmark:xml",
        namespace="topmark",
        local_key="xml",
        score=7,
        selected=False,
        tie_break_rank=2,
        match=ProbeMatchSnapshot(
            extension=False,
            filename=True,
            pattern=True,
            content_probe_allowed=False,
            content_match=False,
            content_error="UnicodeDecodeError",
        ),
    )

    assert format_probe_match_signals(candidate) == (
        "extension=false filename=true pattern=true content_probe=false "
        "content_match=false content_error=UnicodeDecodeError"
    )


def test_render_probe_output_markdown_includes_missing_probe_sections(tmp_path: Path) -> None:
    """Markdown probe output should make missing durable probe results explicit."""
    result: ProcessingResult = _result(_probe_context(tmp_path / "missing.py", probe=None))

    output: str = render_probe_output_markdown(
        _report(view_results=[result], verbosity_level=0),
    )

    assert "# TopMark Resolution Probe Results" in output
    assert "Probing **1** file(s)." in output
    assert "## Files" in output
    assert "### `" in output
    assert "- **Status:** `probe-missing`" in output
    assert "no resolution probe result was recorded" in output


def test_render_probe_output_markdown_filtered_probe_omits_candidate_table(
    tmp_path: Path,
) -> None:
    """Markdown filtered probe output should render `<none>` selections without a table."""
    probe: ResolutionProbeResult = _probe_result(
        tmp_path / "ignored.py",
        status=ResolutionProbeStatus.FILTERED,
        reason=ResolutionProbeReason.EXCLUDED_BY_PATH_FILTER,
        candidates=(),
        selected_file_type=None,
        selected_processor=None,
        use_default_file_type=False,
        use_default_processor=False,
    )
    result: ProcessingResult = _result(_probe_context(tmp_path / "ignored.py", probe=probe))

    output: str = render_probe_output_markdown(
        _report(view_results=[result], verbosity_level=0),
    )

    assert "- **Status:** `filtered`" in output
    assert "- **Reason:** `excluded_by_path_filter`" in output
    assert "- **Selected file type:** `<none>`" in output
    assert "- **Selected processor:** `<none>`" in output
    assert "- **Candidates:** 0" in output
    assert "#### Candidates" not in output


def test_render_probe_output_markdown_renders_diagnostics_and_candidates(
    tmp_path: Path,
) -> None:
    """Markdown probe output should include diagnostics and candidate match signals."""
    probe: ResolutionProbeResult = _probe_result(
        tmp_path / "demo.xml",
        candidates=(
            _candidate(
                qualified_key="topmark:xml",
                local_key="xml",
                content_error="UnicodeDecodeError",
            ),
        ),
        selected_file_type=_selection(
            qualified_key="topmark:xml",
            local_key="xml",
            score=10,
        ),
    )
    ctx: ProcessingContext = _probe_context(tmp_path / "demo.xml", probe=probe)
    ctx.diagnostics.add(
        Diagnostic(level=DiagnosticLevel.WARNING, message="content probe fell back"),
    )
    result: ProcessingResult = _result(ctx)

    output: str = render_probe_output_markdown(
        _report(view_results=[result], verbosity_level=0),
    )

    assert "#### Diagnostics" in output
    assert "**[warning]** content probe fell back" in output
    assert "#### Candidates" in output
    assert "| Rank" in output
    assert "| File Type" in output
    assert "| Match Signals" in output
    assert "`topmark:xml`" in output
    assert "content_error=UnicodeDecodeError" in output


def test_render_probe_output_text_reports_missing_probe_results(tmp_path: Path) -> None:
    """TEXT probe output should make missing durable probe results explicit."""
    result: ProcessingResult = _result(_probe_context(tmp_path / "missing.py", probe=None))

    output: str = render_probe_output_text(
        _report(view_results=[result], verbosity_level=0),
    )

    assert "missing.py:" in output
    assert "probe-missing" in output
    assert "no resolution probe result was recorded" in output


def test_render_probe_output_text_verbose_filtered_probe_has_none_selections(
    tmp_path: Path,
) -> None:
    """Verbose TEXT filtered output should include `<none>` selected details."""
    probe: ResolutionProbeResult = _probe_result(
        tmp_path / "filtered.py",
        status=ResolutionProbeStatus.FILTERED,
        reason=ResolutionProbeReason.EXCLUDED_BY_DISCOVERY_FILTER,
        candidates=(),
        selected_file_type=None,
        selected_processor=None,
        use_default_file_type=False,
        use_default_processor=False,
    )
    result: ProcessingResult = _result(_probe_context(tmp_path / "filtered.py", probe=probe))

    output: str = render_probe_output_text(
        _report(view_results=[result], verbosity_level=1),
    )

    assert "filtered.py:" in output
    assert "<filtered>" in output
    assert "selected file type: <none>" in output
    assert "selected processor: <none>" in output


def test_render_probe_output_text_compact_filtered_probe_uses_filtered_label(
    tmp_path: Path,
) -> None:
    """Compact TEXT probe output should distinguish filtered files from unknown files."""
    probe: ResolutionProbeResult = _probe_result(
        tmp_path / "ignored.py",
        status=ResolutionProbeStatus.FILTERED,
        reason=ResolutionProbeReason.EXCLUDED_BY_FILE_TYPE_FILTER,
        candidates=(),
        selected_file_type=None,
        selected_processor=None,
        use_default_file_type=False,
        use_default_processor=False,
    )
    result: ProcessingResult = _result(_probe_context(tmp_path / "ignored.py", probe=probe))

    output: str = render_probe_output_text(
        _report(view_results=[result], verbosity_level=0),
    )

    assert "TopMark Resolution Probe Results" not in output
    assert "ignored.py:" in output
    assert "<filtered>" in output
    assert "filtered: excluded_by_file_type_filter" in output


def test_render_probe_output_text_verbose_no_processor_probe_has_none_processor(
    tmp_path: Path,
) -> None:
    """Verbose TEXT probe output should report unbound selections without candidates."""
    probe: ResolutionProbeResult = _probe_result(
        tmp_path / "unbound.custom",
        status=ResolutionProbeStatus.NO_PROCESSOR,
        reason=ResolutionProbeReason.SELECTED_FILE_TYPE_HAS_NO_BOUND_PROCESSOR,
        candidates=(),
        selected_file_type=_selection(
            qualified_key="topmark:custom",
            local_key="custom",
            score=None,
        ),
        selected_processor=None,
        use_default_processor=False,
    )
    result: ProcessingResult = _result(_probe_context(tmp_path / "unbound.custom", probe=probe))

    output: str = render_probe_output_text(
        _report(view_results=[result], verbosity_level=2),
    )

    assert "📋 TopMark Resolution Probe Results" in output
    assert "unbound.custom:" in output
    assert "no_processor: processor=<none>" in output
    assert "selected file type: topmark:custom" in output
    assert "selected processor: <none>" in output
    assert "  candidates: 0" in output
    assert "  candidates:\n" not in output


def test_render_probe_output_text_verbose_renders_candidates_and_diagnostics(
    tmp_path: Path,
) -> None:
    """Verbose TEXT probe output should include candidate details and diagnostics."""
    probe: ResolutionProbeResult = _probe_result(
        tmp_path / "demo.py",
        candidates=(
            _candidate(content_error="UnicodeDecodeError"),
            _candidate(
                qualified_key="topmark:text",
                local_key="text",
                score=1,
                selected=False,
                rank=2,
            ),
        ),
    )
    ctx: ProcessingContext = _probe_context(tmp_path / "demo.py", probe=probe)
    ctx.diagnostics.add(
        Diagnostic(level=DiagnosticLevel.ERROR, message="probe warning promoted"),
    )
    result: ProcessingResult = _result(ctx)

    output: str = render_probe_output_text(
        _report(view_results=[result], verbosity_level=2),
    )

    assert "demo.py:" in output
    assert "resolved: processor=pound, score=10" in output
    assert "  candidates:" in output
    assert "1. topmark:python score=10 (selected)" in output
    assert "2. topmark:text score=1" in output
    assert "content_error=UnicodeDecodeError" in output
    assert "ℹ️  Diagnostics: 1 error" in output
    assert "[error] probe warning promoted" in output
