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

from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.machine.schemas import FileTypeBriefEntry
    from topmark.registry.machine.schemas import FileTypeDetailEntry
    from topmark.registry.machine.schemas import FileTypeRef
    from topmark.registry.machine.schemas import FileTypeRefEntry
    from topmark.registry.machine.schemas import FileTypesPayload
    from topmark.registry.machine.schemas import ProcessorBriefEntry
    from topmark.registry.machine.schemas import ProcessorDetailEntry
    from topmark.registry.machine.schemas import ProcessorsPayload


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
    return {
        "name": ft.name,
        "namespace": ft.namespace,
        "qualified_key": ft.qualified_key,
        "description": ft.description,
    }


def _serialize_filetype_details(ft: FileType) -> FileTypeDetailEntry:
    """Serialize the detailed machine payload for a single file type.

    Args:
        ft: File type runtime object.

    Returns:
        A `FileTypeDetailEntry` dict.
    """
    policy_name: str = _policy_name(ft.header_policy)
    return {
        "name": ft.name,
        "namespace": ft.namespace,
        "qualified_key": ft.qualified_key,
        "description": ft.description,
        "extensions": list(ft.extensions or []),
        "filenames": list(ft.filenames or []),
        "patterns": list(ft.patterns or []),
        "skip_processing": bool(ft.skip_processing),
        "has_content_matcher": ft.content_matcher is not None,
        "has_insert_checker": ft.pre_insert_checker is not None,
        "header_policy": policy_name,
    }


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
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()

    payload: list[FileTypeBriefEntry | FileTypeDetailEntry] = []
    for _key, ft in sorted(ft_registry.items()):
        if show_details:
            payload.append(_serialize_filetype_details(ft))
        else:
            brief: FileTypeBriefEntry = {
                "name": ft.name,
                "namespace": ft.namespace,
                "qualified_key": ft.qualified_key,
                "description": ft.description,
            }
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
    from topmark.registry.processors import HeaderProcessorRegistry

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()

    # Invert mapping: processor identity -> (processor exemplar, [file type names])
    groups: dict[tuple[str, str, str, str, str], tuple[HeaderProcessor, list[str]]] = {}
    for ft_name, proc in hp_registry.items():
        key: tuple[str, str, str, str, str] = (
            proc.namespace,
            proc.key,
            proc.qualified_key,
            proc.__class__.__module__,
            proc.__class__.__name__,
        )
        if key not in groups:
            groups[key] = (proc, [])
        groups[key][1].append(ft_name)

    # File types without a bound processor
    unbound: list[str] = sorted([name for name in ft_registry if name not in hp_registry])

    processors: list[ProcessorBriefEntry | ProcessorDetailEntry] = []
    for (_, _, _, _, _), (proc, names) in sorted(groups.items()):
        if show_details:
            ft_refs: list[FileTypeRefEntry] = [
                _serialize_filetype_ref(ft_registry[name]) for name in sorted(names)
            ]
            entry_d: ProcessorDetailEntry = {
                "namespace": proc.namespace,
                "key": proc.key,
                "qualified_key": proc.qualified_key,
                "module": proc.__class__.__module__,
                "class_name": proc.__class__.__name__,
                "filetypes": ft_refs,
            }
            processors.append(entry_d)
        else:
            ft_names: list[str] = [ft_registry[name].qualified_key for name in sorted(names)]
            entry_b: ProcessorBriefEntry = {
                "namespace": proc.namespace,
                "key": proc.key,
                "qualified_key": proc.qualified_key,
                "module": proc.__class__.__module__,
                "class_name": proc.__class__.__name__,
                "filetypes": ft_names,
            }
            processors.append(entry_b)

    unbound_payload: list[FileTypeRef] = []
    for name in unbound:
        file_type: FileType = ft_registry[name]
        if show_details:
            ref: FileTypeRefEntry = _serialize_filetype_ref(file_type)
            unbound_payload.append(ref)
        else:
            unbound_payload.append(file_type.qualified_key)

    return {
        "processors": processors,
        "unbound_filetypes": unbound_payload,
    }
