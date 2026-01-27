# topmark:header:start
#
#   project      : TopMark
#   file         : filetypes.py
#   file_relpath : src/topmark/cli/commands/filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark `filetypes` command.

Lists all file types supported by TopMark along with their identifiers and
descriptions. Useful for discovering available file type filters when
configuring headers.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import click

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cmd_common import get_effective_verbosity
from topmark.cli.keys import CliCmd, CliOpt
from topmark.cli_shared.utils import OutputFormat, format_callable_pretty, render_markdown_table
from topmark.constants import TOPMARK_VERSION
from topmark.core.keys import ArgKey
from topmark.filetypes.base import FileType
from topmark.registry import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.filetypes.base import FileType


def _policy_name(obj: object | None) -> str:
    """Get the name of a policy object.

    Args:
        obj (object | None): The policy object.

    Returns:
        str: The name of the policy, or the class name if no name attribute exists.
    """
    if obj is None:
        return ""
    name: str | None = getattr(obj, "name", None)
    if name:
        return str(name)
    return obj.__class__.__name__


@click.command(
    name=CliCmd.FILETYPES,
    help="List all supported file types.",
    epilog="""
Lists all file types currently supported by TopMark, along with a brief description of each.
Use this command to see which file types can be processed and referenced in configuration.
""",
)
@click.option(
    CliOpt.OUTPUT_FORMAT,
    ArgKey.OUTPUT_FORMAT,
    type=EnumChoiceParam(OutputFormat),
    default=None,
    help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
)
@click.option(
    CliOpt.SHOW_DETAILS,
    ArgKey.SHOW_DETAILS,
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
    """
    ctx: click.Context = click.get_current_context()
    ctx.ensure_object(dict)
    console: ConsoleLike = ctx.obj["console"]

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    fmt: OutputFormat = output_format or OutputFormat.DEFAULT

    # Determine effective program-output verbosity for gating extra details
    vlevel: int = get_effective_verbosity(ctx)

    def _serialize_details(ft: FileType) -> dict[str, Any]:
        """Serialize detailed information about a file type."""
        policy_name: str = _policy_name(ft.header_policy)
        return {
            "name": ft.name,
            "description": ft.description,
            "extensions": list(ft.extensions or []),
            "filenames": list(ft.filenames or []),
            "patterns": list(ft.patterns or []),
            "skip_processing": bool(ft.skip_processing),
            "has_content_matcher": ft.content_matcher is not None,
            "has_insert_checker": ft.pre_insert_checker is not None,
            "header_policy": policy_name,
        }

    if fmt in (OutputFormat.JSON, OutputFormat.NDJSON):
        import json

        if fmt == OutputFormat.JSON:
            payload = (
                [_serialize_details(v) for _k, v in sorted(ft_registry.items())]
                if show_details
                else [
                    {"name": k, "description": v.description}
                    for k, v in sorted(ft_registry.items())
                ]
            )
            console.print(json.dumps(payload, indent=2))
        else:  # NDJSON
            for k, v in sorted(ft_registry.items()):
                obj = (
                    _serialize_details(v)
                    if show_details
                    else {"name": k, "description": v.description}
                )
                console.print(json.dumps(obj))
        return

    if fmt == OutputFormat.MARKDOWN:
        console.print(f"""
# Supported File Types

TopMark version **{TOPMARK_VERSION}** supports the following file types:

""")
        if show_details:
            console.print("""
**Legend**

- **Identifier**: File type key used in configuration.
- **Extensions/Filenames/Patterns**: How files are matched on disk.
- **Skip Processing**: If **yes**, the file type is recognized but never modified by TopMark.
- **Content Matcher**: A content‑based detector (in addition to path matching) that refines
  detection (e.g., JSON vs JSONC).
- **Insert Checker**: A pre‑insert capability check that decides if a TopMark header **may** be
  added for the concrete file content (e.g., skip prolog‑only XML).
- **Header Policy**: Formatting/spacing policy applied by the header processor for this type.
            """)
        else:
            console.print("""
_This list shows the file type identifiers and a short description. Use `--long` to see
matching rules and policy details._
            """)
        if show_details:
            headers: list[str] = [
                "Identifier",
                "Extensions",
                "Filenames",
                "Patterns",
                "Skip Processing",
                "Content Matcher",
                "Insert Checker",
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
            for k, v in sorted(ft_registry.items()):
                exts: str = ", ".join(v.extensions) if v.extensions else ""
                names: str = ", ".join(v.filenames) if v.filenames else ""
                pats: str = ", ".join(v.patterns) if v.patterns else ""
                skip_processing: str = "**yes**" if v.skip_processing else "no"
                has_matcher: str = "**yes**" if (v.content_matcher is not None) else "no"
                has_insert_checker: str = "**yes**" if (v.pre_insert_checker is not None) else "no"
                policy: str = _policy_name(v.header_policy)

                row: list[str] = [
                    f"`{k}`",
                    exts,
                    names,
                    f"`{pats}`" if pats else "",
                    skip_processing,
                    has_matcher,
                    has_insert_checker,
                    policy,
                    v.description,
                ]
                rows.append(row)

            table: str = render_markdown_table(
                headers, rows, align={1: "right", 2: "right", 3: "right"}
            )
            console.print(table)

            console.print()
        else:
            # Simpler table logic with dynamic widths
            headers = ["File Type", "Description"]
            rows = []
            max_widths = defaultdict(int)

            for i, header in enumerate(headers):
                max_widths[i] = len(header)

            for k, v in sorted(ft_registry.items()):
                row = [f"`{k}`", v.description]
                rows.append(row)
                for i, col_data in enumerate(row):
                    max_widths[i] = max(max_widths[i], len(str(col_data)))

            header_str: str = " | ".join(
                f"{headers[i]:<{max_widths[i]}}" for i in range(len(headers))
            )
            console.print(f"| {header_str} |")

            separator_str: str = " | ".join(f"{'-' * max_widths[i]}" for i in range(len(headers)))
            # Add spaces around the separator string for correct alignment
            console.print(f"| {separator_str} |")

            for row in rows:
                row_str: str = " | ".join(f"{row[i]:<{max_widths[i]}}" for i in range(len(row)))
                console.print(f"| {row_str} |")

            console.print()
        # Footer for documentation friendliness
        console.print("\n---\n")
        console.print(f"_Generated with TopMark v{TOPMARK_VERSION}_\n")
        return

    else:  # OutputFormat.DEFAULT (default human output)
        # Banner
        if vlevel > 0:
            console.print(console.styled("Supported file types:\n", bold=True, underline=True))

        total: int = len(ft_registry)
        num_width: int = len(str(total))
        k_len: int = max(1, max(len(k) for k in ft_registry))
        for idx, (k, v) in enumerate(sorted(ft_registry.items()), start=1):
            if show_details:
                exts = ", ".join(v.extensions) if v.extensions else ""
                names = ", ".join(v.filenames) if v.filenames else ""
                pats = ", ".join(v.patterns) if v.patterns else ""
                skip: bool = v.skip_processing
                matcher: bool = v.content_matcher is not None
                policy = _policy_name(v.header_policy)
                console.print(
                    f"{idx:>{num_width}}. {k} {console.styled('— ' + v.description, dim=True)}"
                )
                if exts:
                    console.print(f"      extensions     : {exts}")
                if names:
                    console.print(f"      filenames      : {names}")
                if pats:
                    console.print(f"      patterns       : {pats}")
                if skip:
                    console.print("      skip processing: yes")
                if matcher:
                    content_matcher_name: str = console.styled(
                        format_callable_pretty(v.content_matcher), dim=True
                    )
                    console.print(f"      content matcher: yes {content_matcher_name}")

                if v.pre_insert_checker is not None:
                    insert_checker_name: str = console.styled(
                        format_callable_pretty(v.pre_insert_checker), dim=True
                    )
                    console.print(f"      insert checker : yes {insert_checker_name}")

                if policy:
                    console.print(f"      header_policy  : {policy}")
            else:
                if vlevel > 0:
                    descr: str = console.styled(v.description, dim=True)
                    console.print(f"{idx:>{num_width}}. {k:<{k_len}} {descr}")
                else:
                    console.print(f"{idx:>{num_width}}. {k:<{k_len}}")

    # No explicit return needed for Click commands.
