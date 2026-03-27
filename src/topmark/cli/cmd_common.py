# topmark:header:start
#
#   project      : TopMark
#   file         : cmd_common.py
#   file_relpath : src/topmark/cli/cmd_common.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common command utilities for Click-based commands.

This module holds small, focused helpers used by multiple CLI commands.
They intentionally avoid policy (exit code rules, messages) and only
encapsulate plumbing such as running pipelines, filtering, and error exits.

It also contains a small initializer (`init_common_state`) that populates
`ctx.obj` with the shared UI/runtime state (verbosity, color, console, meta)
when these options are owned by individual commands rather than the root
command group.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from topmark.cli.console.click_console import Console
from topmark.cli.console.color import resolve_color_mode
from topmark.cli.console.context import resolve_console
from topmark.cli.options import ColorMode
from topmark.cli.options import resolve_verbosity
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.cli.validators import validate_verbose_quiet_exclusivity
from topmark.config.io.resolution import load_resolved_config
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import PolicyOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import HeaderMutationMode
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.core.keys import ArgKey
from topmark.core.logging import resolve_env_log_level
from topmark.core.logging import setup_logging
from topmark.core.presentation import StyleRole
from topmark.resolution.files import resolve_file_list

if TYPE_CHECKING:
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.io import InputPlan
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.core.exit_codes import ExitCode


def init_common_state(
    ctx: click.Context,
    *,
    verbose: int,
    quiet: int,
    color_mode: ColorMode | None,
    no_color: bool,
) -> None:
    """Initialize shared UI/runtime state on the Click context.

    It populates `ctx.obj` with:
    - `ArgKey.VERBOSITY_LEVEL`
    - `ArgKey.LOG_LEVEL` (from environment)
    - `ArgKey.COLOR_MODE` and `ArgKey.COLOR_ENABLED`
    - `ArgKey.CONSOLE`

    Args:
        ctx: Current Click context; will have ``obj`` and ``color`` set.
        verbose: Count of ``-v`` flags (0..2).
        quiet: Count of ``-q`` flags (0..2).
        color_mode: Explicit color mode from ``--color`` (or ``None``).
        no_color: Whether ``--no-color`` was passed; forces color off.
    """
    ctx.obj = ctx.obj or {}

    # Program-output verbosity (stored for downstream gating).
    validate_verbose_quiet_exclusivity(ctx, verbose=verbose > 0, quiet=quiet > 0)

    level_cli: int = resolve_verbosity(verbose, quiet)
    ctx.obj[ArgKey.VERBOSITY_LEVEL] = level_cli

    # Internal logging (env-driven).
    level_env: int | None = resolve_env_log_level()
    ctx.obj[ArgKey.LOG_LEVEL] = level_env
    setup_logging(level=level_env)

    # Color policy (command decides output format later; `output_format=None` here).
    effective_color_mode: ColorMode = (
        ColorMode.NEVER if no_color else (color_mode or ColorMode.AUTO)
    )
    ctx.obj[ArgKey.COLOR_MODE] = effective_color_mode
    enable_color: bool = resolve_color_mode(
        color_mode_override=effective_color_mode,
        output_format=None,
    )
    ctx.obj[ArgKey.COLOR_ENABLED] = enable_color
    ctx.color = enable_color

    # Respect the resolved color policy (may differ from the raw --no-color flag).
    console = Console(enable_color=enable_color)
    ctx.obj[ArgKey.CONSOLE] = console


def build_file_list(config: Config, *, stdin_mode: bool, temp_path: Path | None) -> list[Path]:
    """Return the files to process, respecting STDIN content mode.

    - If content-on-STDIN mode, return the single temp path.
    - Otherwise, delegate to the unified resolver that uses `config.files`,
      `files_from`, include/exclude patterns, and file types.
    """
    if stdin_mode:
        if temp_path is None:
            raise RuntimeError("temp_path should not be undefined in stdin_mode")
        return [temp_path]
    return resolve_file_list(config)


def exit_if_no_files(file_list: list[Path], *, styled: bool) -> bool:
    """Echo a friendly message and return True if there is nothing to process."""
    if not file_list:
        console: ConsoleProtocol = resolve_console()
        info_styler: TextStyler = style_for_role(StyleRole.INFO, styled=styled)
        console.print(info_styler("\nℹ️  No files to process.\n"))
        return True
    return False


def maybe_route_console_to_stderr(
    ctx: click.Context,
    *,
    enable_color: bool,
    apply_changes: bool,
    stdin_mode: bool,
    write_mode: str | None,
) -> ConsoleProtocol:
    """Route human-facing console output to stderr when stdout carries file content.

    TopMark can emit rewritten file content to STDOUT in two situations:

    - content-on-STDIN mode (a lone `-` path) when ``--apply`` is set; and
    - when ``--write-mode=stdout`` is used with ``--apply``.

    In both cases, the command must keep STDOUT clean for the content stream so
    that output can be piped safely. Human-facing output (summaries, warnings,
    diagnostics) is therefore routed to STDERR.

    The function updates ``ctx.obj[ArgKey.CONSOLE]`` when rerouting is needed and
    returns the effective console instance.

    Args:
        ctx: Current Click context.
        enable_color: Whether color output is enabled for this invocation.
        apply_changes: Whether ``--apply`` is set (only then can content be emitted).
        stdin_mode: Whether the invocation is in content-on-STDIN mode.
        write_mode: Effective write mode (``"stdout"`` emits content to STDOUT).

    Returns:
        The effective console instance to use for human-facing output.
    """
    emits_content_to_stdout: bool = bool(apply_changes) and (stdin_mode or (write_mode == "stdout"))

    if emits_content_to_stdout:
        console = Console(
            enable_color=enable_color,
            out=sys.stderr,
            err=sys.stderr,
        )
        ctx.obj[ArgKey.CONSOLE] = console
        return console

    # Fall back to the console initialized by `init_common_state`.
    return resolve_console()


def maybe_exit_on_error(*, code: ExitCode | None, temp_path: Path | None) -> None:
    """If an error code was encountered, cleanup and exit with it."""
    if code is not None:
        from topmark.utils.file import safe_unlink

        safe_unlink(temp_path)
        click.get_current_context().exit(code)


def build_config_for_plan(
    *,
    ctx: click.Context,
    plan: InputPlan,
    no_config: bool,
    config_paths: list[str],
    include_file_types: list[str],
    exclude_file_types: list[str],
    align_fields: bool | None,
    relative_to: str | None,
) -> MutableConfig:
    """Build a config draft for an input plan using config-layer helpers only.

    The CLI layer stays intentionally thin:

    1. Compute a discovery anchor from the input plan.
    2. Delegate layered config discovery/merge to
       `topmark.config.io.resolution.load_resolved_config()`.
    3. Apply CLI overrides via `topmark.config.overrides.apply_config_overrides()`.

    Resolution order remains:

        defaults -> discovered config layers -> explicit config files -> CLI overrides

    Args:
        ctx: Click context carrying normalized command options in `ctx.obj`.
        plan: Input plan containing paths, stdin metadata, and pattern-source options.
        no_config: Whether to skip discovered config files.
        config_paths: Explicit extra config files passed on the CLI.
        include_file_types: CLI include file-type filters.
        exclude_file_types: CLI exclude file-type filters.
        align_fields: Optional CLI override for header alignment.
        relative_to: Optional CLI override for header-relative path rendering.

    Returns:
        Mutable configuration draft ready to be frozen.
    """

    def _resolve_discovery_inputs() -> list[Path] | None:
        """Return input paths used only to select the discovery anchor.

        In STDIN mode, `stdin_filename` can still provide a directory hint
        (for example `pkg/module.py`). Otherwise, use the normal path list,
        or let the config layer fall back to CWD.
        """
        if plan.stdin_mode is True:
            stdin_name: str | None = plan.stdin_filename
            if stdin_name:
                sf: Path = Path(stdin_name)
                if sf.parent != Path():
                    if sf.is_absolute():
                        return [sf.parent]
                    return [(Path.cwd() / sf.parent).resolve()]
            return None

        resolved: list[Path] = [Path(p) for p in plan.paths if p and p != "-"]
        return resolved or None

    discovery_inputs: list[Path] | None = _resolve_discovery_inputs()
    extra_config_files: list[Path] = [Path(p) for p in config_paths]

    draft: MutableConfig = load_resolved_config(
        input_paths=discovery_inputs,
        extra_config_files=extra_config_files,
        no_config=no_config,
    )

    header_mutation_mode: HeaderMutationMode | None
    if ctx.obj.get(ArgKey.POLICY_CHECK_ADD_ONLY):
        header_mutation_mode = HeaderMutationMode.ADD_ONLY
    elif ctx.obj.get(ArgKey.POLICY_CHECK_UPDATE_ONLY):
        header_mutation_mode = HeaderMutationMode.UPDATE_ONLY
    else:
        header_mutation_mode = None

    output_target: OutputTarget | None = None
    file_write_strategy: FileWriteStrategy | None = None
    write_mode_obj: object = ctx.obj.get(ArgKey.WRITE_MODE)
    write_mode: str | None = None if write_mode_obj is None else str(write_mode_obj)

    if write_mode == OutputTarget.STDOUT.value:
        output_target = OutputTarget.STDOUT
        file_write_strategy = None
    elif write_mode == FileWriteStrategy.ATOMIC.value:
        output_target = OutputTarget.FILE
        file_write_strategy = FileWriteStrategy.ATOMIC
    elif write_mode == FileWriteStrategy.INPLACE.value:
        output_target = OutputTarget.FILE
        file_write_strategy = FileWriteStrategy.INPLACE

    overrides: ConfigOverrides = ConfigOverrides(
        policy=PolicyOverrides(
            header_mutation_mode=header_mutation_mode,
        ),
        apply_changes=ctx.obj.get(ArgKey.APPLY_CHANGES),
        output_target=output_target,
        file_write_strategy=file_write_strategy,
        files=plan.paths,
        files_from=plan.files_from,
        stdin_mode=plan.stdin_mode,
        stdin_filename=plan.stdin_filename,
        include_patterns=plan.include_patterns,
        include_from=plan.include_from,
        exclude_patterns=plan.exclude_patterns,
        exclude_from=plan.exclude_from,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        align_fields=align_fields,
        relative_to=relative_to,
    )

    draft = apply_config_overrides(draft, overrides=overrides)

    return draft
