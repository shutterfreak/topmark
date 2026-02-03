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
from topmark.api.view import filter_view_results
from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import (
    build_config_for_plan,
    build_file_list,
    exit_if_no_files,
    get_effective_verbosity,
    maybe_exit_on_error,
    render_config_diagnostics,
)
from topmark.cli.errors import TopmarkIOError, TopmarkUsageError
from topmark.cli.io import plan_cli_inputs
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.options import (
    CONTEXT_SETTINGS,
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
    underscored_trap_option,
)
from topmark.cli.utils import (
    emit_diffs,
    emit_processing_results_machine,
    emit_updated_content_to_stdout,
    render_banner,
    render_per_file_guidance,
    render_summary_counts,
)
from topmark.cli_shared.utils import OutputFormat, safe_unlink
from topmark.config.logging import get_logger
from topmark.core.exit_codes import ExitCode
from topmark.core.keys import ArgKey
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.outcomes import Intent, determine_intent
from topmark.pipeline.status import (
    HeaderStatus,
    WriteStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.cli.io import InputPlan
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config import Config, MutableConfig
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.rendering.formats import HeaderOutputFormat

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CHECK,
    help="Validate headers (dry-run). Use --apply to add or update.",
    context_settings=CONTEXT_SETTINGS,
    epilog=f"""\
Adds or updates TopMark header blocks in files (in-place with {CliOpt.APPLY_CHANGES}).
Examples:

  # Preview which files would change (dry-run)
  topmark {CliCmd.CHECK} src

  # Apply: remove headers in-place
  topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} .
""",
)
@common_config_options
@common_file_and_filtering_options
@common_header_formatting_options
@click.option(
    CliOpt.APPLY_CHANGES,
    ArgKey.APPLY_CHANGES,
    is_flag=True,
    help="Write changes to files (off by default).",
)
@click.option(
    CliOpt.WRITE_MODE,
    ArgKey.WRITE_MODE,
    type=click.Choice(["atomic", "inplace", "stdout"], case_sensitive=False),
    help=(
        "Select write strategy: 'atomic' (safe, default), "
        "'inplace' (fast, less safe), or 'stdout' (emit result to standard output)."
    ),
)
@click.option(
    CliOpt.POLICY_CHECK_ADD_ONLY,
    ArgKey.POLICY_CHECK_ADD_ONLY,
    is_flag=True,
    help="Only add headers where missing (no updates).",
)
@click.option(
    CliOpt.POLICY_CHECK_UPDATE_ONLY,
    ArgKey.POLICY_CHECK_UPDATE_ONLY,
    is_flag=True,
    help="Only update existing non-compliant headers (no additions).",
)
@click.option(
    CliOpt.RENDER_DIFF,
    ArgKey.RENDER_DIFF,
    is_flag=True,
    help="Show unified diffs (human output only).",
)
@click.option(
    CliOpt.RESULTS_SUMMARY_MODE,
    ArgKey.RESULTS_SUMMARY_MODE,
    is_flag=True,
    help="Show outcome counts instead of per-file details.",
)
@click.option(
    CliOpt.SKIP_COMPLIANT,
    ArgKey.SKIP_COMPLIANT,
    is_flag=True,
    help="Hide files that are already up-to-date.",
)
@underscored_trap_option("--skip_compliant")
@click.option(
    CliOpt.SKIP_UNSUPPORTED,
    ArgKey.SKIP_UNSUPPORTED,
    is_flag=True,
    help="Hide unsupported file types.",
)
@underscored_trap_option("--skip_unsupported")
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
def check_command(
    *,
    # Command options: common_file_filtering_options
    files_from: list[str],
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    include_file_types: list[str],
    exclude_file_types: list[str],
    relative_to: str | None,
    stdin_filename: str | None,
    # Command options: config
    no_config: bool,
    config_paths: list[str],
    # Command options: formatting
    align_fields: bool,
    header_format: HeaderOutputFormat | None,
    # Command options: check and strip
    apply_changes: bool,
    write_mode: str | None,
    diff: bool,
    summary_mode: bool,
    skip_compliant: bool,
    skip_unsupported: bool,
    output_format: OutputFormat | None,
    # Command options: check
    add_only: bool,
    update_only: bool,
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
        files_from (list[str]): Files that contain newline‑delimited *paths* to add to the
            candidate set before filtering. Use ``-`` to read from STDIN.
        include_patterns (list[str]): Glob patterns to *include* (intersection).
        include_from (list[str]): Files that contain include glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        exclude_patterns (list[str]): Glob patterns to *exclude* (subtraction).
        exclude_from (list[str]): Files that contain exclude glob patterns (one per line).
            Use ``-`` to read patterns from STDIN.
        include_file_types (list[str]): Restrict processing to the given file type identifiers.
        exclude_file_types (list[str]): Exclude processing for the given file type identifiers.
        relative_to (str | None): Base directory used to compute relative paths in outputs.
        stdin_filename (str | None): Assumed filename when  reading content from STDIN).
        no_config (bool): If True, skip loading project/user configuration files.
        config_paths (list[str]): Additional configuration file paths to load and merge.
        align_fields (bool): Whether to align header fields when rendering (captured in config).
        header_format (HeaderOutputFormat | None): Optional output format override for header
            rendering (captured in config).
        apply_changes (bool): Write changes to files; otherwise perform a dry run.
        write_mode (str | None): Whether to use safe atomic writing, faster in-place writing
            or writing to STDOUT (default: atomic writer).
        diff (bool): Show unified diffs of header changes (human output only).
        summary_mode (bool): Show outcome counts instead of per‑file details.
        skip_compliant (bool): Suppress files whose comparison status is UNCHANGED.
        skip_unsupported (bool): Suppress unsupported file types.
        output_format (OutputFormat | None): Output format to use
            (``default``, ``json``, or ``ndjson``).
        add_only (bool): Only add headers where missing (no updates).
        update_only (bool): Only update existing non‑compliant headers (no additions).

    Raises:
        TopmarkUsageError: If no input is provided, or if mutually exclusive STDIN modes
            are combined.
        TopmarkIOError: If an I/O error occurred (read/write).

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
    console: ConsoleLike = ctx.obj["console"]
    prune_override: bool | None = ctx.obj.get(
        "prune"
    )  # injected by tests via CliRunner.invoke(..., obj=...)
    prune: bool = bool(prune_override) if prune_override else False

    # Add apply_changes and write_mode to Click context
    ctx.obj[ArgKey.APPLY_CHANGES] = apply_changes
    ctx.obj[ArgKey.WRITE_MODE] = write_mode

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON) and diff:
        raise TopmarkUsageError(
            f"{ctx.command.name}: {CliOpt.RENDER_DIFF} "
            "is not supported with machine-readable output formats."
        )

    if add_only and update_only:
        raise TopmarkUsageError(
            f"{ctx.command.name}: Options {CliOpt.POLICY_CHECK_ADD_ONLY} and "
            f"{CliOpt.POLICY_CHECK_UPDATE_ONLY} are mutually exclusive."
        )

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

    draft_config: MutableConfig = build_config_for_plan(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_paths,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )

    # Propagate runtime intent for updater (terminal vs preview write status)
    draft_config.apply_changes = bool(apply_changes)

    config: Config = draft_config.freeze()

    # Display Config diagnostics before resolving files
    if fmt == OutputFormat.DEFAULT:
        render_config_diagnostics(ctx=ctx, config=config)

    temp_path: Path | None = plan.temp_path  # for cleanup/STDIN-apply branch
    stdin_mode: bool = plan.stdin_mode
    file_list: list[Path] = build_file_list(
        config,
        stdin_mode=stdin_mode,
        temp_path=temp_path,
    )

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx, config)

    logger.trace("Config after merging args and resolving file list: %s", config)

    # Use Click's text stream for stdin so CliRunner/invoke input is read reliably
    # stdin_stream = click.get_text_stream("stdin") if stdin_text else None

    if exit_if_no_files(file_list):
        # Nothing to do
        return

    # Banner
    if vlevel > 0:
        render_banner(ctx, n_files=len(file_list))

    # Choose the concrete pipeline variant
    pipeline: Sequence[Step] = select_pipeline("check", apply=apply_changes, diff=diff)

    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None = None

    results, encountered_error_code = run_steps_for_files(
        file_list=file_list,
        pipeline=pipeline,
        config=config,
        prune=prune,
    )

    # Optional filtering
    view_results: list[ProcessingContext] = filter_view_results(
        results,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
    )

    # Machine formats first
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_processing_results_machine(
            config=config,
            results=view_results,
            fmt=fmt,
            summary_mode=summary_mode,
        )
    else:
        # Human output
        if summary_mode:
            render_summary_counts(view_results, total=len(file_list))

        else:

            def _check_msg(r: ProcessingContext, apply_changes: bool) -> str | None:
                """Generate a per-file message for 'check' results."""
                if not effective_would_add_or_update(r):
                    return None

                if apply_changes:
                    intent: Intent = determine_intent(r)
                    if r.status.write == WriteStatus.FAILED:
                        return f"❌ Could not {intent.value} header: {r.status.write.value}"
                    if r.status.write == WriteStatus.SKIPPED:
                        # Defensive: should not happen when effective_would_add_or_update is True,
                        # but keeps CLI honest if a later step halts.
                        return f"⚠️  Could not {intent.value} header (write skipped)."
                    return (
                        f"➕ Adding header for '{r.path}'"
                        if r.status.header == HeaderStatus.MISSING
                        else f"✏️  Updating header for '{r.path}'"
                    )

                return (
                    f"🛠️  Run `topmark {CliCmd.CHECK} {CliOpt.APPLY_CHANGES} {r.path}` "
                    "to update this file."
                )

            # Per-file guidance (only in non-summary human mode)
            if fmt == OutputFormat.DEFAULT and not summary_mode and vlevel >= 0:
                render_per_file_guidance(
                    view_results, make_message=_check_msg, apply_changes=apply_changes
                )

        # Diff output
        emit_diffs(results=view_results, diff=diff, command=ctx.command)

    # Writes (only when --apply is set)
    if stdin_mode and apply_changes:
        # For STDIN content mode, emit the modified file content to stdout.
        emit_updated_content_to_stdout(view_results)
        # Cleanup temp file
        safe_unlink(temp_path)
        return

    if apply_changes:
        # Count outcomes after the pipeline writer step finalized statuses.
        written: int = sum(1 for r in results if r.status.write == WriteStatus.WRITTEN)
        failed: int = sum(1 for r in results if r.status.write == WriteStatus.FAILED)

        if fmt == OutputFormat.DEFAULT:
            msg: str = (
                f"\n✅ Applied changes to {written} file(s)."
                if written
                else "\n✅ No changes to apply."
            )
            console.print(console.styled(msg, fg="green", bold=True))
        if failed:
            raise TopmarkIOError(f"Failed to write {failed} file(s). See log for details.")

    if not apply_changes and any(effective_would_add_or_update(r) for r in results):
        ctx.exit(ExitCode.WOULD_CHANGE)

    # Exit on any error encountered during processing
    maybe_exit_on_error(code=encountered_error_code, temp_path=temp_path)

    # Cleanup temp file if any (shouldn't be needed except on errors)
    if temp_path and temp_path.exists():
        safe_unlink(temp_path)

    # No explicit return needed for Click commands.
