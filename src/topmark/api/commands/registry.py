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
supported API layer for "what is available?" queries and is used by the
[`topmark.presentation`][topmark.presentation] presentation layer for
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

from topmark.api.types import BindingInfo
from topmark.api.types import FileTypeInfo
from topmark.api.types import FileTypePolicyInfo
from topmark.api.types import ProcessorInfo
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from topmark.filetypes.policy import FileTypeHeaderPolicy
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorMeta

__all__ = (
    "list_bindings",
    "list_filetypes",
    "list_processors",
)


def _build_filetype_policy_info(policy: FileTypeHeaderPolicy) -> FileTypePolicyInfo:
    """Build a `FileTypePolicyInfo` object for a given file type header policy."""
    return FileTypePolicyInfo(
        supports_shebang=policy.supports_shebang,
        encoding_line_regex=policy.encoding_line_regex,
        pre_header_blank_after_block=policy.pre_header_blank_after_block,
        ensure_blank_after_header=policy.ensure_blank_after_header,
        blank_collapse_mode=policy.blank_collapse_mode.value.lower(),
        blank_collapse_extra=policy.blank_collapse_extra,
    )


def list_filetypes() -> list[FileTypeInfo]:
    """Return metadata about registered file types.

    Returns:
        A list of `FileTypeInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `FileTypeRegistry` from
        [`topmark.registry`][]. This function returns metadata rather than the
        registry objects themselves.
    """
    return [
        FileTypeInfo(
            local_key=ft.local_key,
            namespace=ft.namespace,
            qualified_key=ft.qualified_key,
            description=ft.description,
            bound=Registry.is_filetype_bound(file_type_id=ft.qualified_key),
            extensions=tuple(ft.extensions),
            filenames=tuple(ft.filenames),
            patterns=tuple(ft.patterns),
            skip_processing=ft.skip_processing,
            has_content_matcher=bool(ft.content_matcher),
            has_insert_checker=bool(ft.pre_insert_checker),
            policy=_build_filetype_policy_info(ft.header_policy),
        )
        for ft in Registry.filetypes().values()
    ]


def list_processors() -> list[ProcessorInfo]:
    """Return metadata about registered header processors.

    Returns:
        A list of `ProcessorInfo` dicts (stable, serializable metadata).

    Notes:
        For object-level access, prefer `HeaderProcessorRegistry` from
        [`topmark.registry`][]. This function returns metadata rather than the
        registry objects themselves.
    """
    bound_processor_keys: set[str] = {
        binding.processor.qualified_key
        for binding in Registry.bindings()
        if binding.processor is not None
    }
    items: list[ProcessorInfo] = []
    for qualified_key, proc_def in Registry.processors().items():
        proc_obj: HeaderProcessor = proc_def.processor_class()
        info: ProcessorInfo = ProcessorInfo(
            local_key=getattr(proc_def, "local_key", ""),
            namespace=getattr(proc_def, "namespace", ""),
            qualified_key=qualified_key,
            description=getattr(proc_obj, "description", ""),
            bound=qualified_key in bound_processor_keys,
            line_indent=getattr(proc_obj, "line_indent", "") or "",
            line_prefix=getattr(proc_obj, "line_prefix", "") or "",
            line_suffix=getattr(proc_obj, "line_suffix", "") or "",
            block_prefix=getattr(proc_obj, "block_prefix", "") or "",
            block_suffix=getattr(proc_obj, "block_suffix", "") or "",
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
        processor: ProcessorMeta | None = binding.processor
        if processor is None:
            continue
        info: BindingInfo = BindingInfo(
            file_type_key=binding.filetype.qualified_key,
            file_type_local_key=binding.filetype.local_key,
            file_type_namespace=binding.filetype.namespace,
            processor_key=processor.qualified_key,
            processor_local_key=processor.local_key,
            processor_namespace=processor.namespace,
            file_type_description=binding.filetype.description,
            processor_description=processor.description,
        )
        items.append(info)
    return items
