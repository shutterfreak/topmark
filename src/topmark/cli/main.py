# topmark:header:start
#
#   file         : main.py
#   file_relpath : src/topmark/cli/main.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI entry point for TopMark.

This module wires the TopMark command-line interface (CLI) using Click 8.2.
The **base command** performs a check/dry‑run by default and **applies** changes
when ``--apply`` is specified.

HEaders can be stripped from files with the ``strip`` subcommand.

Auxiliary subcommands provide configuration and
metadata functionality (e.g., ``dump-config``, ``filetypes``, ``show-defaults``,
``init-config``, ``version``).

The root command behaves similar to Black:
- If a token does **not** match a subcommand, it is treated as a **path**.
- If no inputs are provided, a usage error is raised.

Examples:
  Run a dry‑run check on a path::

    topmark src

  Apply changes to files in the current tree::

    topmark --apply .

  Show a JSON summary (CI‑friendly)::

    topmark --summary --format=json src

  Remove headers (dry-run)::

    topmark strip src

  List supported file types::

    topmark filetypes
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, cast

import click

# --- Unified base-command imports for primary operation ---
from topmark.cli.cli_types import EnumParam

# Eagerly register commands by importing command modules
# (import side effects attach subcommands to `cli`).
from topmark.cli.commands.default import default_command
from topmark.cli.commands.dump_config import dump_config_command
from topmark.cli.commands.filetypes import filetypes_command
from topmark.cli.commands.init_config import init_config_command
from topmark.cli.commands.show_defaults import show_defaults_command
from topmark.cli.commands.strip import strip_command
from topmark.cli.commands.version import version_command
from topmark.cli.options import (
    common_config_options,
    common_file_and_filtering_options,
    common_header_formatting_options,
    common_logging_options,
    typed_command_of,
    typed_group,
    typed_option,
    underscored_trap_option,
)
from topmark.cli.utils import (
    ColorMode,
    OutputFormat,
    resolve_color_mode,
)
from topmark.config.logging import TRACE_LEVEL, get_logger, setup_logging
from topmark.pipeline.processors import register_all_processors
from topmark.rendering.formats import HeaderOutputFormat

# --- Typed Click shims to avoid subclassing/using Any during type checking ---
if TYPE_CHECKING:

    class GroupBase(Protocol):
        """Typed base to avoid subclassing Any when Click lacks stubs."""

        def command(
            self, *args: Any, **kwargs: Any
        ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            """Typed Click shim for Click.command."""
            ...

        def invoke(self, ctx: Any) -> Any:
            """Typed Click shim for Click.command."""
            ...

else:
    GroupBase = click.Group  # type: ignore[assignment]

logger = get_logger(__name__)

# Ensure file-type processors are registered regardless of entrypoint (__main__ vs console_scripts)
_processors_registered = False


def ensure_processors_registered() -> None:
    """Idempotently register all header processors.

    Click console scripts may import this module without running ``__main__``, so
    processor registration must happen at import time. Calling this function is
    safe multiple times.

    Returns:
      None
    """
    global _processors_registered
    if not _processors_registered:
        register_all_processors()
        _processors_registered = True


# Register on import so console_scripts entry points also get processors
ensure_processors_registered()


class TopMarkGroup(click.Group):
    """Group that treats unknown first tokens as *paths*, not subcommands.

    If a subcommand name is not found, the token is preserved in ``ctx.meta`` and a
    hidden fallback command (``"__files__"``) is returned. This allows invocations
    like ``topmark README.md`` to behave as if ``topmark __files__ README.md`` had
    been entered, without exposing the fallback to users.

    Attributes:
      fallback_cmd_name: Name of the hidden fallback command that forwards to the
        default flow.
    """

    fallback_cmd_name = "__files__"

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Looks up a subcommand, returning the 'default' if not found."""
        # Check for registered subcommands first
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        # Unknown token → treat it as a file path and fall back.
        # Store the first token in ctx.meta so the fallback can reconstruct ctx.args.
        try:
            ctx.meta["fallback_first"] = cmd_name
        except Exception:
            # ctx.meta is always a dict, but guard just in case
            pass
        return super().get_command(ctx, self.fallback_cmd_name)


# Allow trailing arguments (paths) for the base command while preserving subcommands.
# If a token matches a registered subcommand, Click still dispatches to it; otherwise
# unknown tokens are passed through into `ctx.args` instead of causing a "No such command" error.
CONTEXT_SETTINGS = dict(
    help_option_names=["-h", "--help"],
    allow_extra_args=True,
    # Unknown options should raise errors at the group level so typos like
    # `--exclude_from` don't get silently ignored and turn into paths.
    ignore_unknown_options=False,
)


@typed_group(cls=TopMarkGroup, context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@common_logging_options
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
@click.option(
    "--color",
    "color_mode",
    type=EnumParam(ColorMode),
    default=None,
    help="Color output: auto (default), always, or never.",
)
@click.option(
    "--no-color",
    "no_color",
    is_flag=True,
    help="Disable color output (equivalent to --color=never).",
)
@underscored_trap_option("--no_color")
def cli(
    *,
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
    # Primary operation args/options when no subcommand is invoked
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
    """
    TopMark: file header inspection and management tool.

    When invoked **without a subcommand**, this base command processes files directly.
    Positional paths are read from the remaining command-line arguments (like Black),
    i.e., they come **after** the options parsed by Click. Subcommands remain available
    for metadata tasks (dump-config, filetypes, version, ...).

    Args:
        verbose: Number of times ``-v/--verbose`` was provided.
        quiet: Number of times ``-q/--quiet`` was provided.
        color_mode: Color policy for terminal output (``auto``, ``always``, ``never``).
        no_color: If True, disables color (equivalent to ``--color=never``).
        stdin: If True, read file paths from standard input (one per line).
        include_patterns: Glob patterns specifying additional files or directories to include.
        include_from: Paths to files that contain include glob patterns (one per line).
        exclude_patterns: Glob patterns specifying files or directories to exclude.
        exclude_from: Paths to files that contain exclude glob patterns (one per line).
        no_config: If True, ignore user/project configuration files and use defaults only.
        config_paths: Additional configuration file paths to load and merge.
        file_types: Restrict processing to the given TopMark file type identifiers.
        relative_to: Base directory used to compute relative paths in outputs.
        align_fields: If True, align header fields by the colon for readability.
        header_format: Optional override for the header output format used when rendering.
        apply_changes: If True, write changes to files; otherwise perform a dry run.
        diff: If True, show unified diffs of header changes (human output only).
        summary_mode: If True, print outcome counts instead of per-file details.
        skip_compliant: If True, suppress files whose comparison status is UNCHANGED.
        skip_unsupported: If True, suppress unsupported file types.
        output_format: Output format to use (default, json, or ndjson).

    Notes:
        - Positional file/directory paths are obtained from ``ctx.args`` when no subcommand
          is invoked (so ``topmark [OPTIONS] PATHS...`` works without conflicting with subcommands).
        - The Click context is obtained internally via :func:`click.get_current_context`.

    Returns:
        None.

    Raises:
        click.UsageError: If no input is provided (Black‑style preflight).

    Examples:
        Check files without writing::

            topmark src pkg

        Apply changes and show diffs in human output::

            topmark --apply --diff .

        Machine‑readable summary for CI::

            topmark --summary --format=ndjson src
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)

    # Defensive: make sure processors are registered even if this module was imported
    # in a non-standard way
    ensure_processors_registered()

    # Adjust logging level globally
    level = logging.WARNING - 10 * verbose + 10 * quiet
    level = min(logging.CRITICAL, max(TRACE_LEVEL, level))
    ctx.obj["log_level"] = level
    setup_logging(level=level)

    # Resolve color mode (machine formats may override this later at the subcommand level)
    effective_color_mode: ColorMode = (
        ColorMode.NEVER if no_color else (color_mode or ColorMode.AUTO)
    )

    enable_color = resolve_color_mode(
        cli_mode=effective_color_mode,
        output_format=None,
        stdout_isatty=None,
    )
    ctx.color = bool(enable_color)
    ctx.obj["color_enabled"] = bool(enable_color)

    # If a subcommand is invoked, defer to it; otherwise run the default flow.
    if click.get_current_context().invoked_subcommand:
        return

    # Directly invoke the default implementation so cases like `--stdin` run
    # even when there is no first positional token to trigger the fallback.
    default_command(
        stdin=stdin,
        include_patterns=include_patterns,
        include_from=include_from,
        exclude_patterns=exclude_patterns,
        exclude_from=exclude_from,
        no_config=no_config,
        config_paths=config_paths,
        file_types=file_types,
        relative_to=relative_to,
        align_fields=align_fields,
        header_format=header_format,
        apply_changes=apply_changes,
        diff=diff,
        summary_mode=summary_mode,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
        output_format=output_format,
    )
    return


# --- Lazy-safe, idempotent subcommand registration ---------------------------------
_commands_registered: bool = False


def ensure_commands_registered() -> None:
    """Attach subcommands to `cli` exactly once (safe to call multiple times)."""
    global _commands_registered

    if _commands_registered:
        return

    @typed_command_of(
        cli,
        TopMarkGroup.fallback_cmd_name,
        hidden=True,
        context_settings=CONTEXT_SETTINGS,
    )
    def _files_fallback() -> None:
        """Hidden catch‑all that forwards paths in ``ctx.args`` to the default flow.

        All primary options are parsed at the group level and made available via
        ``ctx.parent.params``. This command reconstructs the first unmatched token
        (if any) from ``ctx.meta`` and ensures it is included in ``ctx.args`` so
        the default implementation sees the complete list of paths.

        Returns:
          None
        """
        ctx = click.get_current_context()
        ctx.ensure_object(dict)

        ensure_processors_registered()

        # Rebuild the file list: include the first unmatched token (used as the
        # displayed command name by Click) and the remaining args.
        first = ctx.meta.get("fallback_first")
        trailing = list(ctx.args)
        files = ([first] if first else []) + trailing
        # Make sure default_command sees these as positional paths.
        ctx.args = files

        parent = ctx.parent or ctx
        p = parent.params
        default_command(
            stdin=p.get("stdin", False),
            include_patterns=p.get("include_patterns", []),
            include_from=p.get("include_from", []),
            exclude_patterns=p.get("exclude_patterns", []),
            exclude_from=p.get("exclude_from", []),
            no_config=p.get("no_config", False),
            config_paths=p.get("config_paths", []),
            file_types=p.get("file_types", []),
            relative_to=p.get("relative_to"),
            align_fields=p.get("align_fields", False),
            header_format=p.get("header_format"),
            apply_changes=p.get("apply_changes", False),
            diff=p.get("diff", False),
            summary_mode=p.get("summary_mode", False),
            skip_compliant=p.get("skip_compliant", False),
            skip_unsupported=p.get("skip_unsupported", False),
            output_format=p.get("output_format"),
        )

    _ = _files_fallback  # keep reference for static analyzers (registered dynamically via Click)

    # Register other visible subcommands

    typed_command_of(
        cli,
        "strip",
        help="Remove the entire TopMark header from files.",
        context_settings=CONTEXT_SETTINGS,
        epilog="""
Removes the full TopMark header block (between 'topmark:header:start' and 'topmark:header:end')
from each targeted file. By default this is a dry run; use --apply to write changes.

Examples:

  # Preview which files would change (dry-run)
  topmark strip src

  # Apply: remove headers in-place
  topmark strip --apply .
""",
    )(strip_command)
    typed_command_of(
        cli,
        "version",
        help="Show the current TopMark version.",
        epilog="""
Displays the currently installed version of TopMark.
Use this command to verify which version of TopMark is installed in your environment.
""",
    )(version_command)
    typed_command_of(
        cli,
        "dump-config",
        help="Dump the final merged config as TOML (after CLI overrides).",
        epilog="""
Outputs the merged TopMark configuration as TOML, after applying all config files and CLI overrides.
This shows the configuration that will be used for processing, including defaults, project config,
and any command-line options.
Use this command to inspect the effective configuration for debugging or documentation purposes.
""",
    )(dump_config_command)
    typed_command_of(
        cli,
        "filetypes",
        help="List all supported file types.",
        epilog="""
Lists all file types currently supported by TopMark, along with a brief description of each.
Use this command to see which file types can be processed and referenced in configuration.
""",
    )(filetypes_command)
    typed_command_of(
        cli,
        "init-config",
        help="Print a starter config file to stdout.",
        epilog="""
Generates a starter TopMark configuration file and prints it to stdout.
Use this command to create an initial config you can adjust for your project.
The output includes default values and a header block.
""",
    )(init_config_command)
    typed_command_of(
        cli,
        "show-defaults",
        help="Display the built-in default configuration.",
        epilog="""
Shows the built-in default TopMark configuration as TOML, including a generated header.
This is the configuration used if no project or user config is provided.
Use this command to review the default values and structure for TopMark config files.
""",
    )(show_defaults_command)
    _commands_registered = True


# Ensure commands are registered when the module is imported (helps tests)
ensure_commands_registered()


# This part is just for direct script execution, e.g., `python src/topmark/cli/main.py`
if __name__ == "__main__":
    # Start the CLI - satisfy the type checker
    cast(Callable[[], None], cli)()
