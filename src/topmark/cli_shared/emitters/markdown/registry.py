# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/registry.py
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
- [`topmark.cli_shared.emitters.shared.registry`][topmark.cli_shared.emitters.shared.registry]
- [`topmark.core.machine`][topmark.core.machine]: canonical machine-output primitives and contracts
"""

from __future__ import annotations

from topmark.cli_shared.emitters.markdown.utils import render_markdown_table
from topmark.cli_shared.emitters.shared.registry import (
    FileTypeHumanItem,
    FileTypesHumanReport,
    ProcessorFileTypeHumanItem,
    ProcessorsHumanReport,
    UnboundFileTypeHumanItem,
    build_filetypes_human_report,
    build_processors_human_report,
)
from topmark.constants import TOPMARK_VERSION


def render_filetypes_markdown(*, report: FileTypesHumanReport) -> str:
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
    lines.append(f"TopMark version **{TOPMARK_VERSION}** supports the following file types:\n")

    if report.show_details:
        lines.append("## Legend\n")
        lines.append("- **Identifier**: File type key used in configuration.")
        lines.append("- **Extensions/Filenames/Patterns**: How files are matched on disk.")
        lines.append(
            "- **Skip Processing**: "
            "If **yes**, the file type is recognized but never modified by TopMark."
        )
        lines.append("- **Content Matcher**: Content-based detector refining detection.")
        lines.append("- **Insert Checker**: Decides if a header may be added for concrete content.")
        lines.append(
            "- **Header Policy**: "
            "Formatting/spacing policy applied by the header processor for this type.\n"
        )

        headers = [
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
        rows: list[list[str]] = []
        for it in items:
            rows.append(
                [
                    f"`{it.name}`",
                    ", ".join(it.extensions),
                    ", ".join(it.filenames),
                    ", ".join(it.patterns),
                    "**yes**" if it.skip_processing else "no",
                    "**yes**" if (it.content_matcher_name is not None) else "no",
                    "**yes**" if (it.insert_checker_name is not None) else "no",
                    it.header_policy_name,
                    it.description,
                ]
            )
        lines.append(render_markdown_table(headers, rows))
    else:
        lines.append(
            "_This list shows the file type identifiers and a short description. "
            "Use `--long` for details._\n"
        )
        headers: list[str] = ["File Type", "Description"]
        rows = [[f"`{it.name}`", it.description] for it in items]
        lines.append(render_markdown_table(headers, rows))

    lines.append("\n---\n")
    lines.append(f"_Generated with TopMark v{TOPMARK_VERSION}_\n")
    return "\n".join(lines)


def build_and_render_filetypes_markdown(*, show_details: bool, verbosity_level: int) -> str:
    """Build and render the filetypes report as Markdown.

    Args:
        show_details: Whether to include extended information.
        verbosity_level: Effective verbosity (kept for symmetry; currently unused by Markdown).

    Returns:
        Rendered Markdown document.
    """
    report: FileTypesHumanReport = build_filetypes_human_report(
        show_details=show_details,
        verbosity_level=verbosity_level,
    )
    return render_filetypes_markdown(report=report)


def render_processors_markdown(*, report: ProcessorsHumanReport) -> str:
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
        f"TopMark version **{TOPMARK_VERSION}** supports the following header processors:\n"
    )

    if report.show_details:
        lines.append("## Legend\n")
        lines.append(
            "- This section groups file types by the **header processor** class handling them."
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
            "_This table lists header processors and the file types they handle. "
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
            "These file types are recognized by TopMark but currently have no "
            "header processor bound. They will be listed, but not processed.\n"
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


def build_and_render_processors_markdown(*, show_details: bool, verbosity_level: int) -> str:
    """Build and render the processors report as Markdown.

    Args:
        show_details: Whether to include extended information.
        verbosity_level: Effective verbosity (kept for symmetry; currently unused by Markdown).

    Returns:
        Rendered Markdown document.
    """
    report: ProcessorsHumanReport = build_processors_human_report(
        show_details=show_details,
        verbosity_level=verbosity_level,
    )
    return render_processors_markdown(report=report)
