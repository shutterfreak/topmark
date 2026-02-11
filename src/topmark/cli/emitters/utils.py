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

from topmark.cli.emitters.text.pipeline import (
    emit_pipeline_banner_text,
    emit_pipeline_diffs_text,
    emit_pipeline_per_file_guidance_text,
    emit_pipeline_summary_counts_text,
)
from topmark.cli_shared.emitters.markdown.pipeline import (
    emit_pipeline_diffs_markdown,
    emit_pipeline_per_file_guidance_markdown,
    render_pipeline_banner_markdown,
    render_pipeline_per_file_guidance_markdown,
)
from topmark.config.logging import get_logger
from topmark.constants import TOML_BLOCK_END, TOML_BLOCK_START
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
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

    Args:
        console: Console used for printing.
        cmd: Command name (e.g. "check", "strip").
        file_list_total: Total number of candidate files (before view filtering).
        view_results: Filtered results to render.
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

    # Summary mode
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
                emit_pipeline_per_file_guidance_markdown(
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
        )
    else:
        console.print(
            render_pipeline_per_file_guidance_markdown(
                view_results=view_results,
                make_message=make_message,
                apply_changes=apply_changes,
                show_diffs=show_diffs,
            ),
            nl=False,
        )
