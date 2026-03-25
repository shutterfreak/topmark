# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/presentation/markdown/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown renderers for registry-related commands.

This module contains Click-free Markdown renderers used by CLI commands to produce
documentation-friendly output. Rendering is pure: functions return a string and perform no I/O.

Notes:
    These renderers use shared Click-free "human report" preparers to ensure TEXT and MARKDOWN
    outputs remain equivalent by construction.

See Also:
- [`topmark.presentation.shared.registry`][topmark.presentation.shared.registry]
- [`topmark.core.machine`][topmark.core.machine]: canonical machine-output primitives and contracts
"""

from __future__ import annotations

from topmark.constants import TOPMARK_VERSION
from topmark.presentation.formatters.filetypes import filetype_policy_to_display_pairs
from topmark.presentation.markdown.utils import render_markdown_table
from topmark.presentation.shared.registry import FileTypeHumanItem
from topmark.presentation.shared.registry import FileTypePolicyHumanItem
from topmark.presentation.shared.registry import FileTypesHumanReport
from topmark.presentation.shared.registry import ProcessorFileTypeHumanItem
from topmark.presentation.shared.registry import ProcessorsHumanReport
from topmark.presentation.shared.registry import UnboundFileTypeHumanItem


def render_filetype_policy_markdown(policy: FileTypePolicyHumanItem) -> str:
    """Render a file type header policy for MARKDOWN output."""
    return ", ".join(
        f"**{key}**={value}" for key, value in filetype_policy_to_display_pairs(policy)
    )


def render_filetypes_markdown(report: FileTypesHumanReport) -> str:
    """Render the `filetypes` registry report as Markdown.

    Args:
        report: Prepared Click-free report model produced by
            `build_filetypes_human_report`.

    Returns:
        A Markdown document suitable for printing to stdout.
    """
    items: tuple[FileTypeHumanItem, ...] = report.items

    lines: list[str] = []
    lines.append("# Supported File Types\n")
    lines.append(
        f"TopMark version **{TOPMARK_VERSION}** supports the following file types "
        f"(shown as canonical qualified identifiers):\n"
    )

    if report.show_details:
        lines.append("## Legend\n")
        lines.append(
            "- **Qualified Key**: Canonical file type identifier used in configuration "
            "and machine output."
        )
        lines.append("- **Local Key / Namespace**: Canonical identity components.")
        lines.append(
            "- **Bound**: Whether the file type currently has an effective processor binding."
        )
        lines.append("- **Extensions/Filenames/Patterns**: How files are matched on disk.")
        lines.append(
            "- **Skip Processing**: "
            "If **yes**, the file type is recognized but never modified by TopMark."
        )
        lines.append("- **Content Matcher**: Whether a content-based matcher is configured.")
        lines.append("- **Insert Checker**: Whether a pre-insert checker is configured.")
        lines.append("- **Header Policy**: Formatting/spacing policy applied to this file type.\n")

        headers = [
            "Qualified Key",
            "Local Key",
            "Namespace",
            "Bound",
            "Extensions",
            "Filenames",
            "Patterns",
            "Skip Processing",
            "Content Matcher",
            "Insert Checker",
            "Header Policy",
            "Description",
        ]
        rows: list[list[str]] = []
        for it in items:
            policy_str: str = render_filetype_policy_markdown(it.policy)

            rows.append(
                [
                    f"`{it.qualified_key}`",
                    f"`{it.local_key}`",
                    f"`{it.namespace}`",
                    "**yes**" if it.bound else "no",
                    ", ".join(it.extensions),
                    ", ".join(it.filenames),
                    ", ".join(it.patterns),
                    "**yes**" if it.skip_processing else "no",
                    "**yes**" if it.has_content_matcher else "no",
                    "**yes**" if it.has_insert_checker else "no",
                    policy_str,
                    it.description,
                ]
            )
        lines.append(render_markdown_table(headers, rows))
    else:
        lines.append(
            "_This list shows the qualified file type identifiers and a short description. "
            "Use `--long` for details._\n"
        )
        headers: list[str] = ["Qualified Key", "Description"]
        rows = [[f"`{it.qualified_key}`", it.description] for it in items]
        lines.append(render_markdown_table(headers, rows))

    lines.append("\n---\n")
    lines.append(f"_Generated with TopMark v{TOPMARK_VERSION}_\n")
    return "\n".join(lines)


def render_processors_markdown(report: ProcessorsHumanReport) -> str:
    """Render the `processors` registry report as Markdown.

    Args:
        report: Prepared Click-free report model produced by
            `build_processors_human_report`.

    Returns:
        A Markdown document suitable for printing to stdout.
    """
    lines: list[str] = []
    lines.append("# Supported Header Processors\n")
    lines.append(
        f"TopMark version **{TOPMARK_VERSION}** supports the following header processors "
        f"and bound qualified file type identifiers:\n"
    )

    if report.show_details:
        lines.append("## Legend\n")
        lines.append(
            "- This section groups qualified file type identifiers by the "
            "**header processor** class handling them."
        )
        lines.append(
            "- See `topmark filetypes --output-format=markdown --long` for per-type matching rules "
            "and policy details.\n"
        )
        for proc in report.processors:
            lines.append(f"\n## **{proc.class_name}** _({proc.module})_\n")
            lines.append("File types handled by this processor:\n")
            headers: list[str] = ["File Types", "Description"]
            rows: list[list[str]] = []
            for ft in proc.filetypes:
                if isinstance(ft, ProcessorFileTypeHumanItem):
                    rows.append([f"`{ft.name}`", ft.description])
            lines.append(render_markdown_table(headers, rows))
    else:
        lines.append(
            "_This table lists header processors and the qualified file type identifiers "
            "they handle. "
            "Use `--long` to expand  per-processor file type listings into separate tables._\n"
        )
        headers = ["Processor", "Module", "File Types"]
        rows: list[list[str]] = []
        for proc in report.processors:
            ft_names: list[str] = [ft for ft in proc.filetypes if isinstance(ft, str)]
            rows.append(
                [
                    f"`{proc.class_name}`",
                    f"`{proc.module}`",
                    ", ".join(f"`{n}`" for n in ft_names),
                ]
            )
        lines.append(render_markdown_table(headers, rows))

    if report.unbound_filetypes:
        lines.append("\n## File types without a registered processor\n")
        lines.append(
            "These qualified file type identifiers are recognized by TopMark but "
            "currently have no header processor bound. They will be listed, but not processed.\n"
        )
        if report.show_details:
            headers = ["File Types", "Description"]
            rows: list[list[str]] = []
            for uft in report.unbound_filetypes:
                if isinstance(uft, UnboundFileTypeHumanItem):
                    rows.append([f"`{uft.name}`", uft.description])
            lines.append(render_markdown_table(headers, rows))
        else:
            for uft in report.unbound_filetypes:
                if isinstance(uft, str):
                    lines.append(f"  - `{uft}`")

    lines.append("\n---\n")
    lines.append(f"_Generated with TopMark v{TOPMARK_VERSION}_\n")

    return "\n".join(lines)
