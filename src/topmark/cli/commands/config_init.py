# topmark:header:start
#
#   project      : TopMark
#   file         : config_init.py
#   file_relpath : src/topmark/cli/commands/config_init.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config init` command.

Prints a starter TopMark configuration file to stdout. Uses the annotated,
commented default TOML template bundled with the package as a scaffold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.emitters.default.config import emit_config_init_default
from topmark.cli.errors import TopmarkUsageError
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_config_machine
from topmark.cli.options import underscored_trap_option
from topmark.cli_shared.emitters.markdown.config import emit_config_init_markdown
from topmark.cli_shared.emitters.shared.config import ConfigInitPrepared, prepare_config_init
from topmark.config import MutableConfig
from topmark.config.logging import get_logger
from topmark.core.formats import OutputFormat, is_machine_format
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
    from topmark.core.machine.schemas import MetaPayload

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name=CliCmd.CONFIG_INIT,
    help="Display an initial TopMark configuration file.",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@underscored_trap_option("--output_format")
@click.option(
    CliOpt.CONFIG_FOR_PYPROJECT,
    ArgKey.CONFIG_FOR_PYPROJECT,
    is_flag=True,
    help="Generate config for inclusion in pyproject.toml.",
)
@click.option(
    CliOpt.CONFIG_ROOT,
    ArgKey.CONFIG_ROOT,
    is_flag=True,
    help="Set generated config as root.",
)
def config_init_command(
    output_format: OutputFormat | None,
    pyproject: bool,
    config_root: bool,
) -> None:
    """Print a starter config file to stdout.

    Outputs an initial TopMark configuration file with default values.
    Intended as a starting point for customization in your own project.

    Notes:
        - In JSON/NDJSON modes, this command emits only a Config snapshot
          (no diagnostics).

    Args:
        output_format: Output format to use
            (``default``, ``markdown``, ``json``, or ``ndjson``).
        pyproject: If True, render as subtable under `[tool.topmark]`
            (default: False: plain topmark.toml TOML config format).
        config_root: If True, set config as root (stops further config resoution)

    Raises:
        NotImplementedError: When providing an unsupported OutputType.
        TopmarkUsageError: When --root or --pyproject is specified in combination
            with a machine format
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    if is_machine_format(fmt):
        # Disable color mode for machine formats
        ctx.obj[ArgKey.COLOR_ENABLED] = False
        if config_root or pyproject:
            raise TopmarkUsageError(
                f"{ctx.command.name}: {CliOpt.CONFIG_ROOT} and {CliOpt.CONFIG_FOR_PYPROJECT} "
                "are not supported with machine-readable output formats."
            )

    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        mutable_config: MutableConfig = MutableConfig.from_defaults()
        emit_config_machine(
            meta=meta,
            config=mutable_config.freeze(),
            fmt=fmt,
        )
        return

    # Human formats: use the full annotated default configuration template
    prepared: ConfigInitPrepared = prepare_config_init(
        for_pyproject=pyproject,
        root=config_root,
    )

    if fmt == OutputFormat.MARKDOWN:
        md: str = emit_config_init_markdown(
            prepared=prepared,
            verbosity_level=vlevel,
        )
        console.print(md, nl=False)
        return

    if fmt == OutputFormat.DEFAULT:
        emit_config_init_default(
            console=console,
            prepared=prepared,
            verbosity_level=vlevel,
        )
        return

    # Defensive guard in case OutputFormat gains new members
    raise NotImplementedError(f"Unsupported output format: {fmt!r}")
