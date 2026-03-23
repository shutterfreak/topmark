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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.filetypes.model import FileType
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.types import ProcessorDefinition
from topmark.utils.introspection import format_callable_pretty

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorDefinition


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
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()

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

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()
    hp_registry: Mapping[str, ProcessorDefinition] = HeaderProcessorRegistry.as_mapping()
    binding_registry: Mapping[str, str] = BindingRegistry.as_mapping()

    # Build a helper map of file types by qualified key:
    ft_by_qk: dict[str, FileType] = {ft.qualified_key: ft for ft in ft_registry.values()}

    # Group by processor qualified key using binding_registry.items()
    groups: dict[str, tuple[ProcessorDefinition, list[FileType]]] = {}

    for filetype_qk, processor_qk in binding_registry.items():
        file_type: FileType | None = ft_by_qk.get(filetype_qk)
        if file_type is None:
            continue
        proc_definition: ProcessorDefinition | None = hp_registry.get(processor_qk)
        if proc_definition is None:
            continue

        if processor_qk not in groups:
            groups[processor_qk] = (proc_definition, [])
        groups[processor_qk][1].append(file_type)

    processors: list[ProcessorHumanItem] = []
    for _key, (proc_definition, bound_file_types_list) in sorted(groups.items()):
        sorted_file_types: list[FileType] = sorted(
            bound_file_types_list,
            key=lambda ft: ft.qualified_key,
        )
        if show_details:
            processors.append(
                ProcessorHumanItem(
                    module=proc_definition.processor_class.__module__,
                    class_name=proc_definition.processor_class.__name__,
                    filetypes=tuple(
                        ProcessorFileTypeHumanItem(
                            name=ft.qualified_key,
                            description=ft.description,
                        )
                        for ft in sorted_file_types
                    ),
                )
            )
        else:
            processors.append(
                ProcessorHumanItem(
                    module=proc_definition.processor_class.__module__,
                    class_name=proc_definition.processor_class.__name__,
                    filetypes=tuple(ft.qualified_key for ft in sorted_file_types),
                )
            )

    unbound_filetypes_list: list[FileType] = sorted(
        [ft for ft in ft_registry.values() if ft.qualified_key not in binding_registry],
        key=lambda ft: ft.qualified_key,
    )
    if show_details:
        unbound_filetypes: tuple[str, ...] | tuple[UnboundFileTypeHumanItem, ...] = tuple(
            UnboundFileTypeHumanItem(
                name=ft.qualified_key,
                description=ft.description,
            )
            for ft in unbound_filetypes_list
        )
    else:
        unbound_filetypes = tuple(ft.qualified_key for ft in unbound_filetypes_list)

    return ProcessorsHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        processors=tuple(processors),
        unbound_filetypes=unbound_filetypes,
    )
