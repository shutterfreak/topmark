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

- `topmark filetypes`
- `topmark processors`

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

from topmark.filetypes.model import FileType
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.machine.schemas import FileTypeBriefEntry
from topmark.registry.machine.schemas import FileTypeDetailEntry
from topmark.registry.machine.schemas import FileTypeRefEntry
from topmark.registry.machine.schemas import FileTypesPayload
from topmark.registry.machine.schemas import ProcessorBriefEntry
from topmark.registry.machine.schemas import ProcessorDetailEntry
from topmark.registry.machine.schemas import ProcessorsPayload
from topmark.registry.types import ProcessorDefinition

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.registry.machine.schemas import FileTypeRef
    from topmark.registry.types import ProcessorDefinition


def _policy_name(obj: object | None) -> str:
    """Return a stable, human/machine-friendly name for a policy object.

    The registry output may include a file type's header policy. The policy object
    might expose a `.name` attribute; otherwise we fall back to the class name.

    Args:
        obj: Policy object or None.

    Returns:
        A stable string suitable for machine output.
    """
    if obj is None:
        return ""
    name: str | None = getattr(obj, "name", None)
    if name:
        return str(name)
    return obj.__class__.__name__


def _serialize_filetype_ref(ft: FileType) -> FileTypeRefEntry:
    """Serialize a file type reference entry for machine payloads.

    Args:
        ft: File type runtime object.

    Returns:
        A `FileTypeRefEntry` dict containing stable identity fields.
    """
    return FileTypeRefEntry(
        local_key=ft.local_key,
        namespace=ft.namespace,
        qualified_key=ft.qualified_key,
        description=ft.description,
    )


def _serialize_filetype_details(ft: FileType) -> FileTypeDetailEntry:
    """Serialize the detailed machine payload for a single file type.

    Args:
        ft: File type runtime object.

    Returns:
        A `FileTypeDetailEntry` dict.
    """
    policy_name: str = _policy_name(ft.header_policy)
    return FileTypeDetailEntry(
        local_key=ft.local_key,
        namespace=ft.namespace,
        qualified_key=ft.qualified_key,
        description=ft.description,
        extensions=list(ft.extensions or []),
        filenames=list(ft.filenames or []),
        patterns=list(ft.patterns or []),
        skip_processing=bool(ft.skip_processing),
        has_content_matcher=ft.content_matcher is not None,
        has_insert_checker=ft.pre_insert_checker is not None,
        header_policy=policy_name,
    )


def build_filetypes_payload(*, show_details: bool) -> FileTypesPayload:
    """Build the registry payload for `topmark filetypes`.

    Args:
        show_details: If True, include matching rules and capability flags.

    Returns:
        List of file type entries, sorted by file type key.

    Notes:
        - The returned structure is JSON-serializable.
        - Sorting is by the registry key to ensure stable output.
    """
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()

    payload: list[FileTypeBriefEntry | FileTypeDetailEntry] = []
    if show_details:
        for _key, ft in sorted(ft_registry.items()):
            payload.append(_serialize_filetype_details(ft))
    else:
        for _key, ft in sorted(ft_registry.items()):
            brief = FileTypeBriefEntry(
                local_key=ft.local_key,
                namespace=ft.namespace,
                qualified_key=ft.qualified_key,
                description=ft.description,
            )
            payload.append(brief)

    return payload


def build_processors_payload(*, show_details: bool) -> ProcessorsPayload:
    """Build the registry payload for `topmark processors`.

    Shape:
        {
          "processors": [
            {"module": "...", "class_name": "...", "filetypes": [...]},
            ...
          ],
          "unbound_filetypes": [...]
        }

    Args:
        show_details: If True, expand file type references with description objects.

    Returns:
        A `ProcessorsPayload` dict whose lists are deterministically sorted.

    Notes:
        - Processors are grouped by concrete processor class (module + class name).
        - `unbound_filetypes` are registry file types that do not have a bound processor.
    """
    from topmark.registry.bindings import BindingRegistry
    from topmark.registry.processors import HeaderProcessorRegistry

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()
    hp_registry: Mapping[str, ProcessorDefinition] = HeaderProcessorRegistry.as_mapping()
    binding_registry: Mapping[str, str] = BindingRegistry.as_mapping()
    ft_by_qk: dict[str, FileType] = {ft.qualified_key: ft for ft in ft_registry.values()}

    # Group by processor_qk

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

    # File types without a bound processor
    unbound_filetypes: list[FileType] = sorted(
        [ft for ft in ft_registry.values() if ft.qualified_key not in binding_registry],
        key=lambda ft: ft.qualified_key,
    )

    processors: list[ProcessorBriefEntry | ProcessorDetailEntry] = []
    for _key, (proc_definition, bound_file_types_list) in sorted(groups.items()):
        sorted_file_types: list[FileType] = sorted(
            bound_file_types_list,
            key=lambda ft: ft.qualified_key,
        )
        if show_details:
            ft_refs: list[FileTypeRefEntry] = [
                _serialize_filetype_ref(ft) for ft in sorted_file_types
            ]
            entry_d = ProcessorDetailEntry(
                namespace=proc_definition.namespace,
                local_key=proc_definition.local_key,
                qualified_key=proc_definition.qualified_key,
                module=proc_definition.processor_class.__module__,
                class_name=proc_definition.processor_class.__name__,
                filetypes=ft_refs,
            )
            processors.append(entry_d)
        else:
            ft_names: list[str] = [ft.qualified_key for ft in sorted_file_types]

            entry_b = ProcessorBriefEntry(
                namespace=proc_definition.namespace,
                local_key=proc_definition.local_key,
                qualified_key=proc_definition.qualified_key,
                module=proc_definition.processor_class.__module__,
                class_name=proc_definition.processor_class.__name__,
                filetypes=ft_names,
            )
            processors.append(entry_b)

    unbound_payload: list[FileTypeRef] = []
    for file_type in unbound_filetypes:
        if show_details:
            ref: FileTypeRefEntry = _serialize_filetype_ref(file_type)
            unbound_payload.append(ref)
        else:
            unbound_payload.append(file_type.qualified_key)

    return ProcessorsPayload(
        processors=processors,
        unbound_filetypes=unbound_payload,
    )
