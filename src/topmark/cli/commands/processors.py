# topmark:header:start
#
#   project      : TopMark
#   file         : processors.py
#   file_relpath : src/topmark/cli/commands/processors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI command to list registered header processors.

This module defines a command-line interface (CLI) command that lists all header processors
registered in TopMark, along with the file types they handle. It supports various output formats,
including JSON, NDJSON, Markdown, and a default human-readable format.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli.machine_emitters import emit_processors_machine
from topmark.cli.options import underscored_trap_option
from topmark.cli_shared.markdown import render_markdown_table
from topmark.constants import TOPMARK_VERSION
from topmark.core.formats import OutputFormat, is_machine_format
from topmark.core.keys import ArgKey
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.core.machine.schemas import MetaPayload
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


@click.command(
    name=CliCmd.PROCESSORS,
    help="List registered header processors.",
    epilog="""
Lists all header processors currently registered in TopMark, along with the file types they handle.
Use this command to see which processors are available and which file types they support.""",
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
    CliOpt.SHOW_DETAILS,
    ArgKey.SHOW_DETAILS,
    is_flag=True,
    help="Show extended information (file types and their description).",
)
def processors_command(
    *,
    show_details: bool = False,
    output_format: OutputFormat | None = None,
) -> None:
    """List registered header processors.

    Prints all header processors supported by TopMark, including the file types they handle.
    Useful for reference when configuring file type filters.

    Args:
        show_details: If True, shows extended information about each processor,
            including associated file types and their descriptions.
        output_format: Output format to use
            (``default``, ``json``, ``ndjson``, or ``markdown``).
            If ``None``, uses the default human-readable format.
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)

    # Machine metadata
    meta: MetaPayload = ctx.obj[ArgKey.META]

    if output_format and is_machine_format(output_format):
        # Disable color mode for machine formats
        ctx.obj[ArgKey.COLOR_ENABLED] = False

    console: ConsoleLike = ctx.obj[ArgKey.CONSOLE]

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    # Machine formats
    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        emit_processors_machine(
            meta=meta,
            fmt=fmt,
            show_details=show_details,
        )
        return

    # Invert mapping: proc class -> [filetype names]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name, proc in hp_registry.items():
        key: tuple[str, str] = (proc.__class__.__module__, proc.__class__.__name__)
        groups[key].append(name)

    # Find unbound file types
    unbound: list[str] = sorted([name for name in ft_registry if name not in hp_registry])

    # Build a unified payload for all formats
    payload_data: dict[str, Any] = {
        "processors": [],
        "unbound_filetypes": [],
    }
    for (mod, cls), names in sorted(groups.items()):
        processor_entry: dict[str, Any] = {
            "module": mod,
            "class": cls,
            "filetypes": sorted(names),
        }
        if show_details:
            processor_entry["filetypes"] = [
                {"name": n, "description": ft_registry[n].description} for n in sorted(names)
            ]
        payload_data["processors"].append(processor_entry)

    for name in unbound:
        if show_details:
            payload_data["unbound_filetypes"].append(
                {"name": name, "description": ft_registry[name].description}
            )
        else:
            payload_data["unbound_filetypes"].append(name)

    if fmt == OutputFormat.MARKDOWN:
        console.print(f"""
# Supported Header Processors

TopMark version **{TOPMARK_VERSION}** supports the following header processors:

""")
        if show_details:
            console.print("""
## Legend

- This section groups file types by the **header processor** class handling them.
- See `topmark filetypes --output-format=markdown --long` for per‑type matching rules,
  content matchers, insert checkers, and policy details.
""")
        else:
            console.print("""
_This table lists header processors and the file types they handle. Use `--long` to expand
per‑processor file type listings into separate tables._
""")
        rows: list[list[str]]
        if show_details:
            for proc in payload_data["processors"]:
                headers: list[str] = ["File Types", "Description"]
                rows = []
                console.print(f"\n## **{proc['class']}** _({proc['module']})_\n")
                console.print("File types handled by this processor:\n")
                # console.print("| File Types | Description |")
                # console.print("|---|---|")
                ft: dict[str, str]
                for ft in proc["filetypes"]:
                    rows.append([f"`{ft['name']}`", ft["description"]])
                    # console.print(f"| `{ft['name']}` | {ft['description']} |")
                table: str = render_markdown_table(headers, rows)
                console.print(table)

        else:
            headers = ["Processor", "Module", "File Types"]
            rows = []

            for proc in payload_data["processors"]:
                rows.append(
                    [
                        f"`{proc['class']}`",
                        f"`{proc['module']}`",
                        ", ".join(f"`{n}`" for n in proc["filetypes"]),
                    ]
                )
            table = render_markdown_table(headers, rows)
            console.print(table)

        if payload_data["unbound_filetypes"]:
            console.print("\n## File types without a registered processor\n")
            console.print(
                "These file types are recognized by TopMark but currently have "
                "no header processor bound. They will be listed, but not processed.\n"
            )
            headers = ["File Types", "Description"]
            rows = []
            for unbound_ft in payload_data["unbound_filetypes"]:
                if show_details:
                    rows.append([f"`{unbound_ft['name']}`", f"`{unbound_ft['description']}`"])
                else:
                    console.print(f"  - `{unbound_ft}`")
            if show_details:
                table = render_markdown_table(headers, rows)
                console.print(table)
        console.print()
        # Footer for documentation friendliness
        console.print("\n---\n")
        console.print(f"_Generated with TopMark v{TOPMARK_VERSION}_\n")
        return

    else:  # OutputFormat.DEFAULT (default human output)
        # Banner
        if vlevel > 0:
            console.print(
                console.styled("\nSupported Header Processors:\n", bold=True, underline=True)
            )

        total_proc: int = len(payload_data["processors"])
        num_proc_width: int = len(str(total_proc))
        proc_idx: int = 0

        total_ft: int = len(ft_registry)
        num_ft_width: int = len(str(total_ft))

        for proc_idx, proc in enumerate(payload_data["processors"], start=1):
            module: str = console.styled("(" + proc["module"] + ")", dim=True)
            if show_details:
                console.print(
                    f"{proc_idx:>{num_proc_width}}. {console.styled(proc['class'], bold=True)} "
                    + module
                )
                for ft_idx, ft in enumerate(proc["filetypes"], start=1):
                    descr: str = console.styled(ft["description"], dim=True)

                    console.print(f"    {ft_idx:>{num_ft_width}}. {ft['name']} - {descr}")
            else:
                proc_ft_count: int = len(proc["filetypes"])
                console.print(
                    f"{proc_idx:>{num_proc_width}}. {console.styled(proc['class'], bold=True)} "
                    + module
                    + f" (total: {proc_ft_count})"
                )
                console.print(f"    - {', '.join(proc['filetypes'])}")

            if vlevel > 0:
                console.print()

        if payload_data["unbound_filetypes"]:
            hdr_no_processor: str = console.styled(
                "File types without a registered processor:",
                bold=True,
            )
            if show_details:
                console.print(hdr_no_processor)
                for uft_idx, unbound_ft in enumerate(payload_data["unbound_filetypes"], start=1):
                    console.print(
                        f"    {uft_idx:>{num_ft_width}}. {unbound_ft['name']} - "
                        f"{console.styled(unbound_ft['description'], dim=True)}"
                    )
            else:
                unreg_ft_count: int = len(payload_data["unbound_filetypes"])
                console.print(f"{hdr_no_processor} (total: {unreg_ft_count})")
                console.print(f"    - {', '.join(payload_data['unbound_filetypes'])}")

    # No explicit return needed for Click commands.
