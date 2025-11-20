# topmark:header:start
#
#   project      : TopMark
#   file         : filetypes.py
#   file_relpath : src/topmark/registry/filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public file type registry (advanced).

Exposes read-only views and optional mutation helpers for registered file
types. Most users should prefer the stable facade
[`topmark.registry.Registry`][topmark.registry.Registry]. This module is intended
for plugins and tests.

Notes:
    * All public views (`as_mapping()`, `names()`, etc.) are derived from a **composed**
      registry (base built-ins + entry points + local overlays − removals) and are
      returned as `MappingProxyType` to prevent accidental mutation.
    * `register()` / `unregister()` perform **overlay-only** changes. They do not mutate
      the internal base registry built by `topmark.filetypes.instances`. Overlays are
      process-local and guarded by an `RLock`.
    * `supported_names()` / `unsupported_names()` compute support against the **composed**
      header processor registry to reflect overlay registrations made via
      `HeaderProcessorRegistry`.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

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

    # Local overlays; applied on top of the base (built-ins + plugins).
    # These *do not* mutate the base registry returned by instances.
    _overrides: dict[str, FileType] = {}
    _removals: set[str] = set()

    @classmethod
    def _compose(cls) -> dict[str, FileType]:
        """Compose base registry with local overlays/removals."""
        from topmark.filetypes.instances import get_file_type_registry as _get_ft

        # Start from a shallow copy of the base mapping
        base: dict[str, FileType] = dict(_get_ft())
        # Apply overrides (late wins)
        base.update(cls._overrides)
        # Drop removals
        for name in cls._removals:
            base.pop(name, None)
        return base

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered file type names (sorted).

        Returns:
            tuple[str, ...]: Sorted file type names.
        """
        with cls._lock:
            return tuple(sorted(cls._compose().keys()))

    @classmethod
    def supported_names(cls) -> tuple[str, ...]:
        """Return file type names that have a registered processor."""
        from topmark.registry.processors import HeaderProcessorRegistry as _HPReg

        with cls._lock:
            proc_names: set[str] = set(_HPReg.as_mapping().keys())
            return tuple(sorted(proc_names & set(cls._compose().keys())))

    @classmethod
    def unsupported_names(cls) -> tuple[str, ...]:
        """Return file type names that are recognized but unsupported."""
        from topmark.registry.processors import HeaderProcessorRegistry as _HPReg

        with cls._lock:
            all_names: set[str] = set(cls._compose().keys())
            supported: set[str] = set(_HPReg.as_mapping().keys())
            return tuple(sorted(all_names - supported))

    @classmethod
    def get(cls, name: str) -> FileType | None:
        """Return a file type by name.

        Args:
            name (str): Registered file type name.

        Returns:
            FileType | None: The `FileType` object if found, else None.
        """
        with cls._lock:
            return cls._compose().get(name)

    @classmethod
    def as_mapping(cls) -> Mapping[str, FileType]:
        """Return a read-only mapping of file types.

        Returns:
            Mapping[str, FileType]: Name -> FileType mapping.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be mutated.
        """
        with cls._lock:
            return MappingProxyType(cls._compose())

    @classmethod
    def iter_meta(cls) -> Iterator[FileTypeMeta]:
        """Iterate over stable metadata for registered file types.

        Yields:
            FileTypeMeta: Serializable metadata about each file type.
        """
        with cls._lock:
            for name, ft in cls._compose().items():
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
            ft_obj (FileType): A `FileType` with a unique, non-empty `.name`.
            processor (type[HeaderProcessor] | None): Optional `HeaderProcessor` instance or class
                to register for this file type. If provided, the processor will be registered and
                bound to this file type.

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
        from topmark.registry.processors import HeaderProcessorRegistry

        with cls._lock:
            name: str = ft_obj.name or ""
            if not name:
                raise ValueError("FileType.name is required.")
            # Check against *composed* view to avoid dupes
            if name in cls._compose():
                raise ValueError(f"Duplicate FileType name: {name}")
            # Record override locally (no base mutation)
            cls._overrides[name] = ft_obj
            if processor is not None:
                # Chain to HeaderProcessorRegistry for linkage; raises on conflict
                HeaderProcessorRegistry.register(name, processor)

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a file type by name.

        Args:
            name (str): Registered file type name.

        Returns:
            bool: `True` if the entry existed and was removed, else `False`.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            # Remove local override (if any) and mark for removal from base
            existed = False
            if name in cls._overrides:
                existed = True
                cls._overrides.pop(name, None)
            # If present only in base, we still support hiding it
            if name in cls._compose():
                existed = True
                cls._removals.add(name)
            return existed
