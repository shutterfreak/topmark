# topmark:header:start
#
#   file         : filetypes.py
#   file_relpath : src/topmark/cli/commands/filetypes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `filetypes` command.

Lists all file types supported by TopMark along with their identifiers and
descriptions. Useful for discovering available file type filters when
configuring headers.
"""

from collections import defaultdict
from typing import Any

import click
from yachalk import chalk

from topmark.cli.cli_types import EnumParam
from topmark.cli_shared.utils import OutputFormat, markdown_table
from topmark.constants import TOPMARK_VERSION
from topmark.filetypes.base import FileType
from topmark.filetypes.instances import get_file_type_registry


@click.command(
    name="filetypes",
    help="List all supported file types.",
    epilog="""
Lists all file types currently supported by TopMark, along with a brief description of each.
Use this command to see which file types can be processed and referenced in configuration.
""",
)
@click.option(
    "--format",
    "output_format",
    type=EnumParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@click.option(
    "--long",
    "show_details",
    is_flag=True,
    help="Show extended information (extensions, filenames, patterns, skip policy, header policy).",
)
def filetypes_command(
    *,
    show_details: bool = False,
    output_format: OutputFormat | None = None,
) -> None:
    """List supported file types.

    Prints all file types supported by TopMark, including their identifiers and descriptions.
    Useful for reference when configuring file type filters.

    Args:
        show_details (bool): If True, shows extended information about each file type,
            including associated extensions, filenames, patterns, skip policy, and header policy.
        output_format (OutputFormat | None): Output format to use
            (``default``, ``json``, or ``ndjson``).
            If ``None``, uses the default human-readable format.

    Returns:
        None. Prints output to stdout.
    """
    file_types = get_file_type_registry()
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    def _serialize_details(ft: FileType) -> dict[str, Any]:
        """Serialize detailed information about a file type."""
        policy = ft.header_policy
        policy_name = getattr(policy, "name", None) or (
            policy.__class__.__name__ if policy else None
        )
        return {
            "name": ft.name,
            "description": ft.description,
            "extensions": list(ft.extensions or []),
            "filenames": list(ft.filenames or []),
            "patterns": list(ft.patterns or []),
            "skip_processing": bool(ft.skip_processing),
            "has_content_matcher": ft.content_matcher is not None,
            "header_policy": policy_name,
        }

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        import json

        if fmt == OutputFormat.JSON:
            payload = (
                [_serialize_details(v) for _k, v in sorted(file_types.items())]
                if show_details
                else [
                    {"name": k, "description": v.description} for k, v in sorted(file_types.items())
                ]
            )
            click.echo(json.dumps(payload, indent=2))
        else:  # NDJSON
            for k, v in sorted(file_types.items()):
                obj = (
                    _serialize_details(v)
                    if show_details
                    else {"name": k, "description": v.description}
                )
                click.echo(json.dumps(obj))
        return

    if fmt == OutputFormat.MARKDOWN:
        click.echo(f"""
# Supported File Types
                   
TopMark version **{TOPMARK_VERSION}** supports the following file types:

""")
        if show_details:
            headers = [
                "Identifier",
                "Extensions",
                "Filenames",
                "Patterns",
                "Skip Processing",
                "Content Matcher",
                "Header Policy",
                "Description",
            ]

            # Collect all rows and find the max width for each column
            rows: list[list[str]] = []
            max_widths: defaultdict[int, int] = defaultdict(int)

            # Calculate max width for headers
            for i, header in enumerate(headers):
                max_widths[i] = len(header)

            # Collect data and calculate max width for each column
            for k, v in sorted(file_types.items()):
                exts = ", ".join(v.extensions) if v.extensions else ""
                names = ", ".join(v.filenames) if v.filenames else ""
                pats = ", ".join(v.patterns) if v.patterns else ""
                skip = "**yes**" if v.skip_processing else "no"
                has_matcher = "**yes**" if (v.content_matcher is not None) else "no"
                policy = getattr(v.header_policy, "name", None) or (
                    v.header_policy.__class__.__name__ if v.header_policy else ""
                )

                row = [
                    f"`{k}`",
                    exts,
                    names,
                    f"`{pats}`" if pats else "",
                    skip,
                    has_matcher,
                    policy,
                    v.description,
                ]
                rows.append(row)

            table = markdown_table(headers, rows, align={1: "right", 2: "right", 3: "right"})
            click.echo(table)

            click.echo()
        else:
            # Simpler table logic with dynamic widths
            headers = ["File Type", "Description"]
            rows = []
            max_widths = defaultdict(int)

            for i, header in enumerate(headers):
                max_widths[i] = len(header)

            for k, v in sorted(file_types.items()):
                row = [f"`{k}`", v.description]
                rows.append(row)
                for i, col_data in enumerate(row):
                    max_widths[i] = max(max_widths[i], len(str(col_data)))

            header_str = " | ".join(f"{headers[i]:<{max_widths[i]}}" for i in range(len(headers)))
            click.echo(f"| {header_str} |")

            separator_str = " | ".join(f"{'-' * max_widths[i]}" for i in range(len(headers)))
            # Add spaces around the separator string for correct alignment
            click.echo(f"| {separator_str} |")

            for row in rows:
                row_str = " | ".join(f"{row[i]:<{max_widths[i]}}" for i in range(len(row)))
                click.echo(f"| {row_str} |")

            click.echo()
        return

    # DEFAULT human
    click.secho("Supported file types:", bold=True, underline=True)
    for k, v in sorted(file_types.items()):
        if show_details:
            exts = ", ".join(v.extensions) if v.extensions else ""
            names = ", ".join(v.filenames) if v.filenames else ""
            pats = ", ".join(v.patterns) if v.patterns else ""
            skip = v.skip_processing
            matcher = v.content_matcher is not None
            policy = getattr(v.header_policy, "name", None) or (
                v.header_policy.__class__.__name__ if v.header_policy else ""
            )
            click.echo(f"  - {k} {chalk.dim('— ' + v.description)}")
            if exts:
                click.echo(f"      extensions     : {exts}")
            if names:
                click.echo(f"      filenames      : {names}")
            if pats:
                click.echo(f"      patterns       : {pats}")
            if skip:
                click.echo("      skip processing: yes")
            if matcher:
                assert v.content_matcher is not None
                click.echo(f"      content matcher: {v.content_matcher.__name__}")
            if policy:
                click.echo(f"      header_policy  : {policy}")
        else:
            click.echo(f"  - {k:<12} {chalk.dim(v.description)}")

    # No explicit return needed for Click commands.
