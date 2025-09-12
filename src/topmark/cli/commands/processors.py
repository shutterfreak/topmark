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
from topmark.cli_shared.utils import OutputFormat, render_markdown_table
from topmark.constants import TOPMARK_VERSION
from topmark.filetypes.instances import get_file_type_registry
from topmark.filetypes.registry import get_header_processor_registry

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


@click.command(
    name="processors",
    help="List registered header processors.",
    epilog="""
Lists all header processors currently registered in TopMark, along with the file types they handle.
Use this command to see which processors are available and which file types they support.""",
)
@click.option(
    "--format",
    "output_format",
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@click.option(
    "--long",
    "show_details",
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
        show_details (bool): If True, shows extended information about each processor,
            including associated file types and their descriptions.
        output_format (OutputFormat | None): Output format to use
            (``default``, ``json``, ``ndjson``, or ``markdown``).
            If ``None``, uses the default human-readable format.
    """
    ctx = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    file_types = get_file_type_registry()
    header_processors = get_header_processor_registry()
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # Determine effective program-output verbosity for gating extra details
    vlevel = get_effective_verbosity(ctx)

    # Invert mapping: proc class -> [filetype names]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name, proc in header_processors.items():
        key = (proc.__class__.__module__, proc.__class__.__name__)
        groups[key].append(name)

    # Find unbound file types
    unbound = sorted([name for name in file_types.keys() if name not in header_processors])

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
                {"name": n, "description": file_types[n].description} for n in sorted(names)
            ]
        payload_data["processors"].append(processor_entry)

    for name in unbound:
        if show_details:
            payload_data["unbound_filetypes"].append(
                {"name": name, "description": file_types[name].description}
            )
        else:
            payload_data["unbound_filetypes"].append(name)

    if fmt == OutputFormat.JSON:
        import json

        console.print(json.dumps(payload_data, indent=2))
        return

    if fmt == OutputFormat.NDJSON:
        import json

        # Output processors
        for proc in payload_data["processors"]:
            console.print(json.dumps({"processor": proc}))
        # Output unbound file types
        for unbound_ft in payload_data["unbound_filetypes"]:
            console.print(json.dumps({"unbound_filetype": unbound_ft}))
        return

    if fmt == OutputFormat.MARKDOWN:
        console.print(f"""
# Supported Header Processors

TopMark version **{TOPMARK_VERSION}** supports the following header processors:

""")
        rows: list[list[str]]
        if show_details:
            for proc in payload_data["processors"]:
                headers = ["File Types", "Description"]
                rows = []
                console.print(f"\n## **{proc['class']}** _({proc['module']})_\n")
                # console.print("| File Types | Description |")
                # console.print("|---|---|")
                for file_types in proc["filetypes"]:
                    rows.append([f"`{file_types['name']}`", file_types["description"]])
                    # console.print(f"| `{ft['name']}` | {ft['description']} |")
                table = render_markdown_table(headers, rows)
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
            headers = ["File Types", "Description"]
            rows = []
            for unbound_ft in payload_data["unbound_filetypes"]:
                if show_details:
                    rows.append([f"`{unbound_ft['name']}`", f"`{unbound_ft['description']}`"])
                else:
                    console.print(f"  - `{unbound_ft}`")
        console.print()
        return

    else:  # OutputFormat.DEFAULT (default human output)
        # Banner
        if vlevel > 0:
            console.print(
                console.styled("\nSupported Header Processors:\n", bold=True, underline=True)
            )

        total_proc = len(payload_data["processors"])
        num_proc_width = len(str(total_proc))
        proc_idx: int = 0

        total_ft = len(file_types)
        num_ft_width = len(str(total_ft))

        for proc in payload_data["processors"]:
            proc_idx += 1

            module = console.styled("(" + proc["module"] + ")", dim=True)
            if show_details:
                console.print(
                    f"{proc_idx:>{num_proc_width}}. {console.styled(proc['class'], bold=True)} "
                    + module
                )
                ft_idx = 0
                for file_types in proc["filetypes"]:
                    ft_idx += 1
                    descr = console.styled(file_types["description"], dim=True)

                    console.print(f"    {ft_idx:>{num_ft_width}}. {file_types['name']} - {descr}")
            else:
                proc_ft_count = len(proc["filetypes"])
                console.print(
                    f"{proc_idx:>{num_proc_width}}. {console.styled(proc['class'], bold=True)} "
                    + module
                    + f" (total: {proc_ft_count})"
                )
                console.print(f"    - {', '.join(proc['filetypes'])}")

            if vlevel > 0:
                console.print()

        if payload_data["unbound_filetypes"]:
            hdr_no_processor = console.styled(
                "File types without a registered processor:",
                bold=True,
            )
            if show_details:
                console.print(hdr_no_processor)
                ft_idx = 0
                for unbound_ft in payload_data["unbound_filetypes"]:
                    ft_idx += 1
                    console.print(
                        f"    {ft_idx:>{num_ft_width}}. {unbound_ft['name']} - "
                        f"{console.styled(unbound_ft['description'], dim=True)}"
                    )
            else:
                unreg_ft_count = len(payload_data["unbound_filetypes"])
                console.print(f"{hdr_no_processor} (total: {unreg_ft_count})")
                console.print(f"    - {', '.join(payload_data['unbound_filetypes'])}")

    # No explicit return needed for Click commands.
