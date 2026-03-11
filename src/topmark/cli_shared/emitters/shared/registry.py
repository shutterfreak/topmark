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

from topmark.registry.filetypes import FileTypeRegistry
from topmark.utils.introspection import format_callable_pretty

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor


def _policy_name(obj: object | None) -> str:
    if obj is None:
        return ""
    name: str | None = getattr(obj, "name", None)
    return str(name) if name else obj.__class__.__name__


@dataclass(frozen=True, slots=True)
class FileTypeHumanItem:
    """Click-free, human-facing view of one file type.

    Attributes:
        name: Qualified file type identifier shown in human-facing output.
        description: Human-readable file type description.
        extensions: Registered filename extensions.
        filenames: Exact registered filenames.
        patterns: Registered path or glob patterns.
        skip_processing: Whether TopMark recognizes but never mutates this type.
        content_matcher_name: Pretty-printed content matcher name, if present.
        insert_checker_name: Pretty-printed insert-checker name, if present.
        header_policy_name: Human-readable header policy identifier.
    """

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
    """Click-free, human-facing view of a processor-bound file type entry.

    Attributes:
        name: Qualified file type identifier shown under the processor.
        description: Human-readable file type description.
    """

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ProcessorHumanItem:
    """Click-free, human-facing view of one header processor binding group.

    Attributes:
        module: Fully-qualified module path of the processor class.
        class_name: Processor class name.
        filetypes: Either qualified file type identifiers (brief mode) or
            expanded processor/file-type items (detail mode).
    """

    module: str
    class_name: str
    filetypes: tuple[str, ...] | tuple[ProcessorFileTypeHumanItem, ...]


@dataclass(frozen=True, slots=True)
class UnboundFileTypeHumanItem:
    """Click-free, human-facing view of an unbound file type entry.

    Attributes:
        name: Qualified file type identifier shown in human-facing output.
        description: Human-readable file type description.
    """

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
    for _, file_type in sorted(ft_registry.items()):
        items.append(
            FileTypeHumanItem(
                name=file_type.qualified_key,
                description=file_type.description,
                extensions=tuple(file_type.extensions),
                filenames=tuple(file_type.filenames),
                patterns=tuple(file_type.patterns),
                skip_processing=file_type.skip_processing,
                content_matcher_name=(
                    format_callable_pretty(file_type.content_matcher)
                    if file_type.content_matcher is not None
                    else None
                ),
                insert_checker_name=(
                    format_callable_pretty(file_type.pre_insert_checker)
                    if file_type.pre_insert_checker is not None
                    else None
                ),
                header_policy_name=_policy_name(file_type.header_policy),
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
        A `ProcessorsHumanReport` grouping qualified file type identifiers by
        header processor identity and listing unbound file types.
    """
    from topmark.registry.processors import HeaderProcessorRegistry

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()

    # Invert mapping: processor identity -> (processor exemplar, [file type names])
    groups: dict[tuple[str, str, str, str, str], tuple[HeaderProcessor, list[str]]] = {}
    for file_type_name, processor in hp_registry.items():
        key: tuple[str, str, str, str, str] = (
            processor.namespace,
            processor.key,
            processor.qualified_key,
            processor.__class__.__module__,
            processor.__class__.__name__,
        )
        if key not in groups:
            groups[key] = (processor, [])
        groups[key][1].append(file_type_name)

    processors: list[ProcessorHumanItem] = []
    for (_, _, _, _, _), (processor, names) in sorted(groups.items()):
        file_type_names: list[str] = sorted(names)
        if show_details:
            processors.append(
                ProcessorHumanItem(
                    module=processor.__class__.__module__,
                    class_name=processor.__class__.__name__,
                    filetypes=tuple(
                        ProcessorFileTypeHumanItem(
                            name=ft_registry[file_type_name].qualified_key,
                            description=ft_registry[file_type_name].description,
                        )
                        for file_type_name in file_type_names
                    ),
                )
            )
        else:
            processors.append(
                ProcessorHumanItem(
                    module=processor.__class__.__module__,
                    class_name=processor.__class__.__name__,
                    filetypes=tuple(
                        ft_registry[file_type_name].qualified_key
                        for file_type_name in file_type_names
                    ),
                )
            )

    unbound_names: list[str] = sorted([name for name in ft_registry if name not in hp_registry])
    if show_details:
        unbound_filetypes: tuple[str, ...] | tuple[UnboundFileTypeHumanItem, ...] = tuple(
            UnboundFileTypeHumanItem(
                name=ft_registry[file_type_name].qualified_key,
                description=ft_registry[file_type_name].description,
            )
            for file_type_name in unbound_names
        )
    else:
        unbound_filetypes = tuple(
            ft_registry[file_type_name].qualified_key for file_type_name in unbound_names
        )

    return ProcessorsHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        processors=tuple(processors),
        unbound_filetypes=unbound_filetypes,
    )
