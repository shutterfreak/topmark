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
- Return TypedDict-based metadata (`FileTypeInfo`, `ProcessorInfo`).
- Do not expose internal registry objects directly.

For advanced use (mutation, direct object access), use
[`topmark.registry.registry.Registry`][topmark.registry.registry.Registry] directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.processors.base import HeaderProcessor
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.api.types import FileTypeInfo
    from topmark.api.types import ProcessorInfo
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition

__all__ = (
    "list_filetypes",
    "list_processors",
)


def list_filetypes(long: bool = False) -> list[FileTypeInfo]:
    """Return metadata about registered file types.

    Args:
        long: If `True`, include extended metadata such as patterns and policy.

    Returns:
        A list of `FileTypeInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `FileTypeRegistry` from
        [`topmark.registry`][]. This function returns metadata (not the objects).
    """
    proc_reg: Mapping[str, object] = Registry.processors_by_qualified_key()

    items: list[FileTypeInfo] = []
    for name, ft in Registry.filetypes().items():
        processor: ProcessorDefinition | None = proc_reg.get(name, None) if proc_reg else None
        supported = bool(processor)
        processor_name: str | None = processor.processor_class.__name__ if processor else None
        info: FileTypeInfo = {
            "name": name,
            "description": getattr(ft, "description", ""),
        }
        if long:
            info.update(
                {
                    "supported": supported,
                    "processor_name": processor_name,
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


def list_processors(long: bool = False) -> list[ProcessorInfo]:
    """Return metadata about registered header processors.

    Args:
        long: If True, include extended details for line/block delimiters.

    Returns:
        A list of `ProcessorInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `HeaderProcessorRegistry` from
        [`topmark.registry`][]. This function returns metadata (not the objects).
    """
    items: list[ProcessorInfo] = []
    for name, proc_def in Registry.processors_by_qualified_key().items():
        proc_obj: HeaderProcessor = proc_def.processor_class()
        info: ProcessorInfo = {
            "name": name,
            "description": getattr(proc_obj, "description", ""),
        }
        if long:
            info.update(
                {
                    "line_prefix": getattr(proc_obj, "line_prefix", "") or "",
                    "line_suffix": getattr(proc_obj, "line_suffix", "") or "",
                    "block_prefix": getattr(proc_obj, "block_prefix", "") or "",
                    "block_suffix": getattr(proc_obj, "block_suffix", "") or "",
                }
            )
        items.append(info)
    return items
