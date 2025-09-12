# topmark:header:start
#
#   project      : TopMark
#   file         : strip.py
#   file_relpath : src/topmark/cli/commands/strip.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark ``strip`` command.

Removes the entire TopMark header from targeted files.
Performs a dry‑run check by default and applies changes when ``--apply`` is given.

Input modes supported:
  • **Paths mode (default)**: one or more PATHS and/or ``--files-from FILE``.
  • **Content on STDIN**: a single ``-`` as the sole PATH **plus** ``--stdin-filename NAME``.
  • **Lists on STDIN for ...-from**: allow ``--files-from -``, ``--include-from -``,
  or ``--exclude-from -`` (exactly one may consume STDIN).

Examples:
  Preview changes (dry run):

    $ topmark strip src

  Apply changes (write in place):

    $ topmark strip --apply .

  Read a *single file's content* from STDIN:

    $ cat with_header.py | topmark strip - --stdin-filename with_header.py

  Read a *list of paths* from STDIN:

    $ git ls-files | topmark strip --files-from -
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import (
    build_config_common,
    build_file_list,
    exit_if_no_files,
    filter_view_results,
    get_effective_verbosity,
    maybe_exit_on_error,
    run_steps_for_files,
)
from topmark.cli.errors import TopmarkIOError, TopmarkUsageError
from topmark.cli.io import plan_cli_inputs
from topmark.cli.options import (
    CONTEXT_SETTINGS,
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
    underscored_trap_option,
)
from topmark.cli.utils import (
    emit_diffs,
    emit_machine_output,
    emit_updated_content_to_stdout,
    render_banner,
    render_per_file_guidance,
    render_summary_counts,
)
from topmark.cli_shared.console_api import ConsoleLike
from topmark.cli_shared.exit_codes import ExitCode
from topmark.cli_shared.utils import (
    OutputFormat,
    safe_unlink,
    write_updates,
)
from topmark.config.logging import get_logger
from topmark.pipeline.context import (
    ComparisonStatus,
    FileStatus,
    HeaderStatus,
    ProcessingContext,
    WriteStatus,
)

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


@click.command(
    name="strip",
    help="Remove the entire TopMark header from files.",
    context_settings=CONTEXT_SETTINGS,
    epilog="""\
Removes TopMark header blocks in files (in-place with --apply).

Examples:

  # Preview which files would change (dry-run)
  topmark strip src

  # Apply: remove headers in-place
  topmark strip --apply .
""",
)
@common_config_options
@common_file_and_filtering_options
@common_header_formatting_options
@click.option(
    "--apply", "apply_changes", is_flag=True, help="Write changes to files (off by default)."
)
@click.option("--diff", is_flag=True, help="Show unified diffs (human output only).")
@click.option(
    "--summary",
    "summary_mode",
    is_flag=True,
    help="Show outcome counts instead of per-file details.",
)
@click.option(
    "--skip-compliant",
    "skip_compliant",
    is_flag=True,
    help="Hide files that are already up-to-date.",
)
@underscored_trap_option("--skip_compliant")
@click.option(
    "--skip-unsupported",
    "skip_unsupported",
    is_flag=True,
    help="Hide unsupported file types.",
)
@underscored_trap_option("--skip_unsupported")
@click.option(
    "--format",
    "output_format",
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
def strip_command(
    *,
    # Command options: common_file_filtering_options
    files_from: list[str],
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    file_types: list[str],
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
    diff: bool,
    summary_mode: bool,
    skip_compliant: bool,
    skip_unsupported: bool,
    output_format: OutputFormat | None,
) -> None:
    """Remove the TopMark header block from targeted files.

    This command reads positional paths from ``click.get_current_context().args``
    (Black‑style) and reuses the standard config resolver and file selection logic.
    It supports three input styles:

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
        file_types (list[str]): Restrict processing to the given TopMark file type identifiers.
        relative_to (str | None): Base directory used to compute relative paths in outputs.
        stdin_filename (str | None): Assumed filename when  reading content from STDIN).
        no_config (bool): If True, skip loading project/user configuration files.
        config_paths (list[str]): Additional configuration file paths to load and merge.
        align_fields (bool): Whether to align header fields when rendering (captured in config).
        header_format (HeaderOutputFormat | None): Optional output format override for header
            rendering (captured in config).
        apply_changes (bool): Write changes to files; otherwise perform a dry run.
        diff (bool): Show unified diffs of header removals (human output only).
        summary_mode (bool): Show outcome counts instead of per‑file details.
        skip_compliant (bool): Suppress files whose comparison status is UNCHANGED.
        skip_unsupported (bool): Suppress unsupported file types.
        output_format (OutputFormat | None): Output format to use
            (``default``, ``json``, or ``ndjson``).

    Raises:
      TopmarkUsageError: If no input is provided, or if mutually exclusive STDIN modes are combined.
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
    ctx = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        if diff:
            raise TopmarkUsageError(
                f"{ctx.command.name}: --diff is not supported with machine-readable output formats."
            )

    # === Build Config and file list ===
    plan = plan_cli_inputs(
        ctx=ctx,
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        stdin_filename=stdin_filename,
    )
    draft_config = build_config_common(
        ctx=ctx,
        plan=plan,
        no_config=no_config,
        config_paths=config_paths,
        file_types=file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
    )

    # Propagate runtime intent for updater (terminal vs preview write status)
    draft_config.apply_changes = bool(apply_changes)

    config = draft_config.freeze()

    temp_path = plan.temp_path  # for cleanup/STDIN-apply branch
    stdin_mode = plan.stdin_mode
    file_list = build_file_list(
        config,
        stdin_mode=stdin_mode,
        temp_path=temp_path,
    )

    # Determine effective program-output verbosity for gating extra details
    vlevel = get_effective_verbosity(ctx, config)

    logger.trace("Config after merging args and resolving file list: %s", config)

    # Use Click's text stream for stdin so CliRunner/invoke input is read reliably
    # stdin_stream = click.get_text_stream("stdin") if stdin_text else None

    if exit_if_no_files(file_list):
        # Nothing to do
        return

    # Banner
    if vlevel > 0:
        render_banner(ctx, n_files=len(file_list))

    pipeline_name = "strip"
    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None = None

    results, encountered_error_code = run_steps_for_files(
        file_list, pipeline_name=pipeline_name, config=config
    )

    # Optional filtering
    view_results = filter_view_results(
        results, skip_compliant=skip_compliant, skip_unsupported=skip_unsupported
    )

    # Machine formats first
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_machine_output(view_results, fmt, summary_mode)
    else:
        # Human output
        if summary_mode:
            render_summary_counts(view_results, total=len(file_list))

        else:

            def _strip_msg(r: ProcessingContext, apply_changes: bool) -> str | None:
                """Generate a per-file message for 'strip' results."""
                if r.status.comparison != ComparisonStatus.CHANGED:
                    return None
                if apply_changes and r.status.header in (HeaderStatus.DETECTED, HeaderStatus.EMPTY):
                    return f"🧹 Stripping header in '{r.path}'"
                return f"🛠️  Run `topmark strip --apply {r.path}` to update this file."

            # Per-file guidance (only in non-summary human mode)
            if fmt == OutputFormat.DEFAULT and not summary_mode:
                if vlevel >= 0:
                    render_per_file_guidance(
                        view_results, make_message=_strip_msg, apply_changes=apply_changes
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
        written = 0
        failed = 0

        def _should_write_strip(r: ProcessingContext) -> bool:
            """Determine whether to write this file in strip mode."""
            return r.status.file is FileStatus.RESOLVED and r.status.write is WriteStatus.REMOVED

        # Perform writes and count successes/failures
        written, failed = write_updates(results, should_write=_should_write_strip)

        if fmt == OutputFormat.DEFAULT:
            msg = (
                f"\n✅ Removed headers in {written} file(s)."
                if written
                else "\n✅ No changes to apply."
            )
            console.print(console.styled(msg, fg="green", bold=True))
        if failed:
            raise TopmarkIOError(f"Failed to write {failed} file(s). See log for details.")

    # Exit code policy for `strip`: non-zero only if a removal would occur.
    # A missing header is *not* an error condition for `strip`.

    def _would_change_strip(results: list[ProcessingContext]) -> bool:
        """Return True if any file would be changed by `strip`."""
        return any(r.status.comparison is ComparisonStatus.CHANGED for r in results)

    if not apply_changes and _would_change_strip(results):
        ctx.exit(ExitCode.WOULD_CHANGE)

    # Exit on any error encountered during processing
    maybe_exit_on_error(code=encountered_error_code, temp_path=temp_path)

    # Cleanup temp file if any (shouldn't be needed except on errors)
    if temp_path and temp_path.exists():
        safe_unlink(temp_path)

    # No explicit return needed for Click commands.
