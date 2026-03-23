# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/api/commands/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Registry introspection helpers (public API).

This module exposes small, serializable metadata views over TopMark's registries. It is the
supported API layer for "what is available?" queries and is used by the CLI emitters for
human-facing reports.

The functions here:
- Ensure built-in processors are registered (idempotent).
- Return TypedDict-based metadata (`FileTypeInfo`, `ProcessorInfo`, `BindingInfo`).
- Do not expose internal registry objects directly.

For advanced use (mutation, direct object access), use
[`topmark.registry.registry.Registry`][topmark.registry.registry.Registry] directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from topmark.api.types import BindingInfo
    from topmark.api.types import FileTypeInfo
    from topmark.api.types import ProcessorInfo
    from topmark.processors.base import HeaderProcessor

__all__ = (
    "list_bindings",
    "list_filetypes",
    "list_processors",
)


def list_filetypes(show_details: bool = False) -> list[FileTypeInfo]:
    """Return metadata about registered file types.

    Args:
        show_details: If `True`, include extended metadata such as patterns and
            policy.

    Returns:
        A list of `FileTypeInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `FileTypeRegistry` from
        [`topmark.registry`][]. This function returns metadata rather than the
        registry objects themselves.
    """
    items: list[FileTypeInfo] = []
    for local_key, ft in Registry.filetypes_by_local_key().items():
        info: FileTypeInfo = {
            "local_key": local_key,
            "namespace": getattr(ft, "namespace", ""),
            "qualified_key": getattr(ft, "qualified_key", ""),
            "description": getattr(ft, "description", ""),
        }
        if show_details:
            info.update(
                {
                    "bound": Registry.is_filetype_bound(file_type_id=local_key),
                    "extensions": tuple(getattr(ft, "extensions", ()) or ()),
                    "filenames": tuple(getattr(ft, "filenames", ()) or ()),
                    "patterns": tuple(getattr(ft, "patterns", ()) or ()),
                    "skip_processing": bool(getattr(ft, "skip_processing", False)),
                    "content_matcher": bool(getattr(ft, "has_content_matcher", False)),
                    "header_policy": str(getattr(ft, "header_policy_name", "")),
                }
            )
        items.append(info)
    return items


def list_processors(show_details: bool = False) -> list[ProcessorInfo]:
    """Return metadata about registered header processors.

    Args:
        show_details: If `True`, include extended details for line/block
            delimiters.

    Returns:
        A list of `ProcessorInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `HeaderProcessorRegistry` from
        [`topmark.registry`][]. This function returns metadata rather than the
        registry objects themselves.
    """
    items: list[ProcessorInfo] = []
    for qualified_key, proc_def in Registry.processors().items():
        proc_obj: HeaderProcessor = proc_def.processor_class()
        info: ProcessorInfo = {
            "local_key": getattr(proc_def, "local_key", ""),
            "namespace": getattr(proc_def, "namespace", ""),
            "qualified_key": qualified_key,
            "description": getattr(proc_obj, "description", ""),
        }
        if show_details:
            info.update(
                {
                    "line_indent": getattr(proc_obj, "line_indent", "") or "",
                    "line_prefix": getattr(proc_obj, "line_prefix", "") or "",
                    "line_suffix": getattr(proc_obj, "line_suffix", "") or "",
                    "block_prefix": getattr(proc_obj, "block_prefix", "") or "",
                    "block_suffix": getattr(proc_obj, "block_suffix", "") or "",
                }
            )
        items.append(info)
    return items


def list_bindings() -> list[BindingInfo]:
    """Return metadata about effective file-type-to-processor bindings.

    Returns:
        A list of `BindingInfo` dicts (stable, serializable metadata).

    Notes:
        This reports effective bindings only. Unbound file types are not
        included in the returned list.
    """
    items: list[BindingInfo] = []
    for binding in Registry.bindings():
        processor = binding.processor
        if processor is None:
            continue
        info: BindingInfo = {
            "file_type_key": binding.filetype.qualified_key,
            "file_type_local_key": binding.filetype.local_key,
            "file_type_namespace": binding.filetype.namespace,
            "processor_key": processor.qualified_key,
            "processor_local_key": processor.local_key,
            "processor_namespace": processor.namespace,
            "file_type_description": binding.filetype.description,
            "processor_description": processor.description,
        }
        items.append(info)
    return items
