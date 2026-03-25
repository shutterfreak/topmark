# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/presentation/shared/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared Click-free preparers for human-facing registry output.

This module prepares typed, human-facing report models for registry-related CLI commands. The
prepared data is intentionally presentation-agnostic and reused by:

- TEXT renderers under [`topmark.presentation.text`][topmark.presentation.text]
  (ANSI/console styling), and
- Markdown renderers under
  [`topmark.presentation.markdown`][topmark.presentation.markdown]
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

from topmark.api.commands.registry import list_filetypes
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.api.types import FileTypeInfo
    from topmark.api.types import FileTypePolicyInfo
    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorDefinition


@dataclass(frozen=True, slots=True)
class FileTypePolicyHumanItem:
    r"""Stable metadata describing header insertion/stripping policy for a file type.

    These attributes are optional; processors read them to adapt behavior without
    hard-coding language specifics. Defaults are conservative and aim to preserve
    user-authored whitespace while keeping round-trips stable.

    Attributes:
        supports_shebang: Whether this file type commonly starts with a POSIX
            shebang (e.g., ``#!/usr/bin/env bash``). When ``True``, processors may
            skip a leading shebang during placement.
        encoding_line_regex: Optional regex (string) that matches an
            encoding declaration line *immediately after* a shebang (e.g., Python
            PEP 263). When provided and a shebang was skipped, a matching line is
            also skipped for placement.
        pre_header_blank_after_block: Number of blank lines to place between a
            preamble block (shebang/encoding or similar) and the header. Typically 1.
        ensure_blank_after_header: Ensure exactly one blank line follows the
            header when body content follows. No extra blank is added at EOF.
        blank_collapse_mode: How to identify and collapse *blank*
            lines around the header during insert/strip repairs. See
            `BlankCollapseMode` for semantics. Defaults to ``STRICT``.
        blank_collapse_extra: Additional characters to treat as blank **in
            addition** to those covered by ``blank_collapse_mode``. For example,
            set to ``\"\\x0c\"`` to consider form-feed collapsible for a given type.
    """

    supports_shebang: bool
    encoding_line_regex: str | None

    pre_header_blank_after_block: int
    ensure_blank_after_header: bool

    # How to identify and collapse “blank” lines around the header during insert/strip repairs.
    blank_collapse_mode: str
    blank_collapse_extra: str


@dataclass(frozen=True, slots=True)
class FileTypeHumanItem:
    """Click-free, human-facing view of one file type.

    Attributes:
        local_key: File type local key.
        namespace: Namespace that owns the file type.
        qualified_key: Canonical qualified file type key.
        description: Human-readable file type description.
        bound: Whether the file type currently has an effective processor binding.
        extensions: Registered filename extensions.
        filenames: Exact registered filenames.
        patterns: Registered path or glob patterns.
        skip_processing: Whether TopMark recognizes but never mutates this type.
        has_content_matcher: Whether a content matcher is configured.
        has_insert_checker: Whether a pre-insert checker is configured.
        policy: Structured header policy metadata for human-facing rendering.
    """

    local_key: str
    namespace: str
    qualified_key: str
    description: str
    bound: bool

    extensions: tuple[str, ...]
    filenames: tuple[str, ...]
    patterns: tuple[str, ...]

    skip_processing: bool
    has_content_matcher: bool
    has_insert_checker: bool

    policy: FileTypePolicyHumanItem


@dataclass(frozen=True, slots=True)
class FileTypesHumanReport:
    """Click-free, human-facing report for `topmark filetypes`."""

    show_details: bool
    verbosity_level: int
    styled: bool
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
    styled: bool


def _build_filetype_policy_human_item(policy: FileTypePolicyInfo) -> FileTypePolicyHumanItem:
    """Build a Click-free file type policy human item used by TEXT and MARKDOWN.

    Args:
        policy: The file type policy info object.

    Returns:
        A `FileTypePolicyHumanItem` object representing the policy info object.
    """
    return FileTypePolicyHumanItem(
        supports_shebang=policy["supports_shebang"],
        encoding_line_regex=policy["encoding_line_regex"],
        pre_header_blank_after_block=policy["pre_header_blank_after_block"],
        ensure_blank_after_header=policy["ensure_blank_after_header"],
        blank_collapse_mode=policy["blank_collapse_mode"],
        blank_collapse_extra=policy["blank_collapse_extra"],
    )


def build_filetypes_human_report(
    *,
    show_details: bool,
    verbosity_level: int,
    styled: bool,
) -> FileTypesHumanReport:
    """Build a Click-free report used by TEXT and MARKDOWN.

    Args:
        show_details: Whether consumers intend to display extended details.
        verbosity_level: Effective verbosity (consumers may ignore).
        styled: Whether to render styled text output.

    Returns:
        A `FileTypesHumanReport` with one item per file type.
    """
    raw_items: list[FileTypeInfo] = list_filetypes()

    items: list[FileTypeHumanItem] = [
        FileTypeHumanItem(
            local_key=item["local_key"],
            namespace=item["namespace"],
            qualified_key=item["qualified_key"],
            description=item["description"],
            bound=item["bound"],
            extensions=tuple(item["extensions"]),
            filenames=tuple(item["filenames"]),
            patterns=tuple(item["patterns"]),
            skip_processing=item["skip_processing"],
            has_content_matcher=item["has_content_matcher"],
            has_insert_checker=item["has_insert_checker"],
            policy=_build_filetype_policy_human_item(item["policy"]),
        )
        for item in sorted(raw_items, key=lambda it: str(it["qualified_key"]))
    ]

    return FileTypesHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        items=tuple(items),
        styled=styled,
    )


def build_processors_human_report(
    *,
    show_details: bool,
    verbosity_level: int,
    styled: bool,
) -> ProcessorsHumanReport:
    """Build a Click-free report used by TEXT and MARKDOWN for `processors`.

    Args:
        show_details: Whether consumers intend to display extended details.
        verbosity_level: Effective verbosity (consumers may ignore).
        styled: Whether to render styled text output.

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
        styled=styled,
    )
