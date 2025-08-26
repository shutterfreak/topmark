# topmark:header:start
#
#   file         : strip.py
#   file_relpath : src/topmark/cli/commands/strip.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark ``strip`` command.

Removes the entire TopMark header from targeted files. By default this command
performs a dry run (no writes); pass ``--apply`` to write changes.

Examples:
  Preview changes (dry run):

    $ topmark strip src

  Apply changes (write in place):

    $ topmark strip --apply .
"""

import logging

import click
from yachalk import chalk

from topmark.cli.cli_types import EnumParam
from topmark.cli.config_resolver import resolve_config_from_click
from topmark.cli.options import (
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
    typed_option,
    underscored_trap_option,
)
from topmark.cli.utils import (
    OutputFormat,
    count_by_outcome,
)
from topmark.config.logging import get_logger
from topmark.file_resolver import resolve_file_list
from topmark.pipeline import runner
from topmark.pipeline.context import ComparisonStatus, FileStatus, HeaderStatus, ProcessingContext
from topmark.pipeline.pipelines import get_pipeline
from topmark.rendering.formats import HeaderOutputFormat
from topmark.utils.diff import render_patch

logger = get_logger(__name__)


@common_config_options
@common_file_and_filtering_options
@common_header_formatting_options
@typed_option(
    "--apply", "apply_changes", is_flag=True, help="Write changes to files (off by default)."
)
@typed_option("--diff", is_flag=True, help="Show unified diffs (human output only).")
@typed_option(
    "--summary",
    "summary_mode",
    is_flag=True,
    help="Show outcome counts instead of per-file details.",
)
@typed_option(
    "--skip-compliant",
    "skip_compliant",
    is_flag=True,
    help="Hide files that are already up-to-date.",
)
@underscored_trap_option("--skip_compliant")
@typed_option(
    "--skip-unsupported",
    "skip_unsupported",
    is_flag=True,
    help="Hide unsupported file types.",
)
@underscored_trap_option("--skip_unsupported")
@typed_option(
    "--format",
    "output_format",
    type=EnumParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
def strip_command(
    *,
    stdin: bool,
    include_patterns: list[str],
    include_from: list[str],
    exclude_patterns: list[str],
    exclude_from: list[str],
    no_config: bool,
    config_paths: list[str],
    file_types: list[str],
    relative_to: str | None,
    align_fields: bool,
    header_format: HeaderOutputFormat | None,
    apply_changes: bool,
    diff: bool,
    summary_mode: bool,
    skip_compliant: bool,
    skip_unsupported: bool,
    output_format: OutputFormat | None,
) -> None:
    """Remove the TopMark header block from targeted files.

    This command reads positional paths from ``click.get_current_context().args``
    (Black‑style) and reuses the standard config resolver and file selection logic
    so options like ``--include``, ``--exclude``, ``--file-type`` and ``--stdin``
    behave the same as the default command.

    Args:
      stdin (bool): Read file paths from standard input (one per line).
      include_patterns (list[str]): Glob patterns specifying additional files or
        directories to include.
      include_from (list[str]): Paths to files that contain include glob patterns
        (one per line).
      exclude_patterns (list[str]): Glob patterns specifying files or directories
        to exclude.
      exclude_from (list[str]): Paths to files that contain exclude glob patterns
        (one per line).
      no_config (bool): Ignore user/project configuration files and use defaults only.
      config_paths (list[str]): Additional configuration file paths to load and merge.
      file_types (list[str]): Restrict processing to the given TopMark file type identifiers.
      relative_to (str | None): Base directory used to compute relative paths in outputs.
      align_fields (bool): Align header fields by the colon for readability.
      header_format (HeaderOutputFormat | None): Optional override for rendering format
        (not used by ``strip`` logic, but accepted for parity with the default command).
      apply_changes (bool): Write changes to files; otherwise perform a dry run.
      diff (bool): Show unified diffs of header removals (human output only).
      summary_mode (bool): Show outcome counts instead of per‑file details.
      skip_compliant (bool): Suppress files whose comparison status is UNCHANGED.
      skip_unsupported (bool): Suppress unsupported file types.
      output_format (OutputFormat | None): Output format to use (``default``, ``json``,
        or ``ndjson``).

    Raises:
      click.UsageError: If no input is provided.
      SystemExit: Exit code 2 in dry‑run mode when changes would be required.

    Returns:
      None: This function terminates the process with the appropriate exit code.

    Exit Status:
      0: Nothing to strip, or writes succeeded with ``--apply``.
      2: Dry run detected files that would change.
      1: Errors occurred while writing files with ``--apply``.
    """
    ctx = click.get_current_context()
    files = list(ctx.args)

    # Before resolving config/files — block empty invocations (Black-style)
    no_inputs = (
        not files and not stdin and not include_patterns and not include_from and not config_paths
    )
    if no_inputs:
        # Show a friendly usage error with guidance
        raise click.UsageError(
            "No input specified. Provide one or more paths, or use --stdin. "
            "See --help for examples.",
            ctx=ctx,
        )

    # === Primary TopMark operation (default: check, write with --apply) ===
    config = resolve_config_from_click(
        ctx=ctx,
        files=list(files),
        stdin=stdin,
        include_patterns=list(include_patterns),
        include_from=list(include_from),
        exclude_patterns=list(exclude_patterns),
        exclude_from=list(exclude_from),
        file_types=list(file_types),
        relative_to=relative_to,
        no_config=no_config,
        config_paths=list(config_paths),
        align_fields=align_fields,
        header_format=header_format,
    )

    logger.trace("Config after merging args: %s", config)

    # Use Click's text stream for stdin so CliRunner/invoke input is read reliably
    stdin_stream = click.get_text_stream("stdin") if stdin else None
    file_list = resolve_file_list(config, stdin_stream=stdin_stream)
    if not file_list:
        click.echo(chalk.blue("\nℹ️  No files to process.\n"))
        raise SystemExit(0)

    if logger.isEnabledFor(logging.INFO):
        click.echo(chalk.blue(f"\n🔍 Processing {len(file_list)} file(s):\n"))
        click.echo(chalk.bold.underline("📋 TopMark Results:"))

    # Use summary pipeline when --summary is set, else full (compare+update+patch)
    pipeline_name = "strip"
    steps = get_pipeline(pipeline_name)

    results: list[ProcessingContext] = []
    for path in file_list:
        try:
            ctx_obj: ProcessingContext = ProcessingContext.bootstrap(path=path, config=config)
            ctx_obj = runner.run(ctx_obj, steps)
            results.append(ctx_obj)
        except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
            logger.error("Filesystem error while processing %s: %s", path, e)
            click.echo(chalk.red(f"❌ Filesystem error processing {path}: {e}"))
            continue
        except UnicodeDecodeError as e:
            logger.error("Encoding error while reading %s: %s", path, e)
            click.echo(chalk.red(f"🧵 Encoding error in {path}: {e}"))
            continue
        except Exception as e:  # pragma: no cover - unexpected path
            logger.exception("Unexpected error processing %s", path)
            click.echo(
                chalk.red(f"⚠️  Unexpected error processing {path}: {e} (use -vv for traceback)")
            )
            continue

    # Optional filtering
    if skip_compliant:
        view_results = [r for r in results if r.status.comparison is not ComparisonStatus.UNCHANGED]
    else:
        view_results = results

    if skip_unsupported:
        view_results = [
            r
            for r in view_results
            if r.status.file
            not in [
                FileStatus.SKIPPED_UNSUPPORTED,
                FileStatus.SKIPPED_KNOWN_NO_HEADERS,
            ]
        ]

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT
    # Machine formats first
    if fmt is OutputFormat.NDJSON:
        import json as _json

        if summary_mode:
            counts = count_by_outcome(view_results)
            for key, (n, label, _color) in counts.items():
                click.echo(_json.dumps({"key": key, "count": n, "label": label}))
        else:
            for r in view_results:
                click.echo(_json.dumps(r.to_dict()))
    elif fmt is OutputFormat.JSON:
        import json as _json

        if summary_mode:
            counts = count_by_outcome(view_results)
            data = {k: {"count": n, "label": label} for k, (n, label, _color) in counts.items()}
            click.echo(_json.dumps(data, indent=2))
        else:
            payload = [r.to_dict() for r in view_results]
            click.echo(_json.dumps(payload, indent=2))
    else:
        # Human output
        if summary_mode:
            click.echo()
            click.echo(chalk.bold.underline("Summary by outcome:"))

            counts = count_by_outcome(view_results)
            label_width = max((len(v[1]) for v in counts.values()), default=0) + 1
            num_width = len(str(len(file_list)))
            for _key, (n, label, color) in counts.items():
                click.echo(color(f"  {label:<{label_width}}: {n:>{num_width}}"))

        else:
            for r in view_results:
                click.echo(r.summary)
                if r.status.comparison == ComparisonStatus.CHANGED:
                    if apply_changes:
                        if r.status.header in [HeaderStatus.DETECTED, HeaderStatus.EMPTY]:
                            click.echo(chalk.yellow(f"   🧹 Stripping header in '{r.path}'"))
                    else:
                        click.echo(
                            chalk.yellow(
                                f"   🛠️  Run `topmark strip --apply {r.path}` to update this file."
                            )
                        )

            # Diff output
            import pprint

            for r in view_results:
                logger.debug("strip(): diff: %s, result: %s", diff, pprint.pformat(r, 2))
                if diff and r.header_diff:
                    click.echo(render_patch(r.header_diff))

    # Writes (only when --apply is set)
    if apply_changes:
        written = 0
        failed = 0
        from pathlib import Path

        for r in results:
            try:
                if r.updated_file_lines is not None and r.file_lines != r.updated_file_lines:
                    Path(str(r.path)).write_text("".join(r.updated_file_lines), encoding="utf-8")
                    written += 1
            except Exception as e:  # pragma: no cover
                failed += 1
                logger.error("Failed to write %s: %s", r.path, e)
        if fmt is OutputFormat.DEFAULT:
            click.echo(
                (
                    f"\n✅ Applied changes to {written} file(s)."
                    if written
                    else "\n✅ No changes to apply."
                )
            )
        if failed:
            raise SystemExit(1)

    # Exit code policy for `strip`: non-zero only if a removal would occur.
    # A missing header is *not* an error condition for `strip`.
    if not apply_changes:
        would_change = any((r.status.comparison == ComparisonStatus.CHANGED) for r in results)
        if would_change:
            raise SystemExit(2)

    if logger.isEnabledFor(logging.INFO):
        click.echo("✅ All done!")

    return
