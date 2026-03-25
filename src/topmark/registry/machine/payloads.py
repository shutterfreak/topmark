# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/registry/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Payload builders for registry-related machine output.

This module builds JSON-serializable payload *objects* (plain Python dicts/lists)
for registry-focused CLI commands:

- `topmark registry filetypes`
- `topmark registry processors`
- `topmark registry bindings`

The builders here are:
- Click-free and console-free.
- Deterministic (sorted) so output is stable for tests and downstream tooling.
- Focused on producing payloads only (no envelope/record shaping, no serialization).

Envelope/record shaping lives in
[`topmark.registry.machine.envelopes`][topmark.registry.machine.envelopes].
Serialization to JSON/NDJSON strings lives in
[`topmark.registry.machine.serializers`][topmark.registry.machine.serializers].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.api.commands.registry import list_bindings
from topmark.api.commands.registry import list_filetypes
from topmark.api.commands.registry import list_processors
from topmark.registry.machine.schemas import BindingBriefEntry
from topmark.registry.machine.schemas import BindingDetailEntry
from topmark.registry.machine.schemas import BindingsPayload
from topmark.registry.machine.schemas import FileTypeBriefEntry
from topmark.registry.machine.schemas import FileTypeDetailEntry
from topmark.registry.machine.schemas import FileTypePolicyEntry
from topmark.registry.machine.schemas import FileTypeRefEntry
from topmark.registry.machine.schemas import FileTypesPayload
from topmark.registry.machine.schemas import ProcessorBriefEntry
from topmark.registry.machine.schemas import ProcessorDetailEntry
from topmark.registry.machine.schemas import ProcessorRefEntry
from topmark.registry.machine.schemas import ProcessorsPayload

if TYPE_CHECKING:
    from topmark.api.types import BindingInfo
    from topmark.api.types import FileTypeInfo
    from topmark.api.types import FileTypePolicyInfo
    from topmark.api.types import ProcessorInfo


def _serialize_filetype_policy(policy: FileTypePolicyInfo) -> FileTypePolicyEntry:
    """Serialize structured file type policy metadata for machine output.

    Args:
        policy: File type policy metadata returned by the public API.

    Returns:
        A `FileTypePolicyEntry` dict preserving the stable API field names.
    """
    return FileTypePolicyEntry(
        supports_shebang=policy["supports_shebang"],
        encoding_line_regex=policy["encoding_line_regex"],
        pre_header_blank_after_block=policy["pre_header_blank_after_block"],
        ensure_blank_after_header=policy["ensure_blank_after_header"],
        blank_collapse_mode=policy["blank_collapse_mode"],
        blank_collapse_extra=policy["blank_collapse_extra"],
    )


def _serialize_processor_ref(item: ProcessorInfo) -> ProcessorRefEntry:
    """Serialize a processor reference entry for machine payloads.

    Args:
        item: Processor metadata returned by the public API.

    Returns:
        A `ProcessorRefEntry` dict containing stable identity fields.
    """
    return ProcessorRefEntry(
        local_key=item["local_key"],
        namespace=item["namespace"],
        qualified_key=item["qualified_key"],
        description=item["description"],
    )


def build_filetypes_payload(*, show_details: bool) -> FileTypesPayload:
    """Build the registry payload for `topmark registry filetypes`.

    Args:
        show_details: If True, include matching rules, binding state, and
            structured policy metadata.

    Returns:
        List of file type entries, sorted by canonical file type key.
    """
    raw_items: list[FileTypeInfo] = list_filetypes()

    payload: list[FileTypeBriefEntry | FileTypeDetailEntry] = []
    for item in sorted(raw_items, key=lambda it: str(it["qualified_key"])):
        if show_details:
            payload.append(
                FileTypeDetailEntry(
                    local_key=item["local_key"],
                    namespace=item["namespace"],
                    qualified_key=item["qualified_key"],
                    description=item["description"],
                    bound=item["bound"],
                    extensions=list(item["extensions"]),
                    filenames=list(item["filenames"]),
                    patterns=list(item["patterns"]),
                    skip_processing=item["skip_processing"],
                    has_content_matcher=item["has_content_matcher"],
                    has_insert_checker=item["has_insert_checker"],
                    policy=_serialize_filetype_policy(item["policy"]),
                )
            )
        else:
            payload.append(
                FileTypeBriefEntry(
                    local_key=item["local_key"],
                    namespace=item["namespace"],
                    qualified_key=item["qualified_key"],
                    description=item["description"],
                )
            )

    return payload


def build_processors_payload(*, show_details: bool) -> ProcessorsPayload:
    """Build the registry payload for `topmark registry processors`.

    Args:
        show_details: If True, include expanded identity and delimiter fields.

    Returns:
        A `ProcessorsPayload` dict sorted by canonical processor key.
    """
    raw_items: list[ProcessorInfo] = list_processors()

    processors: list[ProcessorBriefEntry | ProcessorDetailEntry] = []
    for item in sorted(raw_items, key=lambda it: str(it["qualified_key"])):
        if show_details:
            processors.append(
                ProcessorDetailEntry(
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
            )
        else:
            processors.append(
                ProcessorBriefEntry(
                    local_key=item["local_key"],
                    namespace=item["namespace"],
                    qualified_key=item["qualified_key"],
                    description=item["description"],
                )
            )

    return ProcessorsPayload(processors=processors)


def build_bindings_payload(*, show_details: bool) -> BindingsPayload:
    """Build the registry payload for `topmark registry bindings`.

    Shape:
        {
          "bindings": [...],
          "unbound_filetypes": [...],
          "unused_processors": [...],
        }

    Args:
        show_details: If True, expand bindings and reference entries with
            identity/description objects.

    Returns:
        A `BindingsPayload` dict whose lists are deterministically sorted.
    """
    raw_bindings: list[BindingInfo] = list_bindings()
    raw_filetypes: list[FileTypeInfo] = list_filetypes()
    raw_processors: list[ProcessorInfo] = list_processors()

    bindings: list[BindingBriefEntry | BindingDetailEntry] = []
    for item in sorted(raw_bindings, key=lambda it: str(it["file_type_key"])):
        if show_details:
            bindings.append(
                BindingDetailEntry(
                    file_type_key=item["file_type_key"],
                    file_type_local_key=item["file_type_local_key"],
                    file_type_namespace=item["file_type_namespace"],
                    processor_key=item["processor_key"],
                    processor_local_key=item["processor_local_key"],
                    processor_namespace=item["processor_namespace"],
                    file_type_description=item["file_type_description"],
                    processor_description=item["processor_description"],
                )
            )
        else:
            bindings.append(
                BindingBriefEntry(
                    file_type_key=item["file_type_key"],
                    processor_key=item["processor_key"],
                )
            )

    bound_filetype_keys: set[str] = {item["file_type_key"] for item in raw_bindings}
    unbound_filetypes: list[str | FileTypeRefEntry] = []
    for item in sorted(raw_filetypes, key=lambda it: str(it["qualified_key"])):
        if item["qualified_key"] in bound_filetype_keys:
            continue
        if show_details:
            unbound_filetypes.append(
                FileTypeRefEntry(
                    local_key=item["local_key"],
                    namespace=item["namespace"],
                    qualified_key=item["qualified_key"],
                    description=item["description"],
                )
            )
        else:
            unbound_filetypes.append(item["qualified_key"])

    unused_processors: list[str | ProcessorRefEntry] = []
    for item in sorted(raw_processors, key=lambda it: str(it["qualified_key"])):
        if item["bound"]:
            continue
        if show_details:
            unused_processors.append(_serialize_processor_ref(item))
        else:
            unused_processors.append(item["qualified_key"])

    return BindingsPayload(
        bindings=bindings,
        unbound_filetypes=unbound_filetypes,
        unused_processors=unused_processors,
    )
