# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/presentation/text/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT renderers for registry-related commands.

This module contains pure TEXT renderers used by CLI commands to produce
human-facing console output. Rendering is pure: functions return a string and
perform no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.presentation.formatters.filetypes import filetype_policy_to_display_pairs
from topmark.presentation.shared.registry import FileTypePolicyHumanItem
from topmark.presentation.shared.registry import ProcessorFileTypeHumanItem
from topmark.presentation.shared.registry import UnboundFileTypeHumanItem

if TYPE_CHECKING:
    from topmark.presentation.shared.registry import FileTypeHumanItem
    from topmark.presentation.shared.registry import FileTypesHumanReport
    from topmark.presentation.shared.registry import ProcessorsHumanReport


def render_filetype_policy_text(
    policy: FileTypePolicyHumanItem,
    styled: bool,
) -> str:
    """Render a file type header policy for TEXT output."""
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=styled)

    rendered_items: list[str] = []
    for key, value in filetype_policy_to_display_pairs(policy):
        styled_key: str = emphasis_styler(
            key,
        )
        rendered_items.append(f"{styled_key}={value}")

    return ", ".join(rendered_items)


def render_filetypes_text(
    report: FileTypesHumanReport,
) -> str:
    """Render TEXT output for `topmark registry filetypes`.

    Args:
        report: Precomputed Click-free report model.

    Returns:
        Rendered TEXT output.
    """
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    muted_styler: TextStyler = style_for_role(StyleRole.MUTED, styled=report.styled)
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=report.styled)

    items: tuple[FileTypeHumanItem, ...] = report.items
    vlevel: int = report.verbosity_level

    lines: list[str] = []
    if vlevel > 0:
        heading: str = emphasis_styler(
            "Supported file types (canonical identities):",
        )
        lines.append(heading)
        lines.append("")

    total: int = len(items)
    num_width: int = len(str(total)) if total > 0 else 1
    k_len: int = max(1, max((len(it.qualified_key) for it in items), default=1))

    for idx, it in enumerate(items, start=1):
        descr: str = muted_styler(
            it.description,
        )
        if report.show_details:
            lines.append(f"{idx:>{num_width}}. {it.qualified_key} — {descr}")
            lines.append(f"      local key       : {it.local_key}")
            lines.append(f"      namespace       : {it.namespace}")
            lines.append(f"      bound           : {'yes' if it.bound else 'no'}")
            if it.extensions:
                lines.append(f"      extensions      : {', '.join(it.extensions)}")
            if it.filenames:
                lines.append(f"      filenames       : {', '.join(it.filenames)}")
            if it.patterns:
                lines.append(f"      patterns        : {', '.join(it.patterns)}")
            lines.append(f"      skip processing : {'yes' if it.skip_processing else 'no'}")
            lines.append(f"      content matcher : {'yes' if it.has_content_matcher else 'no'}")
            lines.append(f"      insert checker  : {'yes' if it.has_insert_checker else 'no'}")
            policy_str: str = render_filetype_policy_text(
                it.policy,
                styled=report.styled,
            )
            lines.append(f"      header policy   : {policy_str}")
        else:
            lines.append(f"{idx:>{num_width}}. {it.qualified_key:<{k_len}} {descr}")

    return "\n".join(lines)


def render_processors_text(
    report: ProcessorsHumanReport,
) -> str:
    """Render TEXT output for `topmark processors`.

    Args:
        report: Precomputed Click-free report model.

    Returns:
        Rendered TEXT output.
    """
    vlevel: int = report.verbosity_level
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=report.styled)
    dim_styler: TextStyler = style_for_role(StyleRole.DIFF_LINE_NO, styled=report.styled)
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=report.styled)

    parts: list[str] = []

    if vlevel > 0:
        parts.append(
            heading_styler(
                "\nSupported Header Processors (with qualified file type identifiers):\n",
            )
        )

    total_proc: int = len(report.processors)
    num_proc_width: int = len(str(total_proc)) if total_proc > 0 else 1

    # Width for filetype numbering in detailed mode
    num_ft_width: int = 1
    if report.show_details:
        max_ft_per_proc: int = max(
            (
                sum(1 for ft in p.filetypes if isinstance(ft, ProcessorFileTypeHumanItem))
                for p in report.processors
            ),
            default=1,
        )
        num_ft_width = len(str(max_ft_per_proc))

    for proc_idx, proc in enumerate(report.processors, start=1):
        module: str = dim_styler(
            "(" + proc.module + ")",
        )

        class_name: str = emphasis_styler(
            proc.class_name,
        )
        if report.show_details:
            parts.append(f"{proc_idx:>{num_proc_width}}. {proc.class_name} {module}")
            for ft_idx, ft in enumerate(proc.filetypes, start=1):
                if not isinstance(ft, ProcessorFileTypeHumanItem):
                    continue
                descr: str = dim_styler(
                    ft.description,
                )
                parts.append(f"    {ft_idx:>{num_ft_width}}. {ft.name} - {descr}")
        else:
            ft_names: list[str] = [ft for ft in proc.filetypes if isinstance(ft, str)]
            proc_ft_count: int = len(ft_names)
            parts.append(
                f"{proc_idx:>{num_proc_width}}. {class_name} {module} (total: {proc_ft_count})"
            )
            parts.append(f"    - {', '.join(ft_names)}")

        if vlevel > 0:
            parts.append("")

    if report.unbound_filetypes:
        hdr_no_processor: str = emphasis_styler(
            "File types without a registered processor (qualified identifiers):",
        )
        if report.show_details:
            parts.append(hdr_no_processor)
            for uft_idx, uft in enumerate(report.unbound_filetypes, start=1):
                if not isinstance(uft, UnboundFileTypeHumanItem):
                    continue
                unbound_ft_descr: str = dim_styler(
                    uft.description,
                )
                parts.append(f"    {uft_idx:>{num_ft_width}}. {uft.name} - {unbound_ft_descr}")
        else:
            names: list[str] = [uft for uft in report.unbound_filetypes if isinstance(uft, str)]
            unreg_ft_count: int = len(names)
            parts.append(f"{hdr_no_processor} (total: {unreg_ft_count})")
            parts.append(f"    - {', '.join(names)}")

    return "\n".join(parts)
