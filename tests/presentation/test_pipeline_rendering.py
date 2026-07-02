# topmark:header:start
#
#   project      : TopMark
#   file         : test_pipeline_rendering.py
#   file_relpath : tests/presentation/test_pipeline_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for human-facing pipeline presentation renderers."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import unsupported_output_format
from tests.helpers.registry import make_file_type
from tests.presentation.conftest import find_table_row
from topmark.cli.errors import TopmarkCliPipelineError
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.formats import OutputFormat
from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.hints import make_hint
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import iter_machine_processing_stream
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.reporting import would_add_or_update_result
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PatchStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.status import WriteStatus
from topmark.pipeline.views import DiffView
from topmark.presentation.markdown.paths import render_path_display_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_apply_summary_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_diffs_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_output_markdown
from topmark.presentation.output.pipeline import render_pipeline_command_human_output
from topmark.presentation.output.pipeline import render_pipeline_command_human_stream_output
from topmark.presentation.shared.paths import get_display_path
from topmark.presentation.shared.paths import render_path_display_text
from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
from topmark.presentation.shared.pipeline import PipelineHumanPresentationOptions
from topmark.presentation.shared.pipeline import get_file_type_label
from topmark.presentation.shared.pipeline import summarize_pipeline_file
from topmark.presentation.text.pipeline import render_pipeline_apply_summary_text
from topmark.presentation.text.pipeline import render_pipeline_diffs_text
from topmark.presentation.text.pipeline import render_pipeline_output_text
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.machine.streaming import MachineProcessingStreamEvent
    from topmark.pipeline.reduction import ProcessingReduction
    from topmark.pipeline.result import ProcessingResult
    from topmark.presentation.shared.pipeline import PipelineCommandHumanOutput
    from topmark.presentation.shared.pipeline import PipelineFileSummary


def _make_context(
    path: Path,
    *,
    pipeline_kind: PipelineKindLiteral = "check",
    apply_changes: bool = False,
    stdin_mode: bool = False,
    stdin_filename: str | None = None,
) -> ProcessingContext:
    """Create a resolved pipeline context suitable for presentation tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.run_options = RunOptions(
        pipeline_kind=pipeline_kind,
        apply_changes=apply_changes,
        stdin_mode=stdin_mode,
        stdin_filename=stdin_filename,
    )
    ctx.file_type = make_file_type(
        local_key="python",
        namespace="test",
        description="Python source",
    )
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.MISSING
    ctx.status.comparison = ComparisonStatus.CHANGED
    ctx.status.plan = PlanStatus.PREVIEWED
    return ctx


def _make_report(
    *,
    pipeline_kind: PipelineKindLiteral = "check",
    view_results: Sequence[ProcessingResult],
    file_list_total: int | None = None,
    verbosity_level: int = 0,
    report_scope: ReportScope = ReportScope.ACTIONABLE,
    unsupported_count: int = 0,
    summary_mode: bool = False,
    show_diffs: bool = False,
    apply_changes: bool = False,
) -> PipelineCommandHumanReport:
    """Build a shared human pipeline report for text/Markdown renderers."""
    return PipelineCommandHumanReport(
        verbosity_level=verbosity_level,
        styled=False,
        pipeline_kind=pipeline_kind,
        file_list_total=file_list_total if file_list_total is not None else len(view_results),
        view_results=view_results,
        report_scope=report_scope,
        unsupported_count=unsupported_count,
        summary_mode=summary_mode,
        show_diffs=show_diffs,
        apply_changes=apply_changes,
    )


def _make_presentation_options(
    *,
    pipeline_kind: PipelineKindLiteral = "check",
    verbosity_level: int = 0,
    report_scope: ReportScope = ReportScope.ACTIONABLE,
    summary_mode: bool = False,
    show_diffs: bool = False,
    apply_changes: bool = False,
) -> PipelineHumanPresentationOptions:
    """Build shared human pipeline presentation options for stream renderers."""
    return PipelineHumanPresentationOptions(
        verbosity_level=verbosity_level,
        styled=False,
        pipeline_kind=pipeline_kind,
        report_scope=report_scope,
        summary_mode=summary_mode,
        show_diffs=show_diffs,
        apply_changes=apply_changes,
    )


def _add_diff(
    ctx: ProcessingContext,
) -> None:
    """Attach a deterministic unified diff to a context."""
    ctx.status.patch = PatchStatus.GENERATED
    ctx.views.diff = DiffView(text="--- old\n+++ new\n@@ -1 +1 @@\n-old\n+new\n")


def _force_check_actionable_with_no_concrete_intent(
    result: ProcessingResult,
) -> ProcessingResult:
    """Return a check-actionable result whose statuses imply no concrete intent."""
    return replace(
        result,
        status=replace(
            result.status,
            header=HeaderStatus.PENDING,
            strip=StripStatus.PENDING,
        ),
        outcome=replace(
            result.outcome,
            would_add_or_update=True,
            effective_would_add_or_update=True,
        ),
    )


def _force_strip_actionable_with_insert_intent(
    result: ProcessingResult,
) -> ProcessingResult:
    """Return a strip-actionable result whose statuses imply insert intent."""
    return replace(
        result,
        status=replace(
            result.status,
            header=HeaderStatus.MISSING,
            strip=StripStatus.PENDING,
        ),
        outcome=replace(
            result.outcome,
            would_strip=True,
            effective_would_strip=True,
        ),
    )


def test_render_path_display_text_uses_regular_display_path(
    tmp_path: Path,
) -> None:
    """TEXT path labels should quote regular display paths without STDIN annotation."""
    ctx: ProcessingContext = _make_context(tmp_path / "regular.py")

    assert render_path_display_text(ctx) == f"'{ctx.path}'"


def test_render_path_display_text_uses_stdin_filename(
    tmp_path: Path,
) -> None:
    """TEXT path labels should show the logical stdin filename in STDIN mode."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "materialized-stdin.py",
        stdin_mode=True,
        stdin_filename="logical/input.py",
    )

    assert render_path_display_text(ctx) == "'logical/input.py' (via STDIN)"


def test_render_path_display_markdown_uses_regular_display_path(
    tmp_path: Path,
) -> None:
    """Markdown path labels should render regular display paths as code spans."""
    ctx: ProcessingContext = _make_context(tmp_path / "regular.py")

    assert render_path_display_markdown(ctx) == f"`{ctx.path}`"


def test_render_path_display_markdown_uses_stdin_filename(
    tmp_path: Path,
) -> None:
    """Markdown path labels should show the logical stdin filename in STDIN mode."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "materialized-stdin.py",
        stdin_mode=True,
        stdin_filename="logical/input.py",
    )

    assert render_path_display_markdown(ctx) == "`logical/input.py` _(via STDIN)_"


def test_shared_display_path_uses_stdin_filename_for_stdin_context(
    tmp_path: Path,
) -> None:
    """Shared path rendering should prefer logical STDIN filenames."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "stdin-buffer.py",
        stdin_mode=True,
        stdin_filename="logical.py",
    )

    assert get_display_path(ctx) == "logical.py"


def test_shared_file_type_label_omits_missing_file_type_for_not_found(
    tmp_path: Path,
) -> None:
    """Missing-file synthetic contexts should omit the file-type label."""
    ctx: ProcessingContext = _make_context(tmp_path / "missing.py")
    ctx.file_type = None
    ctx.status.fs = FsStatus.NOT_FOUND

    assert get_file_type_label(ctx) is None


def test_shared_file_type_label_falls_back_to_unknown_for_unresolved_type(
    tmp_path: Path,
) -> None:
    """Resolved non-missing contexts without a file type should render as unknown."""
    ctx: ProcessingContext = _make_context(tmp_path / "unknown.ext")
    ctx.file_type = None

    assert get_file_type_label(ctx) == "<unknown>"


def test_shared_pipeline_file_summary_centralizes_compact_suffixes(
    tmp_path: Path,
) -> None:
    """Shared summary data should capture suffix semantics without format details."""
    ctx: ProcessingContext = _make_context(tmp_path / "summary-shared.py")
    _add_diff(ctx)
    ctx.diagnostics.add(
        Diagnostic(level=DiagnosticLevel.WARNING, message="Check this file"),
    )

    result: ProcessingResult = reduce_processing_contexts([ctx]).results[0]

    summary: PipelineFileSummary = summarize_pipeline_file(result)

    assert summary.file_type_label == "python"
    assert summary.key == "would insert"
    assert summary.label == "header missing, changes found"
    assert summary.secondary_parts == ("diff", "1 warning")
    assert summary.diagnostic_total == 1


def test_shared_pipeline_file_summary_prioritizes_write_status_over_diff(
    tmp_path: Path,
) -> None:
    """Write outcomes should remain the primary compact suffix for both renderers."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "written.py",
        apply_changes=True,
    )
    _add_diff(ctx)
    ctx.status.write = WriteStatus.WRITTEN

    result: ProcessingResult = reduce_processing_contexts([ctx]).results[0]

    summary: PipelineFileSummary = summarize_pipeline_file(result)

    assert summary.secondary_parts == ("changes written to file",)
    assert summary.diagnostic_total == 0


@pytest.mark.parametrize(
    (
        "diagnostic_level",
        "expected_triage_summary",
        "expected_secondary_parts",
        "expected_diagnostic_total",
    ),
    [
        (None, "", (), 0),
        (DiagnosticLevel.WARNING, "1 warning", ("1 warning",), 1),
    ],
)
def test_shared_pipeline_file_summary_reports_diagnostic_summary(
    tmp_path: Path,
    diagnostic_level: DiagnosticLevel | None,
    expected_triage_summary: str,
    expected_secondary_parts: tuple[str, ...],
    expected_diagnostic_total: int,
) -> None:
    """Shared summary data should report diagnostics only when present."""
    ctx: ProcessingContext = _make_context(tmp_path / "diagnostics-summary.py")
    if diagnostic_level is not None:
        ctx.diagnostics.add(
            Diagnostic(level=diagnostic_level, message="Check this file"),
        )

    result: ProcessingResult = reduce_processing_contexts([ctx]).results[0]

    summary: PipelineFileSummary = summarize_pipeline_file(result)

    assert result.diagnostics.stats().triage_summary() == expected_triage_summary
    assert summary.secondary_parts == expected_secondary_parts
    assert summary.diagnostic_total == expected_diagnostic_total


def test_render_pipeline_output_text_compact_check_guidance(
    tmp_path: Path,
) -> None:
    """Compact TEXT check output should include summary, diff hint, and apply guidance."""
    ctx: ProcessingContext = _make_context(tmp_path / "demo.py")
    _add_diff(ctx)
    ctx.diagnostics.add(
        Diagnostic(level=DiagnosticLevel.WARNING, message="Check this file"),
    )

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            show_diffs=False,
            apply_changes=False,
        )
    )

    assert "demo.py:" in output
    assert "python" in output
    assert "diff" in output
    assert "1 warning" in output
    assert "(use '-v' to view)" in output
    assert "Run `topmark check --apply" in output
    assert "to add a TopMark header to this file." in output


def test_render_pipeline_output_text_verbose_includes_banner_diagnostics_and_hint(
    tmp_path: Path,
) -> None:
    """Verbose TEXT output should render banner, diagnostics, and one decisive hint."""
    ctx: ProcessingContext = _make_context(tmp_path / "verbose.py")
    ctx.diagnostics.add(
        Diagnostic(level=DiagnosticLevel.ERROR, message="Broken config"),
    )
    ctx.diagnostic_hints.add(
        make_hint(
            axis=Axis.PLAN,
            code=KnownCode.PLAN_INSERT,
            message="Would insert header",
            detail="extra planner detail",
            cluster=Cluster.WOULD_CHANGE,
        )
    )

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            verbosity_level=1,
        )
    )

    assert "📋 TopMark check Results" in output
    assert "Diagnostics: 1 error" in output
    assert "[error] Broken config" in output
    assert "Hints: 1" in output
    assert "plan" in output
    assert "Would insert header" in output
    assert "use '-vv' to display detailed hints" in output


def test_render_pipeline_output_text_summary_with_diff_section(
    tmp_path: Path,
) -> None:
    """TEXT summary mode should render optional diffs plus grouped outcome counts."""
    ctx: ProcessingContext = _make_context(tmp_path / "summary.py")
    _add_diff(ctx)

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            verbosity_level=1,
            summary_mode=True,
            show_diffs=True,
            file_list_total=3,
        )
    )

    assert "diffs - start" in output
    assert "-old" in output
    assert "+new" in output
    assert "Summary by outcome:" in output
    assert "TOTAL" in output
    assert ": 3" in output


def test_render_pipeline_output_text_actionable_footer_for_hidden_unsupported(
    tmp_path: Path,
) -> None:
    """TEXT actionable output should summarize unsupported files hidden from the list."""
    ctx: ProcessingContext = _make_context(tmp_path / "actionable.py")

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            report_scope=ReportScope.ACTIONABLE,
            unsupported_count=2,
        )
    )

    assert "Unsupported: 2 file(s)" in output
    assert "--report=noncompliant" in output


def test_render_pipeline_output_text_strip_guidance_uses_strip_command(
    tmp_path: Path,
) -> None:
    """TEXT strip rendering should produce strip-specific dry-run guidance."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip.py")
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.PREVIEWED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
        )
    )

    assert "Run `topmark strip --apply" in output
    assert "to strip the TopMark header from this file." in output


def test_render_pipeline_output_text_apply_mode_reports_write_skipped(
    tmp_path: Path,
) -> None:
    """TEXT apply-mode guidance should report defensive skipped writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "skipped.py",
        apply_changes=True,
    )
    ctx.status.write = WriteStatus.SKIPPED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write was skipped" in output
    assert "⚠️  Could not insert header (write skipped)." in output


def test_render_pipeline_output_markdown_apply_mode_reports_write_failed(
    tmp_path: Path,
) -> None:
    """Markdown apply-mode guidance should report failed writes explicitly."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "failed.py",
        apply_changes=True,
    )
    ctx.status.write = WriteStatus.FAILED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write failed" in output
    assert "❌ Could not insert header: write failed" in output


def test_render_pipeline_output_text_renders_hint_detail_at_double_verbose(
    tmp_path: Path,
) -> None:
    """TEXT hints should reveal multiline details at ``-vv`` verbosity."""
    ctx: ProcessingContext = _make_context(tmp_path / "hints.py")
    ctx.diagnostic_hints.add(
        make_hint(
            axis=Axis.PLAN,
            code=KnownCode.PLAN_INSERT,
            message="Would insert header",
            detail="first detail\nsecond detail",
            cluster=Cluster.WOULD_CHANGE,
            terminal=True,
        )
    )

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            verbosity_level=2,
        )
    )

    assert "⏹ plan" in output
    assert "(terminal)" in output
    assert "first detail" in output
    assert "second detail" in output
    assert "use '-vv'" not in output


def test_render_pipeline_output_text_empty_summary_reports_total_only() -> None:
    """TEXT summary mode should render a total even when no rows are visible."""
    output: str = render_pipeline_output_text(
        _make_report(
            view_results=[],
            file_list_total=0,
            summary_mode=True,
        )
    )

    assert "Summary by outcome:" in output
    assert "TOTAL" in output
    assert ": 0" in output
    assert "─" not in output


def test_render_pipeline_output_markdown_per_file_includes_diagnostics_hints_and_diff(
    tmp_path: Path,
) -> None:
    """Markdown per-file output should include diagnostics, hints, and fenced diffs."""
    path: Path = tmp_path / "markdown.py"
    ctx: ProcessingContext = _make_context(path)
    _add_diff(ctx)
    ctx.diagnostics.add(
        Diagnostic(level=DiagnosticLevel.WARNING, message="Review generated header"),
    )
    ctx.diagnostic_hints.add(
        make_hint(
            axis=Axis.PLAN,
            code=KnownCode.PLAN_INSERT,
            message="Would insert header",
            detail="planner detail",
            cluster=Cluster.WOULD_CHANGE,
        )
    )

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            show_diffs=True,
        )
    )

    assert output.startswith("# TopMark check Results\n")
    assert "## Files" in output
    assert f"`{path}` (python)" in output
    assert "🛠️  Run `topmark check --apply" in output
    assert "> ℹ️ **Diagnostics:** 1 warning" in output
    assert "- ⚠️ **[warning]** Review generated header" in output
    assert "- Hints: 1" in output
    assert "▶ **plan** (`would_change`) `plan:insert`: Would insert header" in output
    assert "planner detail" in output
    assert "```diff" in output
    assert "-old" in output
    assert "+new" in output


def test_render_pipeline_output_markdown_summary_table_and_total(
    tmp_path: Path,
) -> None:
    """Markdown summary mode should render grouped outcome table and total."""
    ctx: ProcessingContext = _make_context(tmp_path / "summary.md.py")

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            summary_mode=True,
            file_list_total=5,
        )
    )

    assert "## Summary by outcome" in output
    assert find_table_row(output, "Outcome") == ["Outcome", "Reason", "Count"]
    assert "Total files: **5**" in output


def test_render_pipeline_output_markdown_summary_diff_section(
    tmp_path: Path,
) -> None:
    """Markdown summary mode should render the separate diff section when requested."""
    path: Path = tmp_path / "diffs.py"
    ctx: ProcessingContext = _make_context(path)
    _add_diff(ctx)

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            summary_mode=True,
            show_diffs=True,
        )
    )

    assert "## Diffs" in output
    assert f"### `{path}`" in output
    assert "```diff" in output
    assert "-old" in output
    assert "+new" in output


def test_render_pipeline_output_markdown_actionable_footer_for_hidden_unsupported(
    tmp_path: Path,
) -> None:
    """Markdown actionable output should summarize unsupported files hidden from the list."""
    ctx: ProcessingContext = _make_context(tmp_path / "actionable.py")

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            report_scope=ReportScope.ACTIONABLE,
            unsupported_count=4,
        )
    )

    assert "> ⚠️ Unsupported: 4 file(s)" in output
    assert "--report=noncompliant" in output


def test_render_pipeline_apply_summary_text_reports_written_and_failed() -> None:
    """TEXT apply summary should report written and failed counts."""
    output: str = render_pipeline_apply_summary_text(
        command_path="topmark check",
        written=2,
        failed=1,
        styled=False,
    )

    assert "✅ topmark check: applied changes to 2 file(s)." in output
    assert "⚠️ topmark check: failed to write 1 file(s). See log for details." in output


def test_render_pipeline_apply_summary_markdown_reports_noop_and_failed() -> None:
    """Markdown apply summary should report no-op and failed counts."""
    output: str = render_pipeline_apply_summary_markdown(
        command_path="topmark strip",
        written=0,
        failed=1,
    )

    assert "✅ `topmark strip`: no changes to apply." in output
    assert "> ⚠️ `topmark strip`: failed to write **1** file(s). See log for details." in output


def test_render_pipeline_output_markdown_check_guidance_uses_stdin_filename(
    tmp_path: Path,
) -> None:
    """Markdown check guidance should render the STDIN apply command contract."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "stdin-buffer.py",
        stdin_mode=True,
        stdin_filename="logical/input.py",
    )

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
        )
    )

    assert "`logical/input.py` (python)" in output
    assert (
        "Run `topmark check --apply --stdin-filename logical/input.py -` "
        "to add a TopMark header to this file."
    ) in output


def test_render_pipeline_output_markdown_check_guidance_reports_update(
    tmp_path: Path,
) -> None:
    """Markdown check guidance should distinguish update from insert intent."""
    ctx: ProcessingContext = _make_context(tmp_path / "update.py")
    ctx.status.header = HeaderStatus.DETECTED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
        )
    )

    assert "to update the TopMark header in this file." in output
    assert "to add a TopMark header to this file." not in output


def test_render_pipeline_output_markdown_strip_guidance_uses_strip_command(
    tmp_path: Path,
) -> None:
    """Markdown strip rendering should produce strip-specific dry-run guidance."""
    ctx: ProcessingContext = _make_context(tmp_path / "strip.md.py", pipeline_kind="strip")
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.PREVIEWED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
        )
    )

    assert "# TopMark strip Results" in output
    assert "Run `topmark strip --apply" in output
    assert "to strip the TopMark header from this file." in output


def test_render_pipeline_output_markdown_strip_apply_mode_reports_write_skipped(
    tmp_path: Path,
) -> None:
    """Markdown strip apply-mode guidance should report defensive skipped writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "strip-skipped.py",
        pipeline_kind="strip",
        apply_changes=True,
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.REMOVED
    ctx.status.write = WriteStatus.SKIPPED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write skipped" in output
    assert "⚠️  Could not strip header (write skipped)." in output


def test_render_pipeline_output_text_per_file_renders_diff_fences(
    tmp_path: Path,
) -> None:
    """TEXT per-file output should render optional diff fences outside summary mode."""
    ctx: ProcessingContext = _make_context(tmp_path / "diff-fences.py")
    _add_diff(ctx)

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            show_diffs=True,
        )
    )

    assert " diff - start " in output
    assert "--- old" in output
    assert "+new" in output
    assert " diff - end " in output


def test_render_pipeline_output_text_per_file_omits_empty_diff_block(
    tmp_path: Path,
) -> None:
    """TEXT per-file output should not add diff fences for an empty retained diff."""
    ctx: ProcessingContext = _make_context(tmp_path / "empty-diff-text.py")
    ctx.status.patch = PatchStatus.GENERATED
    ctx.views.diff = DiffView(text="")

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
            show_diffs=True,
        )
    )

    assert "empty-diff-text.py" in output
    assert " diff - start " not in output
    assert " diff - end " not in output


def test_render_pipeline_apply_summary_markdown_reports_written_and_failed() -> None:
    """Markdown apply summary should report written and failed counts together."""
    output: str = render_pipeline_apply_summary_markdown(
        command_path="topmark check",
        written=2,
        failed=1,
    )

    assert "✅ `topmark check`: applied changes to **2** file(s)." in output
    assert "> ⚠️ `topmark check`: failed to write **1** file(s). See log for details." in output


def test_render_pipeline_output_text_check_guidance_reports_update(
    tmp_path: Path,
) -> None:
    """TEXT check guidance should distinguish update from insert intent."""
    ctx: ProcessingContext = _make_context(tmp_path / "text-update.py")
    ctx.status.header = HeaderStatus.DETECTED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            view_results=reduction.results,
        )
    )

    assert "to update the TopMark header in this file." in output
    assert "to add a TopMark header to this file." not in output


def test_render_pipeline_output_markdown_check_apply_mode_reports_write_skipped(
    tmp_path: Path,
) -> None:
    """Markdown check apply-mode guidance should report defensive skipped writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "markdown-skipped.py",
        apply_changes=True,
    )
    ctx.status.write = WriteStatus.SKIPPED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write skipped" in output
    assert "⚠️  Could not insert header (write skipped)." in output


def test_render_pipeline_output_markdown_strip_apply_mode_reports_write_failed(
    tmp_path: Path,
) -> None:
    """Markdown strip apply-mode guidance should report defensive failed writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "strip-failed.py",
        pipeline_kind="strip",
        apply_changes=True,
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.REMOVED
    ctx.status.write = WriteStatus.FAILED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write failed" in output
    assert "❌ Could not strip header: write failed" in output


def test_render_pipeline_output_text_strip_apply_mode_reports_write_failed(
    tmp_path: Path,
) -> None:
    """TEXT strip apply-mode guidance should report defensive failed writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "strip-failed-text.py",
        pipeline_kind="strip",
        apply_changes=True,
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.REMOVED
    ctx.status.write = WriteStatus.FAILED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write failed" in output
    assert "❌ Could not strip header: write failed" in output


def test_pipeline_check_guidance_rejects_missing_concrete_intent(
    tmp_path: Path,
) -> None:
    """Check guidance should reject actionable snapshots without insert/update intent."""
    ctx: ProcessingContext = _make_context(tmp_path / "invalid-check.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    result: ProcessingResult = _force_check_actionable_with_no_concrete_intent(
        reduction.results[0],
    )
    report: PipelineCommandHumanReport = _make_report(view_results=[result])

    with pytest.raises(TopmarkCliPipelineError, match="Unexpected intent none"):
        render_pipeline_output_text(report)

    with pytest.raises(TopmarkCliPipelineError, match="Unexpected intent none"):
        render_pipeline_output_markdown(report)


def test_pipeline_strip_guidance_rejects_non_strip_intent(
    tmp_path: Path,
) -> None:
    """Strip guidance should reject actionable snapshots without strip intent."""
    ctx: ProcessingContext = _make_context(tmp_path / "invalid-strip.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    result: ProcessingResult = _force_strip_actionable_with_insert_intent(
        reduction.results[0],
    )
    report: PipelineCommandHumanReport = _make_report(
        pipeline_kind="strip",
        view_results=[result],
    )

    with pytest.raises(TopmarkCliPipelineError, match="Unexpected intent insert"):
        render_pipeline_output_text(report)

    with pytest.raises(TopmarkCliPipelineError, match="Unexpected intent insert"):
        render_pipeline_output_markdown(report)


def test_pipeline_renderers_reject_invalid_pipeline_kind(
    tmp_path: Path,
) -> None:
    """Both renderers should reject invalid pipeline kinds defensively."""
    ctx: ProcessingContext = _make_context(tmp_path / "invalid.py")

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    report: PipelineCommandHumanReport = _make_report(
        pipeline_kind=cast("PipelineKindLiteral", "unknown"),
        view_results=reduction.results,
    )

    with pytest.raises(RuntimeError, match="Invalid pipeline kind selected"):
        render_pipeline_output_text(report)

    with pytest.raises(RuntimeError, match="Invalid pipeline kind selected"):
        render_pipeline_output_markdown(report)


def test_render_pipeline_output_markdown_apply_mode_reports_insert_success(
    tmp_path: Path,
) -> None:
    """Markdown check apply-mode guidance should report successful insert writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "inserted.py",
        apply_changes=True,
    )
    ctx.status.write = WriteStatus.WRITTEN

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "➕ Adding header in" in output
    assert "inserted.py" in output


def test_render_pipeline_output_markdown_strip_apply_mode_reports_success(
    tmp_path: Path,
) -> None:
    """Markdown strip apply-mode guidance should report successful removals."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "stripped.py",
        pipeline_kind="strip",
        apply_changes=True,
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.REMOVED
    ctx.status.write = WriteStatus.WRITTEN

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "🧹 Stripping header in" in output
    assert "stripped.py" in output


def test_render_pipeline_output_markdown_missing_file_omits_file_type_label(
    tmp_path: Path,
) -> None:
    """Markdown file summaries should omit file-type labels for missing synthetic files."""
    ctx: ProcessingContext = _make_context(tmp_path / "missing.py")
    ctx.file_type = None
    ctx.status.fs = FsStatus.NOT_FOUND
    ctx.status.header = HeaderStatus.PENDING
    ctx.status.comparison = ComparisonStatus.SKIPPED
    ctx.status.plan = PlanStatus.SKIPPED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            report_scope=ReportScope.ALL,
        )
    )

    assert "missing.py` - `" in output
    assert "missing.py` (" not in output


def test_render_pipeline_output_markdown_per_file_omits_empty_diff_block(
    tmp_path: Path,
) -> None:
    """Markdown per-file output should not add a fenced block for an empty retained diff."""
    ctx: ProcessingContext = _make_context(tmp_path / "empty-diff.py")
    ctx.status.patch = PatchStatus.GENERATED
    ctx.views.diff = DiffView(text="")

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_markdown(
        _make_report(
            view_results=reduction.results,
            show_diffs=True,
        )
    )

    assert "empty-diff.py" in output
    assert "```diff" not in output


def test_render_pipeline_apply_summary_markdown_reports_written_without_failures() -> None:
    """Markdown apply summary should omit warning block when all writes succeeded."""
    output: str = render_pipeline_apply_summary_markdown(
        command_path="topmark check",
        written=3,
        failed=0,
    )

    assert "applied changes to **3** file(s)" in output
    assert "failed to write" not in output


def test_render_pipeline_diffs_helpers_return_empty_for_results_without_patches(
    tmp_path: Path,
) -> None:
    """Standalone diff renderers should return an empty payload when no patch renders."""
    ctx: ProcessingContext = _make_context(tmp_path / "no-patch.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    assert render_pipeline_diffs_markdown(results=reduction.results) == ""
    assert render_pipeline_diffs_text(results=reduction.results, styled=False) == ""


def test_render_pipeline_diffs_text_supports_line_numbers(
    tmp_path: Path,
) -> None:
    """Standalone TEXT diff rendering should support optional line numbers."""
    ctx: ProcessingContext = _make_context(tmp_path / "numbered-diff.py")
    _add_diff(ctx)

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_diffs_text(
        results=reduction.results,
        styled=False,
        show_line_numbers=True,
    )

    assert " diff - start " not in output
    assert " diff - end " not in output
    assert "0001|--- old" in output
    assert "0002|+++ new" in output
    assert "0005|+new" in output
    assert "--- old" in output
    assert "+new" in output


def test_render_pipeline_output_text_strip_apply_mode_reports_write_skipped(
    tmp_path: Path,
) -> None:
    """TEXT strip apply-mode guidance should report defensive skipped writes."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "strip-skipped-text.py",
        pipeline_kind="strip",
        apply_changes=True,
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.status.strip = StripStatus.READY
    ctx.status.plan = PlanStatus.REMOVED
    ctx.status.write = WriteStatus.SKIPPED

    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    output: str = render_pipeline_output_text(
        _make_report(
            pipeline_kind="strip",
            view_results=reduction.results,
            apply_changes=True,
        )
    )

    assert "write was skipped" in output
    assert "⚠️  Could not strip header (write skipped)." in output


@pytest.mark.parametrize(
    ("fmt", "is_supported"),
    [
        (OutputFormat.TEXT, True),
        (OutputFormat.MARKDOWN, True),
        (OutputFormat.JSON, False),
        (OutputFormat.NDJSON, False),
        ("bad_format", False),
    ],
)
def test_render_pipeline_command_human_output_accepts_only_human_formats(
    fmt: OutputFormat | str,
    is_supported: bool,
) -> None:
    """Human output facade should accept only human output formats."""
    report = PipelineCommandHumanReport(
        verbosity_level=0,
        styled=False,
        pipeline_kind="check",
        file_list_total=0,
        view_results=[],
        report_scope=ReportScope.ALL,
        unsupported_count=0,
        summary_mode=False,
        show_diffs=False,
        apply_changes=False,
    )

    effective_fmt: OutputFormat = unsupported_output_format(fmt)

    if is_supported:
        render_pipeline_command_human_output(
            report=report,
            results=[],
            fmt=effective_fmt,
        )
        return

    with pytest.raises(
        RuntimeError,
        match=f"Unsupported human output format: {effective_fmt.value}",
    ):
        render_pipeline_command_human_output(
            report=report,
            results=[],
            fmt=effective_fmt,
        )


def test_render_pipeline_command_human_stream_output_matches_batch_text(
    tmp_path: Path,
) -> None:
    """TEXT human output facade should preserve batch output when fed stream events."""
    first_ctx: ProcessingContext = _make_context(tmp_path / "a.py")
    second_ctx: ProcessingContext = _make_context(tmp_path / "b.py")
    second_ctx.status.header = HeaderStatus.DETECTED
    second_ctx.status.comparison = ComparisonStatus.UNCHANGED
    second_ctx.status.plan = PlanStatus.SKIPPED

    reduction: ProcessingReduction = reduce_processing_contexts([first_ctx, second_ctx])
    options: PipelineHumanPresentationOptions = _make_presentation_options(
        verbosity_level=1,
    )
    stream_output: PipelineCommandHumanOutput = render_pipeline_command_human_stream_output(
        options=options,
        events=iter_machine_processing_stream(reduction.results, command="check"),
        fmt=OutputFormat.TEXT,
        would_change=would_add_or_update_result,
    )

    batch_report: PipelineCommandHumanReport = _make_report(
        view_results=(reduction.results[0],),
        file_list_total=2,
        verbosity_level=1,
    )
    batch_output: PipelineCommandHumanOutput = render_pipeline_command_human_output(
        report=batch_report,
        results=reduction.results,
        fmt=OutputFormat.TEXT,
    )

    assert stream_output == batch_output


def test_render_pipeline_command_human_stream_output_matches_batch_markdown_summary_diff(
    tmp_path: Path,
) -> None:
    """Markdown stream output should preserve summary and full diff ordering."""
    first_ctx: ProcessingContext = _make_context(tmp_path / "a.py")
    second_ctx: ProcessingContext = _make_context(tmp_path / "b.py")
    _add_diff(first_ctx)
    _add_diff(second_ctx)

    reduction: ProcessingReduction = reduce_processing_contexts([first_ctx, second_ctx])
    options: PipelineHumanPresentationOptions = _make_presentation_options(
        summary_mode=True,
        show_diffs=True,
    )
    stream_output: PipelineCommandHumanOutput = render_pipeline_command_human_stream_output(
        options=options,
        events=iter_machine_processing_stream(reduction.results, command="check"),
        fmt=OutputFormat.MARKDOWN,
        would_change=would_add_or_update_result,
    )

    batch_report: PipelineCommandHumanReport = _make_report(
        view_results=reduction.results,
        summary_mode=True,
        show_diffs=True,
    )
    batch_output: PipelineCommandHumanOutput = render_pipeline_command_human_output(
        report=batch_report,
        results=reduction.results,
        fmt=OutputFormat.MARKDOWN,
    )

    assert stream_output == batch_output
    assert stream_output.stdout.find("a.py") < stream_output.stdout.find("b.py")


def test_render_pipeline_command_human_stream_output_rejects_bad_order(
    tmp_path: Path,
) -> None:
    """Human stream facade should reject malformed result ordering."""
    ctx: ProcessingContext = _make_context(tmp_path / "bad-order.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    event = MachineProcessingResultEvent(
        command="check",
        index=0,
        result=reduction.results[0],
    )

    with pytest.raises(
        ValueError,
        match="file-result event appeared before run-start",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(event,),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_wrong_command(
    tmp_path: Path,
) -> None:
    """Human stream facade should reject streams for a different command."""
    ctx: ProcessingContext = _make_context(tmp_path / "wrong-command.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])

    with pytest.raises(
        ValueError,
        match="event for a different command",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(pipeline_kind="check"),
            events=iter_machine_processing_stream(reduction.results, command="strip"),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_missing_completion(
    tmp_path: Path,
) -> None:
    """Human stream facade should reject streams without a run-completed event."""
    ctx: ProcessingContext = _make_context(tmp_path / "missing-completion.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )[:-1]

    with pytest.raises(
        ValueError,
        match="missing a run-completed event",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=events,
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_duplicate_start(
    tmp_path: Path,
) -> None:
    """Defensively reject manually assembled streams with duplicate run starts."""
    ctx: ProcessingContext = _make_context(tmp_path / "duplicate-start.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )

    with pytest.raises(
        ValueError,
        match="more than one run-start event",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(events[0], events[0], *events[1:]),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_start_after_completion(
    tmp_path: Path,
) -> None:
    """Defensively reject lifecycle corruption after a completed stream."""
    ctx: ProcessingContext = _make_context(tmp_path / "start-after-completion.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )

    with pytest.raises(
        ValueError,
        match="run-start event appeared after run-completed",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(*events, events[0]),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_result_after_completion(
    tmp_path: Path,
) -> None:
    """Defensively reject file results emitted after completion."""
    ctx: ProcessingContext = _make_context(tmp_path / "result-after-completion.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )

    with pytest.raises(
        ValueError,
        match="file-result event appeared after run-completed",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(*events, events[1]),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_unexpected_index(
    tmp_path: Path,
) -> None:
    """Defensively reject streams whose durable result indexes are not contiguous."""
    ctx: ProcessingContext = _make_context(tmp_path / "bad-index.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )
    bad_result_event = MachineProcessingResultEvent(
        command="check",
        index=2,
        result=reduction.results[0],
    )

    with pytest.raises(
        ValueError,
        match="Expected human presentation file-result index 0, got 2",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(events[0], bad_result_event, events[-1]),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_completion_before_start(
    tmp_path: Path,
) -> None:
    """Defensively reject streams that complete before starting."""
    ctx: ProcessingContext = _make_context(tmp_path / "completion-before-start.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )

    with pytest.raises(
        ValueError,
        match="run-completed event appeared before run-start",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(events[-1],),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_duplicate_completion(
    tmp_path: Path,
) -> None:
    """Defensively reject manually assembled streams with duplicate completions."""
    ctx: ProcessingContext = _make_context(tmp_path / "duplicate-completion.py")
    reduction: ProcessingReduction = reduce_processing_contexts([ctx])
    events: tuple[MachineProcessingStreamEvent, ...] = tuple(
        iter_machine_processing_stream(
            reduction.results,
            command="check",
        )
    )

    with pytest.raises(
        ValueError,
        match="more than one run-completed event",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(*events, events[-1]),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )


def test_render_pipeline_command_human_stream_output_rejects_missing_start(
    tmp_path: Path,
) -> None:
    """Defensively reject empty streams before rendering human output."""
    _make_context(tmp_path / "missing-start.py")

    with pytest.raises(
        ValueError,
        match="missing a run-start event",
    ):
        render_pipeline_command_human_stream_output(
            options=_make_presentation_options(),
            events=(),
            fmt=OutputFormat.TEXT,
            would_change=would_add_or_update_result,
        )
