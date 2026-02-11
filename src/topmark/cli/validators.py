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
    - `validate_*` helpers enforce a policy and raise `TopmarkUsageError` when the invocation is
      invalid or unsupported.

Notes:
    - Messages should use `ctx.command_path` for consistency across command groups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.errors import TopmarkUsageError
from topmark.cli.keys import CliOpt
from topmark.cli_shared.color import ColorMode
from topmark.config.logging import get_logger
from topmark.core.formats import OutputFormat, is_machine_format
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    import click

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)

# "Apply" policies (mutating)


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
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]
    cmd: str = ctx.command_path

    if fmt != OutputFormat.TEXT:
        # ANSI color is only supported for OutputFormat.TEXT (human) output.
        color_mode: ColorMode | None = ctx.obj.get(ArgKey.COLOR_MODE)

        # Warn only when the user explicitly forced color.
        if color_mode == ColorMode.ALWAYS:
            console.warn(
                f"Note: {cmd}: {CliOpt.COLOR_MODE}={color_mode} is ignored "
                f"when {CliOpt.OUTPUT_FORMAT}={fmt.value}."
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
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]
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


def apply_ignore_files_from_policy(
    ctx: click.Context,
    *,
    files_from: list[str] | None,
) -> list[str]:
    """Ignore `--files-from` for commands that do not accept external file lists.

    Some commands are file-agnostic and/or operate purely on configuration state. For those
    commands, `--files-from` is meaningless and can confuse users because it suggests that file
    discovery is involved.

    Policy:
        - If `files_from` is non-empty, emit a warning and clear `ArgKey.FILES_FROM` in `ctx.obj`.
        - Always return the effective `files_from` list (empty when ignored).

    Args:
        ctx: Active Click context.
        files_from: Parsed `--files-from` values (may be None).

    Returns:
        The effective `files_from` list (empty when ignored).
    """
    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]
    cmd: str = ctx.command_path

    if files_from:
        console.warn(
            f"Note: {cmd} ignores {CliOpt.FILES_FROM} "
            "(file lists are not part of the configuration).",
        )
        ctx.obj[ArgKey.FILES_FROM] = []
        return []
    return files_from or []


# "Validate" policies (raising)


def validate_diff_policy_for_output_format(
    ctx: click.Context,
    *,
    diff: bool,
    fmt: OutputFormat,
) -> None:
    """Validate the CLI diff policy for the selected output format.

    Unified diffs are a human-facing rendering feature and are not supported for machine-readable
    output (`json`/`ndjson`). If `--diff` is requested with a machine format, raise a
    `TopmarkUsageError` with a clear message.

    Args:
        ctx: Active Click context containing CLI state and console.
        diff: Whether the user requested unified diffs.
        fmt: Effective output format for this invocation.

    Raises:
        TopmarkUsageError: If diff is True and fmt is JSON/NDJSON.
    """
    cmd: str = ctx.command_path
    opts: str = f"{CliOpt.OUTPUT_FORMAT}={fmt.value}"

    if is_machine_format(fmt) and diff:
        # Diffs are human-only; machine formats must remain structured.
        raise TopmarkUsageError(
            f"{cmd}: {opts}: {CliOpt.RENDER_DIFF} is not supported "
            "with machine-readable output formats."
        )


def validate_check_add_update_policy_exclusivity(
    ctx: click.Context,
    *,
    add_only: bool,
    update_only: bool,
) -> None:
    """Validate the CLI add_only / update_only exclusivity policy for the `check` command.

    The `--add-only` and `--update-only` options represent incompatible operation modes. If both are
    enabled, raise a `TopmarkUsageError` explaining that the options are mutually exclusive.

    Args:
        ctx: Active Click context containing CLI state and console.
        add_only: Whether we should only add nonexistent headers.
        update_only: Whether we should only update existing headers.

    Raises:
        TopmarkUsageError: If both flags are enabled.
    """
    cmd: str = ctx.command_path

    if add_only and update_only:
        raise TopmarkUsageError(
            f"{cmd}: {CliOpt.POLICY_CHECK_ADD_ONLY} and "
            f"{CliOpt.POLICY_CHECK_UPDATE_ONLY} are mutually exclusive."
        )


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

    Raises:
        TopmarkUsageError: If a machine format is selected and any human-only template flag is set.
    """
    cmd: str = ctx.command_path
    opts: str = f"{CliOpt.OUTPUT_FORMAT}={fmt.value}"

    if is_machine_format(fmt) and (config_root or for_pyproject):
        raise TopmarkUsageError(
            f"{cmd}: {opts}: {CliOpt.CONFIG_ROOT} and "
            f"{CliOpt.CONFIG_FOR_PYPROJECT} are not supported "
            "with machine-readable output formats."
        )
