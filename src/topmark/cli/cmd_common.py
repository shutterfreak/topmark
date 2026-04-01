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
from typing import Final

import click

from topmark.cli.console.click_console import Console
from topmark.cli.console.color import resolve_color_mode
from topmark.cli.console.context import resolve_console
from topmark.cli.options import ColorMode
from topmark.cli.options import resolve_verbosity
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.cli.validators import validate_verbose_quiet_exclusivity
from topmark.config.model import MutableConfig
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import PolicyOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.config.resolution import load_resolved_config
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.constants import CLI_OVERRIDE_STR
from topmark.core.keys import ArgKey
from topmark.core.logging import resolve_env_log_level
from topmark.core.logging import setup_logging
from topmark.core.presentation import StyleRole
from topmark.resolution.files import resolve_file_list
from topmark.runtime.model import RunOptions
from topmark.runtime.writer_options import WriterOptions
from topmark.runtime.writer_options import apply_resolved_writer_options
from topmark.toml.guards import as_object_dict
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.resolution import resolve_topmark_toml_sources
from topmark.utils.merge import none_if_empty

if TYPE_CHECKING:
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.io import InputPlan
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.core.exit_codes import ExitCode

_CTX_RESOLVED_WRITER_OPTIONS_KEY: Final[str] = "_topmark_resolved_writer_options"


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


def build_file_list(
    *,
    run_options: RunOptions,
    config: Config,
    temp_path: Path | None,
) -> list[Path]:
    """Return the files to process, respecting content-on-STDIN mode.

    - In content-on-STDIN mode, return the single temp path created for the
      staged input content.
    - Otherwise, delegate to the unified resolver that uses `config.files`,
      `files_from`, include/exclude patterns, and file types.

    Args:
        run_options: Invocation-wide runtime options for the current run.
        config: Effective run config used for file discovery.
        temp_path: Temporary file path created for content-on-STDIN mode, if any.

    Returns:
        The ordered list of files to process for the CLI invocation.

    Raises:
        RuntimeError: If `temp_path` is undefined in `stdin_mode`.
    """
    if run_options.stdin_mode:
        if temp_path is None:
            raise RuntimeError("temp_path should not be undefined in stdin_mode")
        return [temp_path]
    return resolve_file_list(config)


def build_run_options(
    *,
    apply_changes: bool,
    write_mode: str | None,
    stdin_mode: bool,
    stdin_filename: str | None,
    prune_views: bool = True,
) -> RunOptions:
    """Build invocation-wide runtime options for a CLI command.

    Args:
        apply_changes: Whether the command should write changes.
        write_mode: Effective CLI write mode (`stdout`, `atomic`, or `inplace`).
        stdin_mode: Whether the command is operating in content-on-STDIN mode.
        stdin_filename: Synthetic file name associated with STDIN content, if any.
        prune_views: If `True`, trim heavy views after the run (keeps summaries). Default: `True`.

    Returns:
        The execution-only runtime options for the current CLI invocation.

    When available on the current Click context, resolved persisted writer
    preferences from TopMark TOML discovery are overlaid unless explicit
    runtime intent already selected a conflicting output mode or file write
    strategy.
    """
    output_target: OutputTarget | None = None
    file_write_strategy: FileWriteStrategy | None = None

    if stdin_mode and apply_changes or write_mode == OutputTarget.STDOUT.value:
        output_target = OutputTarget.STDOUT
        file_write_strategy = None
    elif write_mode == FileWriteStrategy.ATOMIC.value:
        output_target = OutputTarget.FILE
        file_write_strategy = FileWriteStrategy.ATOMIC
    elif write_mode == FileWriteStrategy.INPLACE.value:
        output_target = OutputTarget.FILE
        file_write_strategy = FileWriteStrategy.INPLACE

    run_options = RunOptions(
        apply_changes=apply_changes,
        output_target=output_target,
        file_write_strategy=file_write_strategy,
        stdin_mode=stdin_mode,
        stdin_filename=stdin_filename,
        prune_views=prune_views,
    )

    ctx: click.Context | None = click.get_current_context(silent=True)
    writer_options: WriterOptions | None = None
    if ctx is not None:
        ctx_obj_raw: object = ctx.obj
        ctx_obj: dict[str, object] = as_object_dict(ctx_obj_raw)
        candidate: object | None = ctx_obj.get(_CTX_RESOLVED_WRITER_OPTIONS_KEY)
        if isinstance(candidate, WriterOptions):
            writer_options = candidate

    return apply_resolved_writer_options(run_options, writer_options)


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
    run_options: RunOptions,
    enable_color: bool,
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
        run_options: Invocation-wide runtime options for the current run.
        enable_color: Whether color output is enabled for this invocation.

    Returns:
        The effective console instance to use for human-facing output.
    """
    emits_content_to_stdout: bool = bool(run_options.apply_changes) and (
        run_options.stdin_mode or (run_options.output_target == OutputTarget.STDOUT)
    )

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


def build_cli_policy_overrides_from_ctx(ctx: click.Context) -> PolicyOverrides:
    """Build structured policy overrides from parsed CLI option values."""
    header_mutation_mode_obj: object = ctx.obj.get(ArgKey.POLICY_HEADER_MUTATION_MODE)
    allow_header_in_empty_files_obj: object = ctx.obj.get(ArgKey.POLICY_ALLOW_HEADER_IN_EMPTY_FILES)
    empty_insert_mode_obj: object = ctx.obj.get(ArgKey.POLICY_EMPTY_INSERT_MODE)
    render_empty_header_when_no_fields_obj: object = ctx.obj.get(
        ArgKey.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS
    )
    allow_reflow_obj: object = ctx.obj.get(ArgKey.POLICY_ALLOW_REFLOW)
    allow_content_probe_obj: object = ctx.obj.get(ArgKey.POLICY_ALLOW_CONTENT_PROBE)

    return PolicyOverrides(
        header_mutation_mode=(
            header_mutation_mode_obj
            if isinstance(header_mutation_mode_obj, HeaderMutationMode)
            else None
        ),
        allow_header_in_empty_files=(
            allow_header_in_empty_files_obj
            if isinstance(allow_header_in_empty_files_obj, bool)
            else None
        ),
        empty_insert_mode=(
            empty_insert_mode_obj if isinstance(empty_insert_mode_obj, EmptyInsertMode) else None
        ),
        render_empty_header_when_no_fields=(
            render_empty_header_when_no_fields_obj
            if isinstance(render_empty_header_when_no_fields_obj, bool)
            else None
        ),
        allow_reflow=(allow_reflow_obj if isinstance(allow_reflow_obj, bool) else None),
        allow_content_probe=(
            allow_content_probe_obj if isinstance(allow_content_probe_obj, bool) else None
        ),
    )


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
       `topmark.config.resolution.load_resolved_config()`.
    3. Apply layered CLI overrides via `topmark.config.overrides.apply_config_overrides()`.

    Resolution order remains:

        defaults -> discovered config layers -> explicit config files -> CLI overrides

    As a side effect, this helper also resolves persisted TOML writer
    preferences for the same discovery inputs and stores them on `ctx.obj` for
    later runtime-option assembly.

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

    resolved_toml: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(
        input_paths=discovery_inputs,
        extra_config_files=extra_config_files,
        strict_config_checking=None,
        no_config=no_config,
    )
    ctx.obj[_CTX_RESOLVED_WRITER_OPTIONS_KEY] = resolved_toml.writer_options

    draft: MutableConfig = load_resolved_config(
        input_paths=discovery_inputs,
        extra_config_files=extra_config_files,
        no_config=no_config,
    )

    policy_overrides: PolicyOverrides = build_cli_policy_overrides_from_ctx(ctx)
    overrides: ConfigOverrides = ConfigOverrides(
        config_origin=Path(CLI_OVERRIDE_STR),
        policy=policy_overrides,
        files=plan.paths,
        files_from=none_if_empty(plan.files_from),
        include_from=none_if_empty(plan.include_from),
        exclude_from=none_if_empty(plan.exclude_from),
        include_patterns=none_if_empty(plan.include_patterns),
        exclude_patterns=none_if_empty(plan.exclude_patterns),
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
        align_fields=align_fields,
        relative_to=relative_to,
    )

    draft = apply_config_overrides(draft, overrides=overrides)

    return draft
