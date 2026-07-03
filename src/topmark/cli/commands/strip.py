# topmark:header:start
#
#   project      : TopMark
#   file         : strip.py
#   file_relpath : src/topmark/cli/commands/strip.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `strip` command.

Removes the entire TopMark header from targeted files.
Performs a dry-run check by default and applies changes when ``--apply`` is given.

Input modes supported:
  • **Paths mode (default)**: one or more PATHS and/or ``--files-from FILE``.
  • **Content on STDIN**: a single ``-`` as the sole PATH **plus** ``--stdin-filename NAME``.
  • **Lists on STDIN for ...-from**: allow ``--files-from -``, ``--include-from -``,
  or ``--exclude-from -`` (exactly one may consume STDIN).

Output model:
  * TEXT output is console-oriented and may use ``-v`` / ``--quiet``.
  * Markdown output is document-oriented and ignores TEXT-only verbosity/quiet controls.
  * JSON/NDJSON output is machine-readable and uses the full raw result set.

Examples:
  Preview changes (dry-run):

    $ topmark strip src

  Apply changes (write in place):

    $ topmark strip --apply .

  Read a *single file's content* from STDIN:

    $ cat with_header.py | topmark strip - --stdin-filename with_header.py

  Read a *list of paths* from STDIN:

    $ git ls-files | topmark strip --files-from -
"""

from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

import click
import rich_click

from topmark.api.runtime import ensure_config_valid
from topmark.cli.cmd_common import build_file_resolution
from topmark.cli.cmd_common import build_resolved_toml_sources_and_config_for_plan
from topmark.cli.cmd_common import build_run_options
from topmark.cli.cmd_common import exit_for_config_validation_error
from topmark.cli.cmd_common import exit_if_no_files
from topmark.cli.cmd_common import init_common_state
from topmark.cli.cmd_common import maybe_exit_on_error
from topmark.cli.cmd_common import resolve_human_console
from topmark.cli.emitters.machine import emit_processing_stream_json_machine
from topmark.cli.emitters.machine import emit_processing_stream_machine
from topmark.cli.help import HelpExample
from topmark.cli.help import render_examples_epilog
from topmark.cli.io import plan_cli_inputs
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.options import PATH_COMMAND_CONTEXT_SETTINGS
from topmark.cli.options import common_apply_and_write_options
from topmark.cli.options import common_color_options
from topmark.cli.options import common_config_resolution_options
from topmark.cli.options import common_file_filtering_options
from topmark.cli.options import common_file_type_filtering_options
from topmark.cli.options import common_files_from_options
from topmark.cli.options import common_include_exclude_from_options
from topmark.cli.options import common_output_format_options
from topmark.cli.options import common_stdin_content_mode_options
from topmark.cli.options import common_text_output_quiet_options
from topmark.cli.options import common_text_output_verbosity_options
from topmark.cli.options import config_strict_options
from topmark.cli.options import pipeline_reporting_options
from topmark.cli.options import render_diff_options
from topmark.cli.options import shared_policy_options
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.streaming import ProcessingStreamStats
from topmark.cli.streaming import emit_stdout_payload
from topmark.cli.streaming import iter_cli_processing_stream
from topmark.cli.streaming import observe_processing_stream
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import validate_diff_apply_mutual_exclusion
from topmark.cli.validators import validate_stdin_dash_requires_piped_input
from topmark.cli.validators import warn_if_machine_summary_diff_ignored
from topmark.cli.validators import warn_if_report_scope_ignored
from topmark.config.policy import MutablePolicy
from topmark.core.errors import ConfigValidationError
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.logging import get_logger
from topmark.core.machine.payloads import build_meta_payload
from topmark.pipeline.engine import PipelineExecutionState
from topmark.pipeline.engine import iter_steps_for_files
from topmark.pipeline.pipelines import select_pipeline
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.reporting import would_strip_result
from topmark.pipeline.synthetic import build_missing_file_contexts
from topmark.presentation.markdown.diagnostic import render_diagnostics_markdown
from topmark.presentation.markdown.pipeline import render_pipeline_apply_summary_markdown
from topmark.presentation.markdown.version import render_version_footer_markdown
from topmark.presentation.output.pipeline import render_pipeline_command_human_stream_output
from topmark.presentation.shared.pipeline import PipelineCommandHumanOutput
from topmark.presentation.shared.pipeline import PipelineHumanPresentationOptions
from topmark.presentation.text.diagnostic import render_diagnostics_text
from topmark.presentation.text.pipeline import render_pipeline_apply_summary_text
from topmark.utils.file import safe_unlink

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.cli.cmd_common import PreparedCliConfig
    from topmark.cli.console.color import ColorMode
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.io import InputPlan
    from topmark.config.model import FrozenConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.machine.streaming import MachineProcessingStreamEvent
    from topmark.pipeline.pipelines import PipelineSelection
    from topmark.resolution.files import FileListResolution
    from topmark.runtime.model import RunOptions


logger: TopmarkLogger = get_logger(__name__)


@rich_click.command(
    name=CliCmd.STRIP,
    context_settings=PATH_COMMAND_CONTEXT_SETTINGS,
    help=(
        f"Preview header removal (dry-run), or remove TopMark headers with {CliOpt.APPLY_CHANGES}."
    ),
    epilog=render_examples_epilog(
        examples=(
            HelpExample(
                summary="Preview which files would change (dry-run)",
                command_line=f"topmark {CliCmd.STRIP} src",
            ),
            HelpExample(
                summary="Remove headers in-place (apply):",
                command_line=f"topmark {CliCmd.STRIP} {CliOpt.APPLY_CHANGES} .",
            ),
        ),
    ),
)
@click.argument("paths", nargs=-1, type=click.UNPROCESSED)
@common_color_options
@common_text_output_verbosity_options
@common_text_output_quiet_options
@config_strict_options
@common_config_resolution_options
@common_stdin_content_mode_options
@common_files_from_options
@common_include_exclude_from_options
@common_file_filtering_options
@common_file_type_filtering_options
@shared_policy_options
@common_apply_and_write_options
@render_diff_options
@pipeline_reporting_options
@common_output_format_options
def strip_command(
    paths: tuple[str, ...],
    *,
    # common_ui_options (verbosity, color):
    verbosity: int,
    quiet: bool,
    color_mode: ColorMode | None,
    no_color: bool,
    # config_strict_options:
    strict: bool | None,
    # common_config_resolution_options:
    no_config: bool,
    config_files: list[str],
    # common_stdin_content_mode_options:
    stdin_filename: str | None,
    # common_files_from_options:
    files_from: list[str],
    # common_include_exclude_from_options:
    include_from: list[str],
    exclude_from: list[str],
    # common_file_filtering_options:
    include_patterns: list[str],
    exclude_patterns: list[str],
    # common_file_type_filtering_options:
    include_file_types: list[str],
    exclude_file_types: list[str],
    # policy_options (shared):
    allow_content_probe: bool | None,
    # common_apply_and_write_options
    apply_changes: bool,
    write_mode: str | None,
    # render_diff_options:
    diff: bool,
    # pipeline_reporting_options
    summary_mode: bool,
    report_scope: ReportScope,
    # common_output_format_options:
    output_format: OutputFormat | None,
) -> None:
    """Remove the TopMark header block from targeted files.

    The command receives Click-parsed positional paths and reuses the standard
    config resolver and file selection logic. It supports three input styles:

    1. Paths mode (default): PATHS and/or ``--files-from FILE``.
    2. Content-on-STDIN: use ``-`` as the sole PATH **and** provide ``--stdin-filename``.
    3. Lists-on-STDIN for one of the "...-from" options: ``--files-from -``,
       ``--include-from -``, or ``--exclude-from -`` (exactly one may consume STDIN).

    Only shared policy options apply to `strip`. Header insertion/update policy
    options are intentionally not exposed for this command.

    Args:
        paths: Positional paths parsed by Click. Use ``--`` before literal
            path names that begin with a dash.
        verbosity: Increase TEXT output detail.
        quiet: Suppress TEXT output.
        color_mode: Set the color mode (default: auto).
        no_color: bool: If set, disable color mode.
        strict: if True, report warnings as errors.
        no_config: If True, skip loading project/user configuration files.
        config_files: Additional configuration file paths to load and merge.
        stdin_filename: Assumed filename when reading content from STDIN).
        files_from: Files that contain newline-delimited *paths* to add to the
            candidate set before filtering. Use ``-`` to read from STDIN.
        include_from: Files that contain include glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        exclude_from: Files that contain exclude glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        include_patterns: Glob patterns to *include* (intersection).
        exclude_patterns: Glob patterns to *exclude* (subtraction).
        include_file_types: Restrict processing to the given file type identifiers.
        exclude_file_types: Exclude processing for the given file type identifiers.
        allow_content_probe: Shared policy override controlling whether
            file-type detection may consult file contents when needed.
        apply_changes: Write changes to files; otherwise perform a dry run.
        write_mode: Whether to use safe atomic writing, faster in-place writing
            or writing to STDOUT (default: atomic writer).
        diff: Show unified diffs of header removals (human output only).
        summary_mode: Show outcome counts instead of per-file details.
        report_scope: Reporting scope for human per-file output (`actionable`, `noncompliant`,
            `all`). Ignored for summary mode and machine-readable formats.
        output_format: Output format to use (``text``, ``markdown``, ``json``, or ``ndjson``).
            Verbosity and quiet controls apply only to TEXT output.

    Exit Status:
        SUCCESS (0): No changes required or all requested changes were written.
        WOULD_CHANGE (3): Dry-run detected files that would change with ``--apply``.
        USAGE_ERROR (64): Invalid invocation (e.g., mixing ``-`` with ``--files-from -``).
        FILE_NOT_FOUND (66): One or more specified files or directories could not be found.
        PERMISSION_DENIED (77): Insufficient permissions to read or write a file.
        ENCODING_ERROR (65): A file could not be decoded or encoded with the expected encoding.
        IO_ERROR (74): An unexpected I/O failure occurred while writing changes.
        PIPELINE_ERROR (70): An internal processing step failed.
        UNEXPECTED_ERROR (255): An unhandled error occurred.
    """
    PIPELINE_KIND: PipelineKindLiteral = "strip"
    ctx: click.Context = click.get_current_context()
    ctx.args = list(paths)
    state: TopmarkCliState = bootstrap_cli_state(ctx)
    # Effective output format (stored early so shared initialization sees it).
    state.output_format = output_format or OutputFormat.TEXT

    # Initialize typed CLI state (TEXT verbosity/quiet, color mode, console).
    init_common_state(
        ctx,
        verbosity=verbosity,
        quiet=quiet,
        color_mode=color_mode,
        no_color=no_color,
    )

    # Effective TEXT verbosity for console-oriented progressive disclosure.
    verbosity_level: int = state.verbosity

    # Machine metadata.
    meta: MetaPayload = build_meta_payload()

    # Effective output format.
    fmt: OutputFormat = state.output_format

    apply_color_policy_for_output_format(ctx, fmt=fmt)
    enable_color: bool = state.color_enabled

    # common_from_sources_options - Fail fast if a `--*-from -` option is used without piped STDIN.
    validate_stdin_dash_requires_piped_input(
        ctx,
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
    )

    validate_diff_apply_mutual_exclusion(ctx, diff=diff, apply_changes=apply_changes)

    warn_if_report_scope_ignored(
        ctx,
        output_format=output_format or OutputFormat.TEXT,
        summary_mode=summary_mode,
        report_scope=report_scope,
    )

    warn_if_machine_summary_diff_ignored(
        ctx,
        output_format=output_format or OutputFormat.TEXT,
        summary_mode=summary_mode,
        diff=diff,
    )

    # Test harnesses may inject this via
    # `CliRunner.invoke(..., obj=TopmarkCliState(prune_pipeline_views=True))`.
    prune_views: bool = state.prune_pipeline_views

    # Store command-scoped runtime values in typed state:
    state.apply_changes = apply_changes
    state.write_mode = write_mode

    # Store policy option values for ConfigOverrides construction.
    state.policy = MutablePolicy(
        allow_content_probe=allow_content_probe,
    )

    # Build layered config, runtime options, and file list.
    plan: InputPlan = plan_cli_inputs(
        ctx=ctx,
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        stdin_filename=stdin_filename,
    )

    prepared_cli_config: PreparedCliConfig = build_resolved_toml_sources_and_config_for_plan(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_files,
        strict=strict,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        align_fields=None,  # Not relevant for `strip``
        relative_to=None,  # Not relevant for `strip``
    )

    # Select the concrete pipeline variant.
    pipeline: PipelineSelection = select_pipeline(
        PIPELINE_KIND,
        apply=apply_changes,
        diff=diff,
    )

    run_options: RunOptions = build_run_options(
        pipeline=pipeline,
        write_mode=write_mode,
        stdin_mode=plan.stdin_mode,
        stdin_filename=plan.stdin_filename,
        prune_views=prune_views,
    )

    logger.debug("run options: %s", run_options)

    # Content-to-STDOUT modes: keep stdout clean for the rewritten file content.
    #
    # - STDIN content mode emits the updated file to stdout when --apply is set.
    # - write_mode="stdout" also emits updated content to stdout.
    #
    # In both cases, route all human-facing console output (summaries, warnings,
    # diagnostics) to stderr.
    #
    # Console selection must happen after planning inputs because stdin mode affects routing.
    machine_console: ConsoleProtocol = state.console
    console: ConsoleProtocol = resolve_human_console(
        ctx,
        run_options=run_options,
        enable_color=enable_color,
    )

    config: FrozenConfig = prepared_cli_config.draft.freeze()

    logger.trace("Run config after layered CLI overrides: %s", config)

    # Validate the effective configuration.
    try:
        ensure_config_valid(
            config,
            resolved=prepared_cli_config.resolved_toml,
        )
    except ConfigValidationError as exc:
        exit_for_config_validation_error(
            ctx=ctx,
            console=console,
            exc=exc,
            config=config,
            fmt=fmt,
            meta=meta,
            verbosity_level=verbosity_level,
            quiet=state.quiet,
            color=enable_color,
        )

    # Display config validation diagnostics before resolving files.
    # TEXT keeps these behind -v; Markdown renders diagnostics whenever present.
    flattened_diagnostics: FrozenDiagnosticLog = config.validation_logs.flattened()

    if fmt == OutputFormat.TEXT and verbosity_level > 0 and not state.quiet:
        console.print(
            render_diagnostics_text(
                diagnostics=flattened_diagnostics,
                verbosity_level=verbosity_level,
                color=enable_color,
            )
        )
    elif fmt == OutputFormat.MARKDOWN and len(flattened_diagnostics) > 0:
        console.print(
            render_diagnostics_markdown(
                diagnostics=flattened_diagnostics,
            )
        )

    temp_path: Path | None = plan.temp_path  # for cleanup/STDIN-apply branch

    file_resolution: FileListResolution = build_file_resolution(
        run_options=run_options,
        config=config,
        temp_path=temp_path,
    )
    file_list: list[Path] = list(file_resolution.selected)

    # Missing explicit literals are represented later as synthetic contexts.
    # They do not count as selected files for pipeline execution.
    if not file_resolution.missing_literals and exit_if_no_files(
        file_list,
        console=console,
        styled=enable_color,
    ):
        # Nothing to do
        return

    # Run the concrete pipeline variant through the streaming-capable engine
    # boundary. Every output format now observes the same durable-result stream;
    # JSON still materializes the complete compatibility envelope before emission.
    execution_state: PipelineExecutionState = PipelineExecutionState()
    missing_results: list[ProcessingContext] = build_missing_file_contexts(
        paths=file_resolution.missing_literals,
        config=config,
        run_options=run_options,
    )
    stream_paths: tuple[Path, ...] = (
        *file_list,
        *file_resolution.missing_literals,
    )
    context_results: chain[ProcessingContext] = chain(
        iter_steps_for_files(
            run_options=run_options,
            config=config,
            path_configs=None,
            pipeline=pipeline,
            file_list=file_list,
            state=execution_state,
        ),
        missing_results,
    )
    stats: ProcessingStreamStats = ProcessingStreamStats()

    events: Iterator[MachineProcessingStreamEvent] = observe_processing_stream(
        iter_cli_processing_stream(
            context_results,
            command=PIPELINE_KIND,
            paths=stream_paths,
            release_views=True,
        ),
        stats=stats,
        would_change=would_strip_result,
    )

    match fmt:
        case OutputFormat.JSON:
            emit_processing_stream_json_machine(
                console=machine_console,
                meta=meta,
                config=config,
                resolved_toml=prepared_cli_config.resolved_toml,
                events=events,
                summary_mode=summary_mode,
            )

        case OutputFormat.NDJSON:
            emit_processing_stream_machine(
                console=machine_console,
                meta=meta,
                config=config,
                resolved_toml=prepared_cli_config.resolved_toml,
                events=events,
                summary_mode=summary_mode,
            )

        case OutputFormat.TEXT | OutputFormat.MARKDOWN:  # pragma: no branch
            # Exhaustive after JSON/NDJSON because CLI validation constrains fmt
            # to a supported OutputFormat value.

            # Report scope is a human per-file listing policy only.
            #
            # - Machine-readable output must always use the full raw result set.
            # - Human summary mode must also use the full raw result set so aggregated
            #   counts are not distorted by per-file report filtering.
            # - Human non-summary output uses the filtered per-file view.
            options = PipelineHumanPresentationOptions(
                pipeline_kind=PIPELINE_KIND,
                report_scope=report_scope,
                verbosity_level=verbosity_level,
                summary_mode=summary_mode,
                show_diffs=diff,
                apply_changes=apply_changes,
                styled=enable_color,
            )
            output: PipelineCommandHumanOutput = render_pipeline_command_human_stream_output(
                options=options,
                events=events,
                fmt=fmt,
                would_change=would_strip_result,
            )

            emit_stdout_payload(output.stdout)

            if (fmt == OutputFormat.TEXT and not state.quiet and output.stderr) or (
                fmt == OutputFormat.MARKDOWN and output.stderr
            ):
                console.print(output.stderr)

    # Combine engine-derived failures with stream-observed failures.
    #
    # `PipelineExecutionState.exit_code` records hard failures encountered while
    # executing the real pipeline. Stream statistics contribute additional exit
    # conditions observed while consuming durable-result events (for example,
    # synthetic missing-input results in `probe`). Engine failures intentionally
    # take precedence here; command-specific semantic exit statuses are evaluated
    # separately below.
    encountered_exit_code: ExitCode | None = execution_state.exit_code or stats.exit_code

    if apply_changes:
        # Writes (only when --apply is set)
        if run_options.stdin_mode:
            # For STDIN content mode, the modified file content is emitted to stdout in WriterStep.
            # So we do not have to output it here.
            #
            # Cleanup the temp file.
            safe_unlink(temp_path)
            return
        else:
            # Count outcomes observed from durable-result stream events.
            written: int = stats.written
            failed: int = stats.failed

            # Emit apply summary. TEXT honors --quiet; Markdown remains document-oriented.
            if fmt == OutputFormat.TEXT and not state.quiet:
                console.print(
                    render_pipeline_apply_summary_text(
                        command_path=ctx.command_path,
                        written=written,
                        failed=failed,
                        styled=enable_color,
                    )
                )
            elif fmt == OutputFormat.MARKDOWN:
                console.print(
                    render_pipeline_apply_summary_markdown(
                        command_path=ctx.command_path,
                        written=written,
                        failed=failed,
                    )
                )

                console.print(render_version_footer_markdown())

            if failed:
                # Keep the user-facing apply summary above, but do not raise here.
                # `encountered_exit_code` already includes the prioritized
                # pipeline-derived exit code, so the centralized
                # `maybe_exit_on_error(...)` call below decides whether this run
                # exits as FILE_NOT_FOUND, PERMISSION_DENIED, ENCODING_ERROR, or
                # IO_ERROR.
                encountered_exit_code = encountered_exit_code or ExitCode.IO_ERROR

    else:
        if fmt == OutputFormat.MARKDOWN:
            console.print(render_version_footer_markdown())

    # Exit on any error encountered during processing. Pipeline errors must beat
    # the dry-run WOULD_CHANGE signal so access/encoding failures never exit as
    # a successful diff-only result.
    maybe_exit_on_error(
        code=encountered_exit_code,
        temp_path=temp_path,
    )

    if not apply_changes and stats.would_change:
        ctx.exit(ExitCode.WOULD_CHANGE)

    # Cleanup temp file if any (shouldn't be needed except on errors)
    if temp_path and temp_path.exists():
        safe_unlink(temp_path)

    # No explicit return is needed for Click commands.
