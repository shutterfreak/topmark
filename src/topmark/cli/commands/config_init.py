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

import sys
from importlib.resources import files
from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.errors import TopmarkUsageError
from topmark.cli.keys import CliOpt
from topmark.cli.utils import emit_config_machine, render_toml_block
from topmark.cli_shared.utils import OutputFormat
from topmark.config import MutableConfig
from topmark.config.io import nest_toml_under_section
from topmark.config.logging import get_logger
from topmark.constants import (
    DEFAULT_TOML_CONFIG_NAME,
    DEFAULT_TOML_CONFIG_PACKAGE,
)
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    import sys

    if sys.version_info >= (3, 14):
        # Python 3.14+: Traversable moved here
        from importlib.resources.abc import Traversable
    else:
        # Python <=3.13
        from importlib.abc import Traversable

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


@click.command(
    name="init-config",
    help="Display an initial TopMark configuration file.",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@click.option(
    CliOpt.CONFIG_FOR_PYPROJECT,
    ArgKey.CONFIG_FOR_PYPROJECT,
    is_flag=True,
    help="Generate config for inclusion in pyproject.toml.",
)
def config_init_command(
    output_format: OutputFormat | None,
    pyproject: bool,
) -> None:
    """Print a starter config file to stdout.

    Outputs an initial TopMark configuration file with default values.
    Intended as a starting point for customization in your own project.

    Notes:
        - In JSON/NDJSON modes, this command emits only a Config snapshot
          (no diagnostics).

    Args:
        output_format (OutputFormat | None): Output format to use
            (``default``, ``markdown``, ``json``, or ``ndjson``).
        pyproject (bool): If True, render as subtable under `[tool.topmark]`
            (default: False: plain topmark.toml TOML config format).

    Raises:
        NotImplementedError: When providing an unsupported OutputType.
        TopmarkUsageError: When --pyproject is specified in combination
            with a machine format
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        if pyproject:
            raise TopmarkUsageError(
                f"{ctx.command.name}: {CliOpt.CONFIG_FOR_PYPROJECT} is not supported "
                "with machine-readable output formats."
            )

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    # For human formats, use the full annotated default configuration template

    resource: Traversable = files(DEFAULT_TOML_CONFIG_PACKAGE).joinpath(DEFAULT_TOML_CONFIG_NAME)
    try:
        toml_text: str = resource.read_text(encoding="utf8")
    except OSError as exc:
        # Fallback: if the template file is not available, fall back to the synthesized defaults
        toml_text = MutableConfig.get_default_config_toml()
        click.secho(f"Falling back to synthesized default config: {exc}", fg="red", err=True)
        logger.warning("Falling back to synthesized default config: %s", exc)

    if fmt == OutputFormat.DEFAULT:
        if pyproject:
            # We want to wrap the content in [tool.topmark]
            target_section = "tool.topmark"

            toml_text = nest_toml_under_section(toml_text, target_section)

        render_toml_block(
            console=console,
            title="Initial TopMark Configuration (TOML):",
            toml_text=toml_text,
            verbosity_level=vlevel,
        )

    elif fmt == OutputFormat.MARKDOWN:
        # Markdown: heading plus fenced TOML block, no ANSI styling.
        console.print("# Initial TopMark Configuration (TOML)")
        console.print()
        console.print("```toml")
        console.print(toml_text.rstrip("\n"))
        console.print("```")

    elif fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        mutable_config: MutableConfig = MutableConfig.from_defaults()
        emit_config_machine(mutable_config.freeze(), fmt=fmt)

    else:
        # Defensive guard in case OutputFormat gains new members
        raise NotImplementedError(f"Unsupported output format: {fmt!r}")

    # No explicit return needed for Click commands.
