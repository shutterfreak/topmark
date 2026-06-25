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

from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import unsupported_output_format
from tests.helpers.registry import make_file_type
from tests.presentation.conftest import find_table_row
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.formats import OutputFormat
from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.hints import make_hint
from topmark.pipeline.reduction import ProcessingReduction
from topmark.pipeline.reduction import reduce_processing_contexts
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import PatchStatus
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.views import DiffView
from topmark.presentation.markdown.paths import render_path_display_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_apply_summary_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_output_markdown
from topmark.presentation.output.pipeline import render_pipeline_command_human_output
from topmark.presentation.shared.paths import get_display_path
from topmark.presentation.shared.paths import render_path_display_text
from topmark.presentation.shared.pipeline import PipelineCommandHumanReport
from topmark.presentation.shared.pipeline import get_file_type_label
from topmark.presentation.text.pipeline import render_pipeline_apply_summary_text
from topmark.presentation.text.pipeline import render_pipeline_output_text
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.result import ProcessingResult


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


def _add_diff(ctx: ProcessingContext) -> None:
    """Attach a deterministic unified diff to a context."""
    ctx.status.patch = PatchStatus.GENERATED
    ctx.views.diff = DiffView(text="--- old\n+++ new\n@@ -1 +1 @@\n-old\n+new\n")


def test_render_path_display_text_uses_regular_display_path(tmp_path: Path) -> None:
    """TEXT path labels should quote regular display paths without STDIN annotation."""
    ctx: ProcessingContext = _make_context(tmp_path / "regular.py")

    assert render_path_display_text(ctx) == f"'{ctx.path}'"


def test_render_path_display_text_uses_stdin_filename(tmp_path: Path) -> None:
    """TEXT path labels should show the logical stdin filename in STDIN mode."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "materialized-stdin.py",
        stdin_mode=True,
        stdin_filename="logical/input.py",
    )

    assert render_path_display_text(ctx) == "'logical/input.py' (via STDIN)"


def test_render_path_display_markdown_uses_regular_display_path(tmp_path: Path) -> None:
    """Markdown path labels should render regular display paths as code spans."""
    ctx: ProcessingContext = _make_context(tmp_path / "regular.py")

    assert render_path_display_markdown(ctx) == f"`{ctx.path}`"


def test_render_path_display_markdown_uses_stdin_filename(tmp_path: Path) -> None:
    """Markdown path labels should show the logical stdin filename in STDIN mode."""
    ctx: ProcessingContext = _make_context(
        tmp_path / "materialized-stdin.py",
        stdin_mode=True,
        stdin_filename="logical/input.py",
    )

    assert render_path_display_markdown(ctx) == "`logical/input.py` _(via STDIN)_"


def test_shared_display_path_uses_stdin_filename_for_stdin_context(tmp_path: Path) -> None:
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


def test_render_pipeline_output_text_compact_check_guidance(tmp_path: Path) -> None:
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


def test_render_pipeline_output_text_summary_with_diff_section(tmp_path: Path) -> None:
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


def test_render_pipeline_output_markdown_summary_table_and_total(tmp_path: Path) -> None:
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


def test_render_pipeline_output_markdown_summary_diff_section(tmp_path: Path) -> None:
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


def test_pipeline_renderers_reject_invalid_pipeline_kind(tmp_path: Path) -> None:
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
