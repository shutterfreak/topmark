# topmark:header:start
#
#   file         : filetypes.py
#   file_relpath : src/topmark/registry/filetypes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public file type registry (advanced).

Exposes read-only views and optional mutation helpers for registered file
types. Most users should prefer the stable facade :class:`topmark.registry.Registry`.
This module is intended for plugins and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Iterator, Mapping, MutableMapping

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


@dataclass(frozen=True)
class FileTypeMeta:
    """Stable, serializable metadata about a registered FileType."""

    name: str
    description: str = ""
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    skip_processing: bool = False
    content_matcher: bool = False
    header_policy: str = ""


class FileTypeRegistry:
    """Stable, read-only oriented view with optional mutation hooks.

    Notes:
        - Mutation hooks are intended for plugin authors and test scaffolding;
          most integrations should use metadata views only.
    """

    _lock = RLock()

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered file type names (sorted).

        Returns:
            tuple[str, ...]: Sorted file type names.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get

        with cls._lock:
            return tuple(sorted(_get().keys()))

    @classmethod
    def supported_names(cls) -> tuple[str, ...]:
        """Return file type names that have a registered processor."""
        from topmark.filetypes.registry import get_header_processor_registry as _get_proc

        with cls._lock:
            return tuple(sorted(set(_get_proc().keys()) & set(cls.names())))

    @classmethod
    def unsupported_names(cls) -> tuple[str, ...]:
        """Return file type names that are recognized but unsupported."""
        from topmark.filetypes.registry import get_header_processor_registry as _get_proc

        with cls._lock:
            all_names = set(cls.names())
            supported = set(_get_proc().keys())
            return tuple(sorted(all_names - supported))

    @classmethod
    def get(cls, name: str) -> FileType | None:
        """Return a file type by name.

        Args:
            name: Registered file type name.

        Returns:
            FileType | None: The `FileType` object if found, else None.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get

        with cls._lock:
            return _get().get(name)

    @classmethod
    def as_mapping(cls) -> Mapping[str, FileType]:
        """Return a read-only mapping of file types.

        Returns:
            Mapping[str, FileType]: Name -> FileType mapping.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be mutated.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get

        with cls._lock:
            return MappingProxyType(_get())

    @classmethod
    def iter_meta(cls) -> Iterator[FileTypeMeta]:
        """Iterate over stable metadata for registered file types.

        Yields:
            FileTypeMeta: Serializable metadata about each file type.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get

        with cls._lock:
            for name, ft in _get().items():
                yield FileTypeMeta(
                    name=name,
                    description=getattr(ft, "description", "") or "",
                    extensions=tuple(getattr(ft, "extensions", ()) or ()),
                    filenames=tuple(getattr(ft, "filenames", ()) or ()),
                    patterns=tuple(getattr(ft, "patterns", ()) or ()),
                    skip_processing=bool(getattr(ft, "skip_processing", False)),
                    content_matcher=bool(getattr(ft, "has_content_matcher", False)),
                    header_policy=str(getattr(ft, "header_policy_name", "")),
                )

    # Optional: mutation (keep out of api.py until you’re ready to support it)
    @classmethod
    def register(
        cls,
        ft_obj: FileType,
        *,
        processor: type[HeaderProcessor] | None = None,
    ) -> None:
        """Register a new file type, and optionally attach a header processor.

        Args:
            ft_obj: A `FileType` with a unique, non-empty `.name`.
            processor: Optional `HeaderProcessor` instance or class to register for this file type.
                If provided, the processor will be registered and bound to this file type.

        Raises:
            ValueError: If `.name` is empty or already registered, or if a processor is provided
                and the file type already has a registered processor.

        Notes:
            - This mutates global registry state. Prefer temporary usage in tests with
              try/finally to ensure cleanup. If a processor is provided, it will be bound
              to the file type and registered, raising if a processor is already present.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get_ft
        from topmark.registry.processors import HeaderProcessorRegistry

        with cls._lock:
            reg: MutableMapping[str, "FileType"] = _get_ft()
            name = ft_obj.name or ""
            if not name:
                raise ValueError("FileType.name is required.")
            if name in reg:
                raise ValueError(f"Duplicate FileType name: {name}")
            reg[name] = ft_obj
            if processor is not None:
                # Chain to HeaderProcessorRegistry for linkage; raises on conflict
                HeaderProcessorRegistry.register(name, processor)

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a file type by name.

        Args:
            name: Registered file type name.

        Returns:
            bool: True if the entry existed and was removed, else False.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get

        with cls._lock:
            reg: MutableMapping[str, FileType] = _get()
            return reg.pop(name, None) is not None
