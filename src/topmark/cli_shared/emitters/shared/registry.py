# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/cli_shared/emitters/shared/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared Click-free preparers for human-facing registry output.

This module prepares typed, human-facing report models for registry-related CLI commands. The
prepared data is intentionally presentation-agnostic and reused by:

- TEXT output emitters under [`topmark.cli.emitters.text`][topmark.cli.emitters.text]
  (ANSI/console styling), and
- Markdown renderers under
  [`topmark.cli_shared.emitters.markdown`][topmark.cli_shared.emitters.markdown]
  (documentation-friendly output).

Notes:
    This is a "human output" layer. It is distinct from
    [`topmark.registry.machine`][topmark.registry.machine], which targets JSON/NDJSON machine
    formats.

See Also:
- [`topmark.registry`][topmark.registry]
- [`topmark.core.machine`][topmark.core.machine]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.registry import FileTypeRegistry
from topmark.utils.introspection import format_callable_pretty

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


def _policy_name(obj: object | None) -> str:
    if obj is None:
        return ""
    name: str | None = getattr(obj, "name", None)
    return str(name) if name else obj.__class__.__name__


@dataclass(frozen=True, slots=True)
class FileTypeHumanItem:
    """Click-free, human-facing view of one file type."""

    name: str
    description: str

    extensions: tuple[str, ...]
    filenames: tuple[str, ...]
    patterns: tuple[str, ...]

    skip_processing: bool
    content_matcher_name: str | None
    insert_checker_name: str | None
    header_policy_name: str


@dataclass(frozen=True, slots=True)
class FileTypesHumanReport:
    """Click-free, human-facing report for `topmark filetypes`."""

    show_details: bool
    verbosity_level: int
    items: tuple[FileTypeHumanItem, ...]


@dataclass(frozen=True, slots=True)
class ProcessorFileTypeHumanItem:
    """Click-free, human-facing view of a file type entry used under a processor."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ProcessorHumanItem:
    """Click-free, human-facing view of one header processor binding group."""

    module: str
    class_name: str
    filetypes: tuple[str, ...] | tuple[ProcessorFileTypeHumanItem, ...]


@dataclass(frozen=True, slots=True)
class UnboundFileTypeHumanItem:
    """Click-free, human-facing view of an unbound file type entry."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ProcessorsHumanReport:
    """Click-free, human-facing report for `topmark processors`."""

    show_details: bool
    verbosity_level: int
    processors: tuple[ProcessorHumanItem, ...]
    unbound_filetypes: tuple[str, ...] | tuple[UnboundFileTypeHumanItem, ...]


def build_filetypes_human_report(
    *, show_details: bool, verbosity_level: int
) -> FileTypesHumanReport:
    """Build a Click-free report used by TEXT and MARKDOWN.

    Args:
        show_details: Whether consumers intend to display extended details.
        verbosity_level: Effective verbosity (consumers may ignore).

    Returns:
        A `FileTypesHumanReport` with one item per file type.
    """
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()

    items: list[FileTypeHumanItem] = []
    for k, v in sorted(ft_registry.items()):
        items.append(
            FileTypeHumanItem(
                name=k,
                description=v.description,
                extensions=tuple(v.extensions),
                filenames=tuple(v.filenames),
                patterns=tuple(v.patterns),
                skip_processing=v.skip_processing,
                content_matcher_name=(
                    format_callable_pretty(v.content_matcher)
                    if v.content_matcher is not None
                    else None
                ),
                insert_checker_name=(
                    format_callable_pretty(v.pre_insert_checker)
                    if v.pre_insert_checker is not None
                    else None
                ),
                header_policy_name=_policy_name(v.header_policy),
            )
        )

    return FileTypesHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        items=tuple(items),
    )


def build_processors_human_report(
    *,
    show_details: bool,
    verbosity_level: int,
) -> ProcessorsHumanReport:
    """Build a Click-free report used by TEXT and MARKDOWN for `processors`.

    Args:
        show_details: Whether consumers intend to display extended details.
        verbosity_level: Effective verbosity (consumers may ignore).

    Returns:
        A `ProcessorsHumanReport` grouping file types by header processor class and listing unbound
        file types.
    """
    from collections import defaultdict

    from topmark.registry import HeaderProcessorRegistry

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()

    # Invert mapping: (module, class) -> [filetype names]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name, proc in hp_registry.items():
        key: tuple[str, str] = (proc.__class__.__module__, proc.__class__.__name__)
        groups[key].append(name)

    processors: list[ProcessorHumanItem] = []
    for (mod, cls), names in sorted(groups.items()):
        ft_names: list[str] = sorted(names)
        if show_details:
            processors.append(
                ProcessorHumanItem(
                    module=mod,
                    class_name=cls,
                    filetypes=tuple(
                        ProcessorFileTypeHumanItem(
                            name=n,
                            description=ft_registry[n].description,
                        )
                        for n in ft_names
                    ),
                )
            )
        else:
            processors.append(
                ProcessorHumanItem(
                    module=mod,
                    class_name=cls,
                    filetypes=tuple(ft_names),
                )
            )

    unbound_names: list[str] = sorted([name for name in ft_registry if name not in hp_registry])
    if show_details:
        unbound_filetypes: tuple[str, ...] | tuple[UnboundFileTypeHumanItem, ...] = tuple(
            UnboundFileTypeHumanItem(name=n, description=ft_registry[n].description)
            for n in unbound_names
        )
    else:
        unbound_filetypes = tuple(unbound_names)

    return ProcessorsHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        processors=tuple(processors),
        unbound_filetypes=unbound_filetypes,
    )
