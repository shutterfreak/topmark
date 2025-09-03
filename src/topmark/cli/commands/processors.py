# topmark:header:start
#
#   file         : processors.py
#   file_relpath : src/topmark/cli/commands/processors.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI command to list registered header processors.

This module defines a command-line interface (CLI) command that lists all header processors
registered in TopMark, along with the file types they handle. It supports various output formats,
including JSON, NDJSON, Markdown, and a default human-readable format.
"""

from collections import defaultdict
from typing import Any

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli_shared.utils import OutputFormat, render_markdown_table
from topmark.constants import TOPMARK_VERSION
from topmark.filetypes.instances import get_file_type_registry
from topmark.filetypes.registry import get_header_processor_registry


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
    ft = get_file_type_registry()
    reg = get_header_processor_registry()
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # Invert mapping: proc class -> [filetype names]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name, proc in reg.items():
        key = (proc.__class__.__module__, proc.__class__.__name__)
        groups[key].append(name)

    # Find unbound file types
    unbound = sorted([name for name in ft.keys() if name not in reg])

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
                {"name": n, "description": ft[n].description} for n in sorted(names)
            ]
        payload_data["processors"].append(processor_entry)

    for name in unbound:
        if show_details:
            payload_data["unbound_filetypes"].append(
                {"name": name, "description": ft[name].description}
            )
        else:
            payload_data["unbound_filetypes"].append(name)

    if fmt == OutputFormat.JSON:
        import json

        click.echo(json.dumps(payload_data, indent=2))
        return

    if fmt == OutputFormat.NDJSON:
        import json

        # Output processors
        for proc in payload_data["processors"]:
            click.echo(json.dumps({"processor": proc}))
        # Output unbound file types
        for unbound_ft in payload_data["unbound_filetypes"]:
            click.echo(json.dumps({"unbound_filetype": unbound_ft}))
        return

    if fmt == OutputFormat.MARKDOWN:
        click.echo(f"""
# Supported Header Processors

TopMark version **{TOPMARK_VERSION}** supports the following header processors:

""")
        rows: list[list[str]]
        if show_details:
            for proc in payload_data["processors"]:
                headers = ["File Types", "Description"]
                rows = []
                click.echo(f"\n## **{proc['class']}** _({proc['module']})_\n")
                # click.echo("| File Types | Description |")
                # click.echo("|---|---|")
                for ft in proc["filetypes"]:
                    rows.append([f"`{ft['name']}`", ft["description"]])
                    # click.echo(f"| `{ft['name']}` | {ft['description']} |")
                table = render_markdown_table(headers, rows)
                click.echo(table)

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
            click.echo(table)

        if payload_data["unbound_filetypes"]:
            click.echo("\n## File types without a registered processor\n")
            headers = ["File Types", "Description"]
            rows = []
            for unbound_ft in payload_data["unbound_filetypes"]:
                if show_details:
                    rows.append([f"`{unbound_ft['name']}`", f"`{unbound_ft['description']}`"])
                else:
                    click.echo(f"  - `{unbound_ft}`")
        click.echo()
        return

    else:  # OutputFormat.DEFAULT
        # default human
        click.secho("\nSupported Header Processors:\n", bold=True, underline=True)
        for proc in payload_data["processors"]:
            click.echo(
                f"  - **{proc['class']}** {click.style('(' + proc['module'] + ')', dim=True)}"
            )
            if show_details:
                for ft in proc["filetypes"]:
                    click.echo(f"      - {ft['name']} - {click.style(ft['description'], dim=True)}")
            else:
                click.echo(f"      - {', '.join(proc['filetypes'])}")

        if payload_data["unbound_filetypes"]:
            click.secho("\nFile types without a registered processor:\n", bold=True)
            if show_details:
                for unbound_ft in payload_data["unbound_filetypes"]:
                    click.echo(
                        f"  - {unbound_ft['name']} - "
                        f"{click.style(unbound_ft['description'], dim=True)}"
                    )
            else:
                click.echo(f"  - {', '.join(payload_data['unbound_filetypes'])}")

        click.echo()
