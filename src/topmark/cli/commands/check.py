# topmark:header:start
#
#   project      : TopMark
#   file         : check.py
#   file_relpath : src/topmark/cli/commands/check.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Default TopMark operation (check/apply).

Checks whether the TopMark header is present, needs updating or complies.
Performs a dry‑run check by default and applies changes when ``--apply`` is given.

Input modes supported:
  * **Paths mode (default)**: one or more PATHS and/or ``--files-from FILE``.
  * **Content on STDIN**: a single ``-`` as the sole PATH **plus** ``--stdin-filename NAME``.
  * **Lists on STDIN for ...-from**: allow ``--files-from -``, ``--include-from -``,
    or ``--exclude-from -`` (exactly one may consume STDIN).

Examples:
  Check files and print a human summary:

    $ topmark check --summary src

  Emit per‑file objects in NDJSON (one per line):

    $ topmark check --output-format=ndjson src pkg

  Write changes and show diffs (human output only):

    $ topmark check --apply --diff .

  Read a *single file's content* from STDIN:

    $ cat foo.py | topmark check - --stdin-filename foo.py

  Read a *list of paths* from STDIN:

    $ git ls-files | topmark check --files-from -
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.api.runtime import select_pipeline
from topmark.cli.cmd_common import build_config_for_plan
from topmark.cli.cmd_common import build_file_list
from topmark.cli.cmd_common import exit_if_no_files
from topmark.cli.cmd_common import init_common_state
from topmark.cli.cmd_common import maybe_exit_on_error
from topmark.cli.cmd_common import maybe_route_console_to_stderr
from topmark.cli.emitters.machine import emit_processing_results_machine
from topmark.cli.errors import TopmarkCliIOError
from topmark.cli.io import plan_cli_inputs
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import PATH_COMMAND_CONTEXT_SETTINGS
from topmark.cli.options import check_policy_options
from topmark.cli.options import common_apply_and_write_options
from topmark.cli.options import common_config_resolution_options
from topmark.cli.options import common_file_filtering_options
from topmark.cli.options import common_file_type_filtering_options
from topmark.cli.options import common_from_sources_options
from topmark.cli.options import common_header_formatting_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_stdin_content_mode_options
from topmark.cli.options import common_ui_options
from topmark.cli.options import pipeline_reporting_options
from topmark.cli.options import render_diff_options
from topmark.cli.reporting import ReportScope
from topmark.cli.reporting import filter_results_for_report
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import validate_check_add_update_policy_exclusivity
from topmark.cli.validators import validate_diff_policy_for_output_format
from topmark.cli.validators import validate_stdin_dash_requires_piped_input
from topmark.cli.validators import warn_if_report_scope_ignored
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.core.logging import get_logger
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.status import WriteStatus
from topmark.presentation.shared.pipeline import check_msg_markdown
from topmark.presentation.shared.pipeline import check_msg_text
from topmark.presentation.shared.pipeline import render_pipeline_apply_summary_human
from topmark.presentation.shared.pipeline import render_pipeline_human_output
from topmark.presentation.text.diagnostic import render_diagnostics_text
from topmark.utils.file import safe_unlink

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.io import InputPlan
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CHECK,
    context_settings=PATH_COMMAND_CONTEXT_SETTINGS,
    help="Validate headers (dry-run). Use --apply to add or update.",
    epilog=f"""\
Adds or updates TopMark header blocks in files (in-place with {CliOpt.APPLY_CHANGES}).
Examples:

  # Preview which files would change (dry-run)
  topmark {CliCmd.CHECK} src

  # Apply: remove headers in-place
  topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} .
""",
)
@common_ui_options
@common_config_resolution_options
@common_stdin_content_mode_options
@common_from_sources_options
@common_file_filtering_options
@common_file_type_filtering_options
@check_policy_options
@common_apply_and_write_options
@render_diff_options
@pipeline_reporting_options
@common_header_formatting_options
@common_output_format_options
def check_command(
    *,
    # common_ui_options (verbosity, color):
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # common_config_resolution_options:
    no_config: bool,
    config_files: list[str],
    # common_stdin_content_mode_options:
    stdin_filename: str | None,
    # common_from_sources_options:
    files_from: list[str],
    include_from: list[str],
    exclude_from: list[str],
    # common_file_filtering_options:
    include_patterns: list[str],
    exclude_patterns: list[str],
    # common_file_type_filtering_options:
    include_file_types: list[str],
    exclude_file_types: list[str],
    # check_policy_options:
    add_only: bool,
    update_only: bool,
    # common_apply_and_write_options
    apply_changes: bool,
    write_mode: str | None,
    # render_diff_options:
    diff: bool,
    # pipeline_reporting_options
    summary_mode: bool,
    report: ReportScope,
    # common_header_formatting_options:
    align_fields: bool,
    relative_to: str | None,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Run the unified default command (check/apply).

    The command receives options parsed at the group level and reads positional
    paths from ``click.get_current_context().args`` (Black‑style). It supports
    three input styles:

    1. Paths mode (default): PATHS and/or ``--files-from FILE``.
    2. Content-on-STDIN: use ``-`` as the sole PATH **and** provide ``--stdin-filename``.
    3. Lists-on-STDIN for one of the "...-from" options: ``--files-from -``,
       ``--include-from -``, or ``--exclude-from -`` (exactly one may consume STDIN).

    Args:
        verbose: Incements the verbosity level,
        quiet: Decrements  the verbosity level,
        color_mode: Set the color mode (derfault: autp),
        no_color: bool: If set, disable color mode.
        no_config: If True, skip loading project/user configuration files.
        config_files: Additional configuration file paths to load and merge.
        stdin_filename: Assumed filename when  reading content from STDIN).
        files_from: Files that contain newline‑delimited *paths* to add to the
            candidate set before filtering. Use ``-`` to read from STDIN.
        include_from: Files that contain include glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        exclude_from: Files that contain exclude glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        include_patterns: Glob patterns to *include* (intersection).
        exclude_patterns: Glob patterns to *exclude* (subtraction).
        include_file_types: Restrict processing to the given file type identifiers.
        exclude_file_types: Exclude processing for the given file type identifiers.
        add_only: Only add headers where missing (no updates).
        update_only: Only update existing non‑compliant headers (no additions).
        apply_changes: Write changes to files; otherwise perform a dry run.
        write_mode: Whether to use safe atomic writing, faster in-place writing
            or writing to STDOUT (default: atomic writer).
        diff: Show unified diffs of header changes (human output only).
        summary_mode: Show outcome counts instead of per‑file details.
        report: Reporting scope for human per-file output (`actionable`, `noncompliant`, `all`).
            Ignored for summary mode and machine-readable formats.
        align_fields: Whether to align header fields when rendering (captured in config).
        relative_to: Base path used only for resolving header metadata (e.g., `file_relpath`).
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        TopmarkCliIOError: If an I/O error occurred (read/write).

    Exit Status:
        SUCCESS (0): No changes required or all requested changes were written.
        WOULD_CHANGE (2): Dry‑run detected files that would change with ``--apply``.
        USAGE_ERROR (64): Invalid invocation (e.g., mixing ``-`` with ``--files-from -``).
        FILE_NOT_FOUND (66): One or more specified files or directories could not be found.
        PERMISSION_DENIED (77): Insufficient permissions to read or write a file.
        ENCODING_ERROR (65): A file could not be decoded or encoded with the expected encoding.
        IO_ERROR (74): An unexpected I/O failure occurred while writing changes.
        PIPELINE_ERROR (70): An internal processing step failed.
        UNEXPECTED_ERROR (255): An unhandled error occurred.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)

    # Initialize the common state (verbosity, color mode) and initialize console
    init_common_state(
        ctx,
        verbose=verbose,
        quiet=quiet,
        color_mode=color_mode,
        no_color=no_color,
    )

    # Retrieve effective human facing program-output verbosity for gating extra details
    verbosity_level: int = ctx.obj[ArgKey.VERBOSITY_LEVEL]

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    # Output format
    fmt: OutputFormat = output_format or OutputFormat.TEXT

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = ctx.obj[ArgKey.COLOR_ENABLED]

    # common_from_sources_options - Fail fast if a `--*-from -` option is used without piped STDIN.
    validate_stdin_dash_requires_piped_input(
        ctx,
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
    )

    validate_diff_policy_for_output_format(ctx, diff=diff, fmt=fmt)

    validate_check_add_update_policy_exclusivity(ctx, add_only=add_only, update_only=update_only)

    warn_if_report_scope_ignored(
        ctx,
        output_format=output_format or OutputFormat.TEXT,
        summary_mode=summary_mode,
        report=report,
    )

    prune_override: bool | None = ctx.obj.get(
        "prune"
    )  # injected by tests via CliRunner.invoke(..., obj=...)
    prune: bool = bool(prune_override) if prune_override else False

    # Add apply_changes and write_mode to Click context
    ctx.obj[ArgKey.APPLY_CHANGES] = apply_changes
    ctx.obj[ArgKey.WRITE_MODE] = write_mode

    # === Build Config (layered discovery) and file list ===
    plan: InputPlan = plan_cli_inputs(
        ctx=ctx,
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        stdin_filename=stdin_filename,
    )

    # Content-to-STDOUT modes: keep stdout clean for the rewritten file content.
    #
    # - STDIN content mode emits the updated file to stdout when --apply is set.
    # - write_mode="stdout" also emits updated content to stdout.
    #
    # In both cases, route all human-facing console output (summaries, warnings,
    # diagnostics) to stderr.
    #
    # Console selection must happen after planning inputs because stdin mode affects routing.
    console: ConsoleProtocol = maybe_route_console_to_stderr(
        ctx,
        enable_color=enable_color,
        apply_changes=apply_changes,
        stdin_mode=plan.stdin_mode,
        write_mode=write_mode,
    )

    draft_config: MutableConfig = build_config_for_plan(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_files,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        align_fields=align_fields,
        relative_to=relative_to,
    )

    # Propagate runtime intent for updater (terminal vs preview write status)
    draft_config.apply_changes = bool(apply_changes)

    config: Config = draft_config.freeze()

    logger.trace("Config after merging args and resolving file list: %s", config)

    # Display Config diagnostics before resolving files
    if fmt == OutputFormat.TEXT and verbosity_level > 0:
        console.print(
            render_diagnostics_text(
                diagnostics=config.diagnostics,
                verbosity_level=verbosity_level,
                color=enable_color,
            )
        )

    temp_path: Path | None = plan.temp_path  # for cleanup/STDIN-apply branch
    stdin_mode: bool = plan.stdin_mode
    file_list: list[Path] = build_file_list(
        config,
        stdin_mode=stdin_mode,
        temp_path=temp_path,
    )

    # Use Click's text stream for stdin so CliRunner/invoke input is read reliably
    # stdin_stream = click.get_text_stream("stdin") if stdin_text else None

    if exit_if_no_files(file_list):
        # Nothing to do
        return

    # Choose the concrete pipeline variant
    pipeline: Sequence[Step[ProcessingContext]] = select_pipeline(
        "check",
        apply=apply_changes,
        diff=diff,
    )

    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None = None

    results, encountered_error_code = run_steps_for_files(
        file_list=file_list,
        pipeline=pipeline,
        config=config,
        prune=prune,
    )

    # Report scope is a human per-file listing policy only.
    #
    # - Machine output must always use the full raw result set.
    # - Human summary mode must also use the full raw result set so aggregated
    #   counts are not distorted by per-file report filtering.
    # - Human non-summary output uses the filtered per-file view.
    view_results, unsupported_count = filter_results_for_report(
        results,
        report=report,
        would_change=effective_would_add_or_update,
    )

    human_results: list[ProcessingContext] = results if summary_mode else view_results

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_processing_results_machine(
            meta=meta,
            config=config,
            results=results,
            fmt=fmt,
            summary_mode=summary_mode,
        )
    else:
        console.print(
            render_pipeline_human_output(
                cmd=CliCmd.CHECK,
                file_list_total=len(file_list),
                view_results=human_results,
                report=report,
                unsupported_count=unsupported_count,
                fmt=fmt,
                verbosity_level=verbosity_level,
                summary_mode=summary_mode,
                show_diffs=diff,
                make_message=check_msg_markdown if fmt == OutputFormat.MARKDOWN else check_msg_text,
                apply_changes=apply_changes,
                enable_color=enable_color,
            )
        )

    if apply_changes:
        # Writes (only when --apply is set)
        if stdin_mode:
            # For STDIN content mode, the modified file content is emitted to stdout in WriterStep.
            # So we do not have to output it here.
            #
            # Cleanup the temp file
            safe_unlink(temp_path)
            return
        else:
            # Count outcomes after the pipeline writer step finalized statuses.
            written: int = sum(1 for r in results if r.status.write == WriteStatus.WRITTEN)
            failed: int = sum(1 for r in results if r.status.write == WriteStatus.FAILED)

            console.print(
                render_pipeline_apply_summary_human(
                    fmt=fmt,
                    command_path=ctx.command_path,
                    written=written,
                    failed=failed,
                    styled=enable_color,
                )
            )

            if failed:
                raise TopmarkCliIOError(f"Failed to write {failed} file(s). See log for details.")

    else:
        # Dry-run: determine exit code
        if any(effective_would_add_or_update(r) for r in results):
            ctx.exit(ExitCode.WOULD_CHANGE)

    # Exit on any error encountered during processing
    maybe_exit_on_error(
        code=encountered_error_code,
        temp_path=temp_path,
    )

    # Cleanup temp file if any (shouldn't be needed except on errors)
    if temp_path and temp_path.exists():
        safe_unlink(temp_path)

    # No explicit return needed for Click commands.
