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
[`topmark.registry.machine.shapes`][topmark.registry.machine.shapes].
Serialization to JSON/NDJSON strings lives in
[`topmark.registry.machine.serializers`][topmark.registry.machine.serializers].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.registry import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.registry.machine.schemas import (
        FileTypeBriefEntry,
        FileTypeDetailEntry,
        FileTypeRef,
        FileTypeRefEntry,
        FileTypesPayload,
        ProcessorBriefEntry,
        ProcessorDetailEntry,
        ProcessorsPayload,
    )


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
    for key, ft in sorted(ft_registry.items()):
        if show_details:
            payload.append(_serialize_filetype_details(ft))
        else:
            brief: FileTypeBriefEntry = {"name": key, "description": ft.description}
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
    from collections import defaultdict

    from topmark.registry import HeaderProcessorRegistry

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()

    # Invert mapping: processor class -> [filetype names]
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for ft_name, proc in hp_registry.items():
        key: tuple[str, str] = (proc.__class__.__module__, proc.__class__.__name__)
        groups[key].append(ft_name)

    # File types without a bound processor
    unbound: list[str] = sorted([name for name in ft_registry if name not in hp_registry])

    processors: list[ProcessorBriefEntry | ProcessorDetailEntry] = []
    for (mod, cls), names in sorted(groups.items()):
        if show_details:
            ft_refs: list[FileTypeRefEntry] = [
                {"name": n, "description": ft_registry[n].description} for n in sorted(names)
            ]
            entry_d: ProcessorDetailEntry = {
                "module": mod,
                "class_name": cls,
                "filetypes": ft_refs,
            }
            processors.append(entry_d)
        else:
            ft_names: list[str] = sorted(names)
            entry_b: ProcessorBriefEntry = {
                "module": mod,
                "class_name": cls,
                "filetypes": ft_names,
            }
            processors.append(entry_b)

    unbound_payload: list[FileTypeRef] = []
    for name in unbound:
        if show_details:
            ref: FileTypeRefEntry = {"name": name, "description": ft_registry[name].description}
            unbound_payload.append(ref)
        else:
            unbound_payload.append(name)

    return {
        "processors": processors,
        "unbound_filetypes": unbound_payload,
    }
