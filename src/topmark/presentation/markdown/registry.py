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

from typing import TYPE_CHECKING

from topmark.constants import TOPMARK_VERSION
from topmark.presentation.formatters.filetypes import filetype_policy_to_display_pairs
from topmark.presentation.markdown.utils import render_markdown_table
from topmark.presentation.markdown.version import render_version_footer_markdown

if TYPE_CHECKING:
    from topmark.presentation.shared.registry import BindingsHumanReport
    from topmark.presentation.shared.registry import FileTypeHumanItem
    from topmark.presentation.shared.registry import FileTypePolicyHumanItem
    from topmark.presentation.shared.registry import FileTypesHumanReport
    from topmark.presentation.shared.registry import ProcessorsHumanReport


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

    lines.append(render_version_footer_markdown())

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
        f"TopMark version **{TOPMARK_VERSION}** supports "
        "the following registered header processors "
        f"(shown as canonical qualified identifiers):\n"
    )

    if report.show_details:
        lines.append("## Legend\n")
        lines.append("- **Qualified Key**: Canonical processor identifier used in machine output.")
        lines.append("- **Local Key / Namespace**: Canonical identity components.")
        lines.append(
            "- **Bound**: Whether the processor currently participates in "
            "at least one effective binding."
        )
        lines.append(
            "- **Line / Block Prefix/Suffix**: Comment delimiters emitted by this processor.\n"
        )

        headers = [
            "Qualified Key",
            "Local Key",
            "Namespace",
            "Bound",
            "Line Indent",
            "Line Prefix",
            "Line Suffix",
            "Block Prefix",
            "Block Suffix",
            "Description",
        ]
        rows: list[list[str]] = []
        for proc in report.processors:
            rows.append(
                [
                    f"`{proc.qualified_key}`",
                    f"`{proc.local_key}`",
                    f"`{proc.namespace}`",
                    "**yes**" if proc.bound else "no",
                    proc.line_indent,
                    proc.line_prefix,
                    proc.line_suffix,
                    proc.block_prefix,
                    proc.block_suffix,
                    proc.description,
                ]
            )
        lines.append(render_markdown_table(headers, rows))
    else:
        lines.append(
            "_This table lists canonical header processor identifiers and a short description. "
            "Use `--long` for identity and delimiter details._\n"
        )
        headers = ["Qualified Key", "Description"]
        rows = [[f"`{proc.qualified_key}`", proc.description] for proc in report.processors]
        lines.append(render_markdown_table(headers, rows))

    lines.append(render_version_footer_markdown())

    return "\n".join(lines)


def render_bindings_markdown(report: BindingsHumanReport) -> str:
    """Render the `bindings` registry report as Markdown.

    Args:
        report: Prepared Click-free report model produced by
            `build_bindings_human_report`.

    Returns:
        A Markdown document suitable for printing to stdout.
    """
    lines: list[str] = []
    lines.append("# Effective File Type Bindings\n")
    lines.append(
        f"TopMark version **{TOPMARK_VERSION}** currently resolves the following effective "
        f"file-type-to-processor bindings:\n"
    )

    if report.show_details:
        headers = [
            "File Type",
            "Processor",
            "File Type Local Key",
            "File Type Namespace",
            "Processor Local Key",
            "Processor Namespace",
            "File Type Description",
            "Processor Description",
        ]
        rows: list[list[str]] = []
        for binding in report.bindings:
            rows.append(
                [
                    f"`{binding.file_type_key}`",
                    f"`{binding.processor_key}`",
                    f"`{binding.file_type_local_key}`",
                    f"`{binding.file_type_namespace}`",
                    f"`{binding.processor_local_key}`",
                    f"`{binding.processor_namespace}`",
                    binding.file_type_description,
                    binding.processor_description,
                ]
            )
        lines.append(render_markdown_table(headers, rows))
    else:
        headers = ["File Type", "Processor"]
        rows = [
            [f"`{binding.file_type_key}`", f"`{binding.processor_key}`"]
            for binding in report.bindings
        ]
        lines.append(render_markdown_table(headers, rows))

    if report.unbound_filetypes:
        lines.append("\n## Unbound File Types\n")
        headers = ["Qualified Key", "Description"]
        rows = [[f"`{item.name}`", item.description] for item in report.unbound_filetypes]
        lines.append(render_markdown_table(headers, rows))

    if report.unused_processors:
        lines.append("\n## Unused Processors\n")
        headers = ["Qualified Key", "Description"]
        rows = [[f"`{item.qualified_key}`", item.description] for item in report.unused_processors]
        lines.append(render_markdown_table(headers, rows))

    lines.append(render_version_footer_markdown())

    return "\n".join(lines)
