# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/emitters/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI emitter utilities.

Small formatting helpers used by the human-facing CLI emitters.

This module is intentionally lightweight and should not perform configuration discovery, file I/O,
or other command logic. Prefer to keep computation in
[`topmark.cli_shared.emitters.shared`][topmark.cli_shared.emitters.shared] preparers and pass the
results to format-specific emitters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.emitters.text.pipeline import emit_pipeline_banner_text
from topmark.cli.emitters.text.pipeline import emit_pipeline_diffs_text
from topmark.cli.emitters.text.pipeline import emit_pipeline_per_file_guidance_text
from topmark.cli.emitters.text.pipeline import emit_pipeline_summary_counts_text
from topmark.cli.keys import CliOpt
from topmark.cli.reporting import ReportScope
from topmark.cli_shared.emitters.markdown.pipeline import emit_pipeline_diffs_markdown
from topmark.cli_shared.emitters.markdown.pipeline import render_pipeline_banner_markdown
from topmark.cli_shared.emitters.markdown.pipeline import render_pipeline_per_file_guidance_markdown
from topmark.cli_shared.emitters.markdown.pipeline import render_pipeline_summary_counts_markdown
from topmark.cli_shared.emitters.shared.pipeline import markdown_code_span
from topmark.constants import TOML_BLOCK_END
from topmark.constants import TOML_BLOCK_START
from topmark.core.formats import OutputFormat
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext


logger: TopmarkLogger = get_logger(__name__)

# Config helpers


def emit_toml_block(
    *,
    console: ConsoleLike,
    title: str,
    toml_text: str,
    verbosity_level: int,
) -> None:
    """Emit a TOML snippet with optional banner and BEGIN/END markers.

    Used by config commands in the default (ANSI) output format.

    Args:
        console: Console instance for printing styled output.
        title: Title line shown above the block when verbosity > 0.
        toml_text: The TOML content to render.
        verbosity_level: Effective verbosity; 0 disables banners.
    """
    if verbosity_level > 0:
        console.print(
            console.styled(
                title,
                bold=True,
                underline=True,
            )
        )
        console.print(
            console.styled(
                TOML_BLOCK_START,
                fg="cyan",
                dim=True,
            )
        )

    console.print(
        console.styled(
            toml_text,
            fg="cyan",
        )
    )

    if verbosity_level > 0:
        console.print(
            console.styled(
                TOML_BLOCK_END,
                fg="cyan",
                dim=True,
            )
        )


# Pipeline command helpers (check/strip)


def emit_pipeline_human_output(
    *,
    console: ConsoleLike,
    cmd: str,
    file_list_total: int,
    view_results: list[ProcessingContext],
    report: ReportScope,
    unsupported_count: int,
    fmt: OutputFormat,
    verbosity_level: int,
    summary_mode: bool,
    show_diffs: bool,
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
    enable_color: bool,
) -> None:
    """Emit human-facing output for pipeline commands.

    This unifies TEXT (ANSI) and MARKDOWN output for pipeline-oriented
    commands like `check` and `strip`.

    Notes:
        This helper only supports `TEXT` and `MARKDOWN`.

    Args:
        console: Console used for printing.
        cmd: Command name (e.g. "check", "strip").
        file_list_total: Total number of candidate files (before view filtering).
        view_results: Filtered results to render.
        report: Controls which per-file entries are rendered for human output.
        unsupported_count: Unsupported file count.
        fmt: Human output format.
        verbosity_level: Effective verbosity for gating banners/details.
        summary_mode: If True, show outcome counts only.
        show_diffs: If True, render unified diffs (human formats only).
        make_message: Per-file guidance message factory.
        apply_changes: Whether changes are being applied (vs dry-run).
        enable_color: Whether ANSI output should be colorized.

    Raises:
        ValueError: When an unsupported human output format was provided.
    """
    if fmt not in (OutputFormat.TEXT, OutputFormat.MARKDOWN):
        raise ValueError(f"Unsupported human output format: {fmt}")

    # Banner (verbosity-gated)
    if verbosity_level > 0:
        if fmt == OutputFormat.TEXT:
            emit_pipeline_banner_text(cmd=cmd, n_files=file_list_total)
        else:
            console.print(render_pipeline_banner_markdown(cmd=cmd, n_files=file_list_total))
            console.print()

    # Summary mode (grouped by `(outcome, reason)`)
    if summary_mode:
        if show_diffs:
            if fmt == OutputFormat.TEXT:
                emit_pipeline_diffs_text(results=view_results, color=enable_color)
            else:
                console.print(emit_pipeline_diffs_markdown(results=view_results))
        if fmt == OutputFormat.TEXT:
            emit_pipeline_summary_counts_text(view_results=view_results, total=file_list_total)
        else:
            console.print(
                render_pipeline_summary_counts_markdown(
                    view_results=view_results,
                    total=file_list_total,
                )
            )
        return

    # Per-file guidance
    if fmt == OutputFormat.TEXT:
        emit_pipeline_per_file_guidance_text(
            view_results=view_results,
            make_message=make_message,
            apply_changes=apply_changes,
            show_diffs=show_diffs,
            verbosity_level=verbosity_level,
            color=enable_color,
        )
    else:
        console.print(
            render_pipeline_per_file_guidance_markdown(
                view_results=view_results,
                make_message=make_message,
                apply_changes=apply_changes,
                show_diffs=show_diffs,
                verbosity_level=verbosity_level,
            ),
            nl=False,
        )

    # In actionable mode, unsupported files are hidden from the per-file listing but summarized
    # for visibility.
    if (not summary_mode) and (report == ReportScope.ACTIONABLE) and (unsupported_count > 0):
        emit_pipeline_hidden_unsupported_footer_human(
            console=console,
            fmt=fmt,
            unsupported_count=unsupported_count,
        )


def emit_pipeline_hidden_unsupported_footer_human(
    *,
    console: ConsoleLike,
    fmt: OutputFormat,
    unsupported_count: int,
) -> None:
    """Emit the footer after a pipeline 'apply' command."""
    if fmt == OutputFormat.TEXT:
        console.print(
            console.styled(
                f"⚠️  Unsupported: {unsupported_count} file(s) "
                f"(use {CliOpt.REPORT}={ReportScope.NONCOMPLIANT.value} to list)",
                fg="yellow",
            )
        )
    elif fmt == OutputFormat.MARKDOWN:
        console.print(
            f"\n> ⚠️ Unsupported: {unsupported_count} file(s) "
            f"(use {CliOpt.REPORT}={ReportScope.NONCOMPLIANT.value} to list)\n"
        )


def emit_pipeline_apply_summary_human(
    *,
    console: ConsoleLike,
    fmt: OutputFormat,
    command_path: str,
    written: int,
    failed: int,
) -> None:
    """Emit a short human-facing apply summary footer.

    This is only for human formats (TEXT/MARKDOWN). Machine formats must never emit
    human summaries.

    Args:
        console: Console used for printing.
        fmt: Human output format (TEXT or MARKDOWN).
        command_path: Command path (e.g. "topmark check", "topmark strip").
        written: Number of files written.
        failed: Number of files that failed to write.
    """
    if fmt not in (OutputFormat.TEXT, OutputFormat.MARKDOWN):
        return

    if fmt == OutputFormat.TEXT:
        if written:
            msg: str = f"\n✅ {command_path}: applied changes to {written} file(s)."
        else:
            msg = f"\n✅ {command_path}: no changes to apply."
        console.print(console.styled(msg, fg="green", bold=True))
        if failed:
            console.print(
                console.styled(
                    f"\n⚠️ {command_path}: failed to write {failed} file(s). See log for details.",
                    fg="yellow",
                    bold=True,
                )
            )
        return

    # MARKDOWN
    cmd_md: str = markdown_code_span(command_path)
    if written:
        console.print(f"\n✅ {cmd_md}: applied changes to **{written}** file(s).\n")
    else:
        console.print(f"\n✅ {cmd_md}: no changes to apply.\n")
    if failed:
        console.print(
            f"\n> ⚠️ {cmd_md}: failed to write **{failed}** file(s). See log for details.\n"
        )
