# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/cli/emitters/text/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT (human) emitters and models for registry-related commands.

This module contains:
- Click/console-dependent emitters that print those models with ANSI styling.

Notes:
    The TEXT format is currently considered a CLI concern because it relies on
    console styling. When a fully Click-free rendering layer is introduced for
    TEXT output, the report builders can move to
    [`topmark.cli_shared.emitters`][topmark.cli_shared.emitters].

See Also:
- [`topmark.registry`][topmark.registry]: file type registry and processor binding
- [`topmark.core.machine`][topmark.core.machine]: canonical machine-output documentation anchor
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli_shared.emitters.shared.registry import (
    ProcessorFileTypeHumanItem,
    UnboundFileTypeHumanItem,
)

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.cli_shared.emitters.shared.registry import (
        FileTypeHumanItem,
        FileTypesHumanReport,
        ProcessorsHumanReport,
    )


def emit_filetypes_text(*, console: ConsoleLike, report: FileTypesHumanReport) -> None:
    """Emit TEXT output for `topmark filetypes`.

    Args:
        console: Console abstraction (Click-owned).
        report: Precomputed Click-free report model.
    """
    items: tuple[FileTypeHumanItem, ...] = report.items
    vlevel: int = report.verbosity_level

    if vlevel > 0:
        console.print(console.styled("Supported file types:\n", bold=True, underline=True))

    total: int = len(items)
    num_width: int = len(str(total)) if total > 0 else 1
    k_len: int = max(1, max((len(it.name) for it in items), default=1))

    for idx, it in enumerate(items, start=1):
        if report.show_details:
            console.print(
                f"{idx:>{num_width}}. {it.name} {console.styled('— ' + it.description, dim=True)}"
            )
            if it.extensions:
                console.print(f"      extensions     : {', '.join(it.extensions)}")
            if it.filenames:
                console.print(f"      filenames      : {', '.join(it.filenames)}")
            if it.patterns:
                console.print(f"      patterns       : {', '.join(it.patterns)}")
            if it.skip_processing:
                console.print("      skip processing: yes")
            if it.content_matcher_name is not None:
                console.print(
                    f"      content matcher: "
                    f"yes {console.styled(it.content_matcher_name, dim=True)}"
                )
            if it.insert_checker_name is not None:
                console.print(
                    f"      insert checker : yes {console.styled(it.insert_checker_name, dim=True)}"
                )
            if it.header_policy_name:
                console.print(f"      header_policy  : {it.header_policy_name}")
        else:
            descr: str = console.styled(it.description, dim=True)
            console.print(f"{idx:>{num_width}}. {it.name:<{k_len}} {descr}")


def emit_processors_text(*, console: ConsoleLike, report: ProcessorsHumanReport) -> None:
    """Emit TEXT output for `topmark processors`.

    Args:
        console: Console abstraction (Click-owned).
        report: Precomputed Click-free report model.
    """
    vlevel: int = report.verbosity_level

    if vlevel > 0:
        console.print(console.styled("\nSupported Header Processors:\n", bold=True, underline=True))

    total_proc: int = len(report.processors)
    num_proc_width: int = len(str(total_proc)) if total_proc > 0 else 1

    # Width for filetype numbering in detailed mode
    num_ft_width: int = 1
    if report.show_details:
        max_ft_per_proc = max(
            (
                sum(1 for ft in p.filetypes if isinstance(ft, ProcessorFileTypeHumanItem))
                for p in report.processors
            ),
            default=1,
        )
        num_ft_width = len(str(max_ft_per_proc))

    for proc_idx, proc in enumerate(report.processors, start=1):
        module: str = console.styled("(" + proc.module + ")", dim=True)

        if report.show_details:
            console.print(
                f"{proc_idx:>{num_proc_width}}. {console.styled(proc.class_name, bold=True)} "
                + module
            )
            for ft_idx, ft in enumerate(proc.filetypes, start=1):
                if not isinstance(ft, ProcessorFileTypeHumanItem):
                    continue
                descr: str = console.styled(ft.description, dim=True)
                console.print(f"    {ft_idx:>{num_ft_width}}. {ft.name} - {descr}")
        else:
            ft_names: list[str] = [ft for ft in proc.filetypes if isinstance(ft, str)]
            proc_ft_count: int = len(ft_names)
            console.print(
                f"{proc_idx:>{num_proc_width}}. {console.styled(proc.class_name, bold=True)} "
                + module
                + f" (total: {proc_ft_count})"
            )
            console.print(f"    - {', '.join(ft_names)}")

        if vlevel > 0:
            console.print()

    if report.unbound_filetypes:
        hdr_no_processor: str = console.styled(
            "File types without a registered processor:",
            bold=True,
        )
        if report.show_details:
            console.print(hdr_no_processor)
            for uft_idx, uft in enumerate(report.unbound_filetypes, start=1):
                if not isinstance(uft, UnboundFileTypeHumanItem):
                    continue
                console.print(
                    f"    {uft_idx:>{num_ft_width}}. {uft.name} - "
                    f"{console.styled(uft.description, dim=True)}"
                )
        else:
            names: list[str] = [uft for uft in report.unbound_filetypes if isinstance(uft, str)]
            unreg_ft_count: int = len(names)
            console.print(f"{hdr_no_processor} (total: {unreg_ft_count})")
            console.print(f"    - {', '.join(names)}")
