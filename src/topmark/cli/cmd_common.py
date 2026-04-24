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

It also contains a small initializer (`init_common_state`) that prepares the
shared typed CLI state (`TopmarkCliState`) for commands that own verbosity,
color, and related human-output controls rather than the root command group.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

import click

from topmark.cli.console.click_console import Console
from topmark.cli.console.color import resolve_color_mode
from topmark.cli.options import ColorMode
from topmark.cli.options import normalize_verbosity
from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.state import get_cli_state
from topmark.cli.validators import validate_output_verbosity_policy
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import PolicyOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.constants import CLI_OVERRIDE_STR
from topmark.core.logging import resolve_env_log_level
from topmark.core.logging import setup_logging
from topmark.core.presentation import StyleRole
from topmark.resolution.files import resolve_file_list
from topmark.runtime.model import RunOptions
from topmark.runtime.writer_options import WriterOptions
from topmark.runtime.writer_options import apply_resolved_writer_options
from topmark.utils.merge import none_if_empty

if TYPE_CHECKING:
    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.cli.io import InputPlan
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.config.policy import MutablePolicy
    from topmark.core.exit_codes import ExitCode
    from topmark.core.formats import OutputFormat
    from topmark.toml.resolution import ResolvedTopmarkTomlSources

_CTX_RESOLVED_WRITER_OPTIONS_KEY: Final[str] = "_topmark_resolved_writer_options"


def init_common_state(
    ctx: click.Context,
    *,
    verbosity: int,
    quiet: bool,
    color_mode: ColorMode | None,
    no_color: bool,
) -> None:
    """Initialize shared UI/runtime state on the Click context.

    It initializes the shared `TopmarkCliState` stored on `ctx.obj`.

    Args:
        ctx: Current Click context; will have ``obj`` and ``color`` set.
        verbosity: Count of ``--verbose/-v`` flags (0..2).
        quiet: Whether ``--quiet/-q`` was provided.
        color_mode: Explicit color mode from ``--color`` (or ``None``).
        no_color: Whether ``--no-color`` was passed; forces color off.
    """
    state: TopmarkCliState = bootstrap_cli_state(ctx)

    # 1. Color policy for the effective command output format.
    effective_color_mode: ColorMode = (
        ColorMode.NEVER if no_color else (color_mode or ColorMode.AUTO)
    )
    # Store the resolved color mode in the Click context:
    state.color_mode = effective_color_mode
    enable_color: bool = resolve_color_mode(
        color_mode_override=effective_color_mode,
        output_format=state.output_format,
    )
    # Store whether color is enabled for this invocation.
    state.color_enabled = enable_color
    ctx.color = enable_color

    # 2. Initialize the console.
    # Respect the resolved color policy (may differ from the raw `--no-color`` flag).
    console = Console(enable_color=enable_color)
    # Store the console in the Click context:
    state.console = console

    # 3. Initialize internal logging (env-driven).
    level_env: int | None = resolve_env_log_level()
    setup_logging(level=level_env)
    # Store the resolved internal runtime log level in the Click context:
    state.log_level = level_env

    # 4. Validate output verbosity for human formats.
    fmt: OutputFormat = state.output_format

    # Store raw human-output controls so validators can normalize ignored flags.
    state.verbosity = verbosity
    state.quiet = quiet

    # Program-output verbosity / quiet policy (stored for downstream gating).
    validate_output_verbosity_policy(
        ctx,
        verbosity=verbosity,
        quiet=quiet,
        fmt=fmt,
    )

    # Store normalized effective human-output state for downstream consumers.
    state.verbosity = normalize_verbosity(state.verbosity)


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


# ---- Runtime option assembly ----


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
        state: TopmarkCliState = get_cli_state(ctx)
        candidate: object | None = state.extras.get(_CTX_RESOLVED_WRITER_OPTIONS_KEY)
        if isinstance(candidate, WriterOptions):
            writer_options = candidate

    return apply_resolved_writer_options(run_options, writer_options)


def exit_if_no_files(file_list: list[Path], *, console: ConsoleProtocol, styled: bool) -> bool:
    """Echo a friendly message and return True if there is nothing to process."""
    if not file_list:
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

    The function updates the console stored on the shared typed CLI state when
    rerouting is needed and returns the effective console instance.

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
        state: TopmarkCliState = get_cli_state(ctx)
        state.console = console
        return console

    # Fall back to the console initialized by `init_common_state`.
    return get_cli_state(ctx).console


def maybe_exit_on_error(*, code: ExitCode | None, temp_path: Path | None) -> None:
    """If an error code was encountered, cleanup and exit with it."""
    if code is not None:
        from topmark.utils.file import safe_unlink

        safe_unlink(temp_path)
        click.get_current_context().exit(code)


def build_cli_policy_overrides(state: TopmarkCliState) -> PolicyOverrides:
    """Build structured policy overrides from typed CLI state.

    Args:
        state: Shared typed CLI invocation state.

    Returns:
        Structured policy overrides derived from the mutable CLI policy object.
    """
    policy: MutablePolicy = state.policy
    return PolicyOverrides(
        header_mutation_mode=policy.header_mutation_mode,
        allow_header_in_empty_files=policy.allow_header_in_empty_files,
        empty_insert_mode=policy.empty_insert_mode,
        render_empty_header_when_no_fields=policy.render_empty_header_when_no_fields,
        allow_reflow=policy.allow_reflow,
        allow_content_probe=policy.allow_content_probe,
    )


# ---- Config/TOML preparation for a CLI run ----


def build_resolved_toml_sources_and_config_for_plan(
    *,
    ctx: click.Context,
    plan: InputPlan,
    no_config: bool,
    config_paths: list[str],
    strict_config_checking: bool | None,
    include_file_types: list[str],
    exclude_file_types: list[str],
    align_fields: bool | None,
    relative_to: str | None,
) -> tuple[
    ResolvedTopmarkTomlSources,
    MutableConfig,
]:
    """Build resolved TOML sources and a config draft for an input plan.

    This helper keeps the CLI layer intentionally thin:

    1. Compute a discovery anchor from the input plan.
    2. Resolve TOML sources once.
    3. Build the layered config draft from that resolved TOML state.
    4. Apply layered CLI overrides via
    `topmark.config.overrides.apply_config_overrides()`.

    Resolution order remains:

        defaults -> resolved TOML sources -> config draft -> CLI overrides

    As a side effect, this helper also resolves persisted TOML writer
    preferences for the same discovery inputs and stores them on the shared
    typed CLI state for later runtime-option assembly.

    Args:
        ctx: Click context carrying the shared typed CLI state.
        plan: Input plan containing paths, STDIN metadata, and pattern-source
            options.
        no_config: Whether to skip discovered config files.
        config_paths: Explicit extra config files passed on the CLI.
        strict_config_checking: Optional CLI override for strict config
            checking. `None` means that strictness should be taken from the
            resolved TOML sources.
        include_file_types: CLI include file-type filters.
        exclude_file_types: CLI exclude file-type filters.
        align_fields: Optional CLI override for header alignment.
        relative_to: Optional CLI override for header-relative path rendering.

    Returns:
        A tuple containing:
            - resolved TOML-side state for the current run
            - mutable config draft ready to be frozen
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

    resolved_toml, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=discovery_inputs,
        extra_config_files=extra_config_files,
        strict_config_checking=strict_config_checking,
        no_config=no_config,
    )

    state: TopmarkCliState = bootstrap_cli_state(ctx)
    state.extras[_CTX_RESOLVED_WRITER_OPTIONS_KEY] = resolved_toml.writer_options

    policy_overrides: PolicyOverrides = build_cli_policy_overrides(state)
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

    return resolved_toml, draft
