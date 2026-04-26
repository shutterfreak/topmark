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

TEXT output may use `verbosity_level` for console-oriented progressive disclosure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole
from topmark.presentation.formatters.filetypes import filetype_policy_to_display_pairs

if TYPE_CHECKING:
    from topmark.presentation.shared.registry import BindingsHumanReport
    from topmark.presentation.shared.registry import FileTypeHumanItem
    from topmark.presentation.shared.registry import FileTypePolicyHumanItem
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
    """Render TEXT output for `topmark registry processors`.

    Args:
        report: Precomputed Click-free report model.

    Returns:
        Rendered TEXT output.
    """
    vlevel: int = report.verbosity_level
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=report.styled)
    dim_styler: TextStyler = style_for_role(StyleRole.DIFF_LINE_NO, styled=report.styled)

    parts: list[str] = []

    if vlevel > 0:
        parts.append(heading_styler("Registered header processors:"))
        parts.append("")

    total_proc: int = len(report.processors)
    num_proc_width: int = len(str(total_proc)) if total_proc > 0 else 1
    k_len: int = max(1, max((len(proc.qualified_key) for proc in report.processors), default=1))

    for proc_idx, proc in enumerate(report.processors, start=1):
        descr: str = dim_styler(proc.description)
        if report.show_details:
            parts.append(f"{proc_idx:>{num_proc_width}}. {proc.qualified_key} — {descr}")
            parts.append(f"      local key       : {proc.local_key}")
            parts.append(f"      namespace       : {proc.namespace}")
            parts.append(f"      bound           : {'yes' if proc.bound else 'no'}")
            parts.append(f"      line indent     : {proc.line_indent}")
            parts.append(f"      line prefix     : {proc.line_prefix}")
            parts.append(f"      line suffix     : {proc.line_suffix}")
            parts.append(f"      block prefix    : {proc.block_prefix}")
            parts.append(f"      block suffix    : {proc.block_suffix}")
        else:
            parts.append(f"{proc_idx:>{num_proc_width}}. {proc.qualified_key:<{k_len}} {descr}")

    return "\n".join(parts)


def render_bindings_text(
    report: BindingsHumanReport,
) -> str:
    """Render TEXT output for `topmark registry bindings`.

    Args:
        report: Precomputed Click-free report model.

    Returns:
        Rendered TEXT output.
    """
    vlevel: int = report.verbosity_level
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=report.styled)
    dim_styler: TextStyler = style_for_role(StyleRole.DIFF_LINE_NO, styled=report.styled)

    parts: list[str] = []

    if vlevel > 0:
        parts.append(heading_styler("Effective file-type-to-processor bindings:"))
        parts.append("")

    total: int = len(report.bindings)
    num_width: int = len(str(total)) if total > 0 else 1

    for idx, binding in enumerate(report.bindings, start=1):
        if report.show_details:
            parts.append(f"{idx:>{num_width}}. {binding.file_type_key} -> {binding.processor_key}")
            parts.append(f"      file type local key : {binding.file_type_local_key}")
            parts.append(f"      file type namespace : {binding.file_type_namespace}")
            parts.append(f"      processor local key : {binding.processor_local_key}")
            parts.append(f"      processor namespace : {binding.processor_namespace}")
            parts.append(f"      file type desc      : {dim_styler(binding.file_type_description)}")
            parts.append(f"      processor desc      : {dim_styler(binding.processor_description)}")
        else:
            parts.append(f"{idx:>{num_width}}. {binding.file_type_key} -> {binding.processor_key}")

    if report.unbound_filetypes:
        parts.append("")
        parts.append(heading_styler("Unbound file types:"))
        for idx, item in enumerate(report.unbound_filetypes, start=1):
            parts.append(f"{idx:>{num_width}}. {item.name} — {dim_styler(item.description)}")

    if report.unused_processors:
        parts.append("")
        parts.append(heading_styler("Unused processors:"))
        for idx, item in enumerate(report.unused_processors, start=1):
            parts.append(
                f"{idx:>{num_width}}. {item.qualified_key} — {dim_styler(item.description)}"
            )

    return "\n".join(parts)
