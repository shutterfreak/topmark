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
prepared data is intentionally Click-free and reused by:

- TEXT renderers under [`topmark.presentation.text`][topmark.presentation.text]
  (ANSI/console styling), and
- Markdown renderers under
  [`topmark.presentation.markdown`][topmark.presentation.markdown]
  (documentation-friendly output).

TEXT renderers may use `verbosity_level` and `styled`; Markdown renderers treat
Markdown as document-oriented output and use `show_details` as the shared detail-depth control.

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

from topmark.api.commands.registry import list_bindings
from topmark.api.commands.registry import list_filetypes
from topmark.api.commands.registry import list_processors

if TYPE_CHECKING:
    from topmark.api.types import BindingInfo
    from topmark.api.types import FileTypeInfo
    from topmark.api.types import FileTypePolicyInfo
    from topmark.api.types import ProcessorInfo


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
    """Click-free, human-facing report for `topmark registry filetypes`."""

    show_details: bool
    verbosity_level: int
    styled: bool
    items: tuple[FileTypeHumanItem, ...]


@dataclass(frozen=True, slots=True)
class BindingHumanItem:
    """Click-free, human-facing view of one effective binding.

    Attributes:
        file_type_key: Canonical file type key.
        file_type_local_key: File type local key.
        file_type_namespace: Namespace that owns the file type.
        processor_key: Canonical processor key.
        processor_local_key: Processor local key.
        processor_namespace: Namespace that owns the processor.
        file_type_description: Human-readable file type description.
        processor_description: Human-readable processor description.
    """

    file_type_key: str
    file_type_local_key: str
    file_type_namespace: str

    processor_key: str
    processor_local_key: str
    processor_namespace: str

    file_type_description: str
    processor_description: str


@dataclass(frozen=True, slots=True)
class ProcessorHumanItem:
    """Click-free, human-facing view of one header processor.

    Attributes:
        local_key: Processor local key.
        namespace: Namespace that owns the processor.
        qualified_key: Canonical processor key.
        description: Human-readable processor description.
        bound: Whether the processor currently participates in at least one
            effective binding.
        line_indent: Line comment indent (if applicable).
        line_prefix: Line comment prefix (if applicable).
        line_suffix: Line comment suffix (if applicable).
        block_prefix: Block comment prefix (if applicable).
        block_suffix: Block comment suffix (if applicable).
    """

    local_key: str
    namespace: str
    qualified_key: str
    description: str
    bound: bool

    line_indent: str
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str


@dataclass(frozen=True, slots=True)
class UnboundFileTypeHumanItem:
    """Click-free, human-facing view of an unbound file type.

    Attributes:
        name: Qualified file type identifier shown in human-facing output.
        description: Human-readable file type description.
    """

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ProcessorsHumanReport:
    """Click-free, human-facing report for `topmark registry processors`."""

    show_details: bool
    verbosity_level: int
    processors: tuple[ProcessorHumanItem, ...]
    styled: bool


@dataclass(frozen=True, slots=True)
class BindingsHumanReport:
    """Click-free, human-facing report for `topmark registry bindings`."""

    show_details: bool
    verbosity_level: int
    bindings: tuple[BindingHumanItem, ...]
    unbound_filetypes: tuple[UnboundFileTypeHumanItem, ...]
    unused_processors: tuple[ProcessorHumanItem, ...]
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
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.

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
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.

    Returns:
        A `ProcessorsHumanReport` with one item per registered processor.
    """
    raw_items: list[ProcessorInfo] = list_processors()

    processors: list[ProcessorHumanItem] = [
        ProcessorHumanItem(
            local_key=item["local_key"],
            namespace=item["namespace"],
            qualified_key=item["qualified_key"],
            description=item["description"],
            bound=item["bound"],
            line_indent=item["line_indent"],
            line_prefix=item["line_prefix"],
            line_suffix=item["line_suffix"],
            block_prefix=item["block_prefix"],
            block_suffix=item["block_suffix"],
        )
        for item in sorted(raw_items, key=lambda it: str(it["qualified_key"]))
    ]

    return ProcessorsHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        processors=tuple(processors),
        styled=styled,
    )


def build_bindings_human_report(
    *,
    show_details: bool,
    verbosity_level: int,
    styled: bool,
) -> BindingsHumanReport:
    """Build a Click-free report used by TEXT and MARKDOWN for `bindings`.

    Args:
        show_details: Whether consumers intend to display extended details.
        verbosity_level: Effective TEXT verbosity; Markdown renderers ignore it.
        styled: Whether TEXT renderers should apply styling; Markdown renderers ignore it.

    Returns:
        A `BindingsHumanReport` with effective bindings, unbound file types, and
        currently unused processors.
    """
    raw_bindings: list[BindingInfo] = list_bindings()
    raw_filetypes: list[FileTypeInfo] = list_filetypes()
    raw_processors: list[ProcessorInfo] = list_processors()

    bindings: list[BindingHumanItem] = [
        BindingHumanItem(
            file_type_key=item["file_type_key"],
            file_type_local_key=item["file_type_local_key"],
            file_type_namespace=item["file_type_namespace"],
            processor_key=item["processor_key"],
            processor_local_key=item["processor_local_key"],
            processor_namespace=item["processor_namespace"],
            file_type_description=item["file_type_description"],
            processor_description=item["processor_description"],
        )
        for item in sorted(raw_bindings, key=lambda it: str(it["file_type_key"]))
    ]

    bound_filetype_keys: set[str] = {item.file_type_key for item in bindings}
    unbound_filetypes: list[UnboundFileTypeHumanItem] = [
        UnboundFileTypeHumanItem(
            name=item["qualified_key"],
            description=item["description"],
        )
        for item in sorted(raw_filetypes, key=lambda it: str(it["qualified_key"]))
        if item["qualified_key"] not in bound_filetype_keys
    ]

    unused_processors: list[ProcessorHumanItem] = [
        ProcessorHumanItem(
            local_key=item["local_key"],
            namespace=item["namespace"],
            qualified_key=item["qualified_key"],
            description=item["description"],
            bound=item["bound"],
            line_indent=item["line_indent"],
            line_prefix=item["line_prefix"],
            line_suffix=item["line_suffix"],
            block_prefix=item["block_prefix"],
            block_suffix=item["block_suffix"],
        )
        for item in sorted(raw_processors, key=lambda it: str(it["qualified_key"]))
        if not item["bound"]
    ]

    return BindingsHumanReport(
        show_details=show_details,
        verbosity_level=verbosity_level,
        bindings=tuple(bindings),
        unbound_filetypes=tuple(unbound_filetypes),
        unused_processors=tuple(unused_processors),
        styled=styled,
    )
