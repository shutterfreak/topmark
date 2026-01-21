# topmark:header:start
#
#   project      : TopMark
#   file         : config_defaults.py
#   file_relpath : src/topmark/cli/commands/config_defaults.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `config defaults` command.

Displays the built-in default TopMark configuration. This includes the default
header template and the default TOML configuration bundled with the package.
Intended as a reference for users customizing their own configuration files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.keys import ArgKey, CliOpt
from topmark.cli.utils import emit_config_machine, render_toml_block
from topmark.cli_shared.utils import OutputFormat
from topmark.config import MutableConfig

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


@click.command(
    name="show-defaults",
    help="Display the built-in default TopMark configuration file.",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
def config_defaults_command(
    output_format: OutputFormat | None,
) -> None:
    """Display the built-in default configuration.

    Outputs the TopMark default configuration file as bundled with the package.
    Useful as a reference for configuration structure and default values.

    Notes:
        - In JSON/NDJSON modes, this command emits only a Config snapshot
          (no diagnostics).

    Args:
        output_format (OutputFormat | None): Output format to use
            (``default``, ``markdown``, ``json``, or ``ndjson``).

    Raises:
        NotImplementedError: When providing an unsupported OutputType.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    toml_text: str = MutableConfig.to_cleaned_toml(MutableConfig.get_default_config_toml())

    if fmt == OutputFormat.DEFAULT:
        render_toml_block(
            console=console,
            title="Default TopMark Configuration (TOML):",
            toml_text=toml_text,
            verbosity_level=vlevel,
        )

    elif fmt == OutputFormat.MARKDOWN:
        # Markdown: heading plus fenced TOML block, no ANSI styling.
        console.print("# Default TopMark Configuration (TOML)")
        console.print()
        console.print("```toml")
        console.print(toml_text.rstrip("\n"))
        console.print("```")

    elif fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        # Machine-readable formats: emit JSON/NDJSON without human banners
        emit_config_machine(MutableConfig.from_defaults().freeze(), fmt=fmt)

    else:
        # Defensive guard in case OutputFormat gains new members
        raise NotImplementedError(f"Unsupported output format: {fmt!r}")

    # No explicit return needed for Click commands.
