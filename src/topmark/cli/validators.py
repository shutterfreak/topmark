# topmark:header:start
#
#   project      : TopMark
#   file         : validators.py
#   file_relpath : src/topmark/cli/validators.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI input validation and option policy helpers.

This module centralizes small, Click-layer checks and normalizations that are shared across
multiple commands.

Conventions:
    - `apply_*` helpers apply a policy and may mutate `ctx.obj` (for example, to disable ANSI
      color for output formats that must remain plain). Some `apply_*` helpers also return the
      effective value they set/normalized.
    - `validate_*` helpers enforce a policy and raise `TopmarkCliUsageError` when the invocation is
      invalid or unsupported.

Notes:
    - Messages should use `ctx.command_path` for consistency across command groups.
    - All `validate_*` helpers raise `TopmarkCliUsageError` on invalid usage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import TypeVar

import click

from topmark.cli.console.color import ColorMode
from topmark.cli.console.context import resolve_console
from topmark.cli.errors import TopmarkCliUsageError
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.formats import is_machine_format
from topmark.core.keys import ArgKey
from topmark.core.logging import TRACE_LEVEL
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from click.core import ParameterSource

    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.reporting import ReportScope
    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)

# Type variable for warn_and_clear generic return type
_T = TypeVar("_T")

#: Custom verbosity levels, mapped to standard logging levels
LOG_LEVELS: dict[str, int] = {
    "TRACE": TRACE_LEVEL,  # Custom TRACE (5) sits below logging.DEBUG.
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ---- Reusable validators ----


def validate_forbidden_options_in_extra_args(
    ctx: click.Context,
    *,
    forbidden_opts: Mapping[str, str],
) -> None:
    """Reject known-but-forbidden options that remain in `ctx.args`.

    This is used for commands that enable Click's permissive path-oriented parsing
    (`ignore_unknown_options=True` / `allow_extra_args=True`), where unsupported
    options would otherwise be silently accepted as extra arguments.
    """
    extra_args: list[str] = list(ctx.args)
    for opt, reason in forbidden_opts.items():
        if opt in extra_args:
            raise TopmarkCliUsageError(
                f"{ctx.command_path}: {opt} is not supported for this command. {reason}"
            )


def validate_mutually_exclusive(
    ctx: click.Context,
    *,
    flags: dict[str, bool],
    message: str | None = None,
) -> None:
    """Validate that at most one of the provided flags is enabled.

    This is a small Click-oriented utility for enforcing mutual exclusion
    between boolean CLI options.

    Args:
        ctx: Active Click context (used for `ctx.command_path` in messages).
        flags: Mapping of user-facing option spellings (e.g. `"--add-only"`)
            to their parsed boolean values.
        message: Optional override for the error message. When omitted, a
            standard message using the enabled option spellings is emitted.

    Raises:
        TopmarkCliUsageError: If more than one flag is enabled.
    """
    enabled: list[str] = [opt for opt, is_on in flags.items() if is_on]
    if len(enabled) <= 1:
        return

    cmd: str = ctx.command_path
    if message is None:
        # Keep message stable and easy to read.
        joined: str = " and ".join(enabled) if len(enabled) == 2 else ", ".join(enabled)
        message = f"{cmd}: {joined} are mutually exclusive."

    raise TopmarkCliUsageError(message)


def validate_machine_format_forbids_flags(
    ctx: click.Context,
    *,
    fmt: OutputFormat,
    flags: Mapping[str, bool],
    reason: str,
) -> None:
    """Validate that certain flags are forbidden when a machine-readable output format is used.

    This is a Click-layer policy helper to enforce that specific CLI options are not
    compatible with machine-readable output formats (e.g. JSON, NDJSON).

    Args:
        ctx: Active Click context (used for `ctx.command_path` in messages).
        fmt: Effective output format selected for the command.
        flags: Mapping of user-facing option spellings to their parsed boolean values.
        reason: Explanation string appended to the error message. Should include a
            leading verb phrase such as "is not supported" or "are not supported".

    Raises:
        TopmarkCliUsageError: If any of the specified flags are enabled with a machine format.
    """
    if not is_machine_format(fmt):
        return

    enabled: list[str] = [opt for opt, is_on in flags.items() if is_on]
    if not enabled:
        return

    cmd: str = ctx.command_path
    if len(enabled) == 1:
        opts: str = enabled[0]
    elif len(enabled) == 2:
        opts = " and ".join(enabled)
    else:
        opts = ", ".join(enabled)

    raise TopmarkCliUsageError(f"{cmd}: {CliOpt.OUTPUT_FORMAT}={fmt.value}: {opts} {reason}")


# ---- Reusable non-raising policy helpers ----


def warn_and_clear(
    ctx: click.Context,
    *,
    message: str,
    obj_key: str,
    cleared_value: _T,
) -> _T:
    """Emit a warning and clear a value in the Click context object.

    This helper is useful for apply_* policies that need to warn the user about ignored
    options and then clear the corresponding values in `ctx.obj`.

    Args:
        ctx: Active Click context containing CLI state and console.
        message: Warning message to emit.
        obj_key: The key in `ctx.obj` to clear (`ArgKey.*` string value).
        cleared_value: The value to set for the cleared key.

    Returns:
        The cleared value.
    """
    console: ConsoleProtocol = ctx.obj[ArgKey.CONSOLE]
    console.warn(message)
    ctx.obj[obj_key] = cleared_value
    return cleared_value


def warn_if_report_scope_ignored(
    ctx: click.Context,
    *,
    output_format: OutputFormat,
    summary_mode: bool,
    report: ReportScope,
) -> None:
    """Warn when an explicitly provided `--report` value will have no effect.

    `--report` only affects human per-file output. It is ignored when:

    - a machine-readable output format is selected, or
    - summary mode is enabled.

    To avoid noisy warnings for the default case, this helper only emits a
    warning when the user explicitly provided `--report` on the command line.

    Warnings are emitted through the CLI console helper so machine-readable payloads on stdout
    remain unchanged.

    Args:
        ctx: Active Click context.
        output_format: Effective output format.
        summary_mode: Whether summary-only mode is enabled.
        report: Effective report scope.
    """
    param_source: ParameterSource | None = ctx.get_parameter_source(ArgKey.REPORT)
    if param_source is not click.core.ParameterSource.COMMANDLINE:
        return

    msgs: list[str] = []

    if is_machine_format(output_format):
        msgs.append(
            f"Note: {ctx.command_path}: {CliOpt.REPORT}={report.value} is ignored when "
            f"{CliOpt.OUTPUT_FORMAT}={output_format.value}."
        )
    if summary_mode:
        msgs.append(
            f"Note: {ctx.command_path}: {CliOpt.REPORT}={report.value} is ignored when "
            f"{CliOpt.RESULTS_SUMMARY_MODE} is enabled."
        )
    if not msgs:
        return

    console: ConsoleProtocol = resolve_console()
    for msg in msgs:
        console.warn(msg)


def apply_color_policy_for_output_format(
    ctx: click.Context,
    *,
    fmt: OutputFormat,
) -> None:
    """Enforce the CLI color policy for the selected output format.

    Colorized (ANSI) output is only supported for `OutputFormat.TEXT`. For all other formats
    (e.g. `markdown`, `json`, `ndjson`), ANSI color codes must be disabled to avoid corrupting
    structured or copy/paste-friendly output.

    Behavior:
        - If `fmt` is not `OutputFormat.TEXT`, force `ArgKey.COLOR_ENABLED` to `False`.
        - If the user explicitly requested `--color=always` and the format
          does not support color, emit a warning explaining that the option
          is being ignored.

    This helper mutates `ctx.obj` and is intended to be called by subcommands after the effective
    output format has been resolved.

    Requires in `ctx.obj`:
        - `ArgKey.CONSOLE`: The active `ConsoleLike` instance.
        - `ArgKey.COLOR_MODE`: The color mode specified with `--color ColorMode` or `--no-color`.
        - `ArgKey.COLOR_ENABLED`: Whether color mode is effectively enabled.

    Args:
        ctx: Active Click context containing CLI state and console.
        fmt: Effective output format selected for the command.
    """
    if fmt != OutputFormat.TEXT:
        # ANSI color is only supported for OutputFormat.TEXT (human) output.
        color_mode: ColorMode | None = ctx.obj.get(ArgKey.COLOR_MODE)

        # Warn only when the user explicitly forced color.
        if color_mode == ColorMode.ALWAYS:
            warn_and_clear(
                ctx,
                message=(
                    f"Note: {ctx.command_path}: {CliOpt.COLOR_MODE}={color_mode} is ignored "
                    f"when {CliOpt.OUTPUT_FORMAT}={fmt.value}."
                ),
                obj_key=ArgKey.COLOR_ENABLED,
                cleared_value=False,
            )

        # Ensure downstream emitters do not use ANSI styling.
        ctx.obj[ArgKey.COLOR_ENABLED] = False


def apply_ignore_positional_paths_policy(
    ctx: click.Context,
    *,
    warn_stdin_dash: bool = True,
) -> None:
    """Ignore positional PATHS for file-agnostic commands.

    Some CLI commands do not operate on input files (for example, configuration inspection
    commands like ``topmark config check``). When such commands are implemented with
    ``allow_extra_args=True`` / ``ignore_unknown_options=True``, Click places unexpected
    positional arguments into ``ctx.args``.

    This helper applies a consistent policy:

    - If any positional arguments were provided, emit a warning that they are ignored.
    - If ``"-"`` was provided (STDIN sentinel) and ``warn_stdin_dash`` is enabled, emit a
      dedicated warning that STDIN is ignored.
    - Clear ``ctx.args`` so downstream logic can assume the command is file-agnostic.

    Messages use Click's computed `ctx.command_path` (for example, "topmark config check"), which
    already includes the full group/subcommand path.

    Args:
        ctx: Active Click context.
        warn_stdin_dash: If True, emit an extra warning when ``"-"`` is present.

    Returns:
        None. This helper mutates ``ctx.args`` in-place.
    """
    console: ConsoleProtocol = ctx.obj[ArgKey.CONSOLE]
    cmd: str = ctx.command_path

    original_args: list[str] = list(ctx.args)
    if not original_args:
        return

    if warn_stdin_dash and "-" in original_args:
        console.warn(
            f"Note: {cmd} is file-agnostic; '-' (content from STDIN) is ignored.",
        )

    console.warn(
        f"Note: {cmd} is file-agnostic; positional paths are ignored.",
    )

    ctx.args = []


# ---- Command-specific validators ----


def validate_verbose_quiet_exclusivity(
    ctx: click.Context,
    *,
    verbose: bool,
    quiet: bool,
) -> None:
    """Validate the CLI `--verbose` / `--quiet` exclusivity.

    Args:
        ctx: Active Click context containing CLI state and console.
        verbose: Whether `--verbose` was specified.
        quiet: Whether `--quiet` was specified.

    """
    validate_mutually_exclusive(
        ctx,
        flags={
            CliOpt.VERBOSE: verbose,
            CliOpt.QUIET: quiet,
        },
    )
    # Raises: TopmarkCliUsageError: If both flags are enabled.


def validate_diff_policy_for_output_format(
    ctx: click.Context,
    *,
    diff: bool,
    fmt: OutputFormat,
) -> None:
    """Validate that unified diffs are only supported with human-readable output formats.

    Unified diffs are a human-facing rendering feature and are not supported for machine-readable
    output (`json`/`ndjson`). If `--diff` is requested with a machine format, raise a
    `TopmarkCliUsageError`.

    Args:
        ctx: Active Click context containing CLI state and console.
        diff: Whether the user requested unified diffs.
        fmt: Effective output format for this invocation.
    """
    validate_machine_format_forbids_flags(
        ctx,
        fmt=fmt,
        flags={CliOpt.RENDER_DIFF: diff},
        reason="is not supported with machine-readable output formats.",
    )
    # Raises: TopmarkCliUsageError: If diff is True and fmt is JSON/NDJSON.


def validate_human_only_config_flags_for_machine_format(
    ctx: click.Context,
    *,
    config_root: bool,
    for_pyproject: bool,
    fmt: OutputFormat,
) -> None:
    """Validate that human-only config template flags are not used with machine formats.

    Some options only affect human-facing template rendering (e.g. injecting `root = true`
    or emitting a pyproject-scoped `[tool.topmark]` header). Machine-readable output formats
    (JSON/NDJSON) should remain schema-driven and are not compatible with such template-only
    toggles.

    Args:
        ctx: Active Click context.
        config_root: Whether the user requested `--root`.
        for_pyproject: Whether the user requested `--pyproject`.
        fmt: Effective output format for this invocation.
    """
    validate_machine_format_forbids_flags(
        ctx,
        fmt=fmt,
        flags={
            CliOpt.CONFIG_ROOT: config_root,
            CliOpt.CONFIG_FOR_PYPROJECT: for_pyproject,
        },
        reason="are not supported with machine-readable output formats.",
    )
    # Raises: TopmarkCliUsageError: If a machine format is selected and any human-only template flag
    # is set.


def validate_stdin_dash_requires_piped_input(
    ctx: click.Context,
    *,
    files_from: list[str] | None,
    include_from: list[str] | None,
    exclude_from: list[str] | None,
) -> None:
    """Fail fast if a `--*-from -` option is used without piped STDIN.

    Args:
        ctx: Active Click context.
        files_from: Parsed `--files-from` values (may be None).
        include_from: Parsed `--include-from` values (may be None).
        exclude_from: Parsed `--exclude-from` values (may be None).

    Raises:
        TopmarkCliUsageError: if any of the `--*-from` options contain '-' but STDIN is a TTY.
    """
    uses_dash: bool = (
        ("-" in files_from if files_from else False)
        or ("-" in include_from if include_from else False)
        or ("-" in exclude_from if exclude_from else False)
    )
    if not uses_dash:
        return

    import sys

    if sys.stdin.isatty():
        cmd: str = ctx.command_path
        raise TopmarkCliUsageError(
            f"{cmd}: '-' requests patterns/paths from STDIN, but no STDIN is piped. "
            "Pipe input (e.g. `printf 'pat\\n' | ... --exclude-from -`) or use a file path."
        )
