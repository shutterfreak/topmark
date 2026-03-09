# topmark:header:start
#
#   project      : TopMark
#   file         : processors.py
#   file_relpath : src/topmark/registry/processors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public header processor registry (advanced).

Exposes read-only views and optional mutation helpers for registered header processors. Most users
should prefer the stable facade
[`topmark.registry.registry.Registry`][topmark.registry.registry.Registry]. This module is intended
for plugins and tests.

Notes:
    * Public views (`as_mapping()`, `names()`, `get()`) are sourced from a **composed**
      registry (base + local overrides - removals) and exposed as `MappingProxyType`.
    * `register()` / `unregister()` apply **overlay-only** changes; they do not mutate
      the internal base processor mapping constructed from explicit built-in bindings.
    * When registering a processor class, the target `FileType` is supplied by the
      caller so the instantiated processor can be bound consistently.
    * When the environment variable ``TOPMARK_VALIDATE`` is set to a truthy value
      (``1``, ``true``, ``yes``), lightweight developer validations will run on the
      composed processor mapping (see `_dev_validate_processors`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING
from typing import Final

from topmark.core.errors import DuplicateProcessorRegistrationError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor


_validation_done: bool = False
_VALIDATION_ENV: Final[str] = "TOPMARK_VALIDATE"


def _dev_validate_processors(proc_map: Mapping[str, HeaderProcessor]) -> None:
    """Run lightweight developer validations when TOPMARK_VALIDATE=1.

    This function is a no-op unless the environment variable TOPMARK_VALIDATE
    is set to a truthy value ("1", "true", "yes"). It is executed at most once
    per process.
    """
    global _validation_done
    if _validation_done:
        return
    if os.getenv(_VALIDATION_ENV, "").lower() not in {"1", "true", "yes"}:
        return

    # Intentionally lightweight: avoid importing other registries or concrete processors
    # to prevent type-check-time import cycles.
    _validation_done = True


@dataclass(frozen=True)
class ProcessorMeta:
    """Stable, serializable metadata about a registered processor instance."""

    name: str
    description: str = ""
    line_prefix: str = ""
    line_suffix: str = ""
    block_prefix: str = ""
    block_suffix: str = ""


class HeaderProcessorRegistry:
    """Stable, read-only oriented view with optional mutation hooks.

    Notes:
        - Mutation hooks are intended for plugin authors and test scaffolding;
          most integrations should use metadata views only.
    """

    _lock: RLock = RLock()
    _overrides: dict[str, HeaderProcessor] = {}
    _removals: set[str] = set()
    _cache: Mapping[str, HeaderProcessor] | None = None

    @classmethod
    def _clear_cache(cls) -> None:
        """Clear any cached composed views.

        Primarily used by tests and by mutation helpers so subsequent `as_mapping()`
        calls reflect updated overlays/removals or base registry state.
        """
        cls._cache = None

    @classmethod
    def _compose(cls) -> dict[str, HeaderProcessor]:
        """Compose base processor registry with local overrides/removals."""
        cached: Mapping[str, HeaderProcessor] | None = cls._cache
        if cached is not None:
            return dict(cached)

        from topmark.processors.instances import get_base_header_processor_registry

        # get_base_header_processor_registry() returns the base processor registry.
        base: dict[str, HeaderProcessor] = dict(get_base_header_processor_registry())
        base.update(cls._overrides)
        for name in cls._removals:
            base.pop(name, None)
        _dev_validate_processors(base)

        cls._cache = MappingProxyType(base)
        return dict(base)

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered header processor names (sorted).

        Returns:
            Sorted processor names.
        """
        with cls._lock:
            return tuple(sorted(cls._compose().keys()))

    @classmethod
    def is_registered(cls, file_type_name: str) -> bool:
        """Return True if a processor is registered for the given file type name."""
        with cls._lock:
            return file_type_name in cls._compose()

    @classmethod
    def get(cls, name: str) -> HeaderProcessor | None:
        """Return a header processor by name.

        Args:
            name: File type name used as the processor registry key.

        Returns:
            The processor if found, else None.
        """
        with cls._lock:
            return cls._compose().get(name)

    @classmethod
    def as_mapping(cls) -> Mapping[str, HeaderProcessor]:
        """Return a read-only mapping of header processors.

        Returns:
            Mapping of file type name to bound `HeaderProcessor` instance.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be mutated.
        """
        with cls._lock:
            cached: Mapping[str, HeaderProcessor] | None = cls._cache
            if cached is not None:
                return cached

            # Compose a fresh view and cache it.
            # NOTE: tests may monkeypatch `_compose()`; do not rely on `_compose()`
            # to populate `_cache`.
            composed: dict[str, HeaderProcessor] = cls._compose()
            cls._cache = MappingProxyType(composed)
            return cls._cache

    @classmethod
    def iter_meta(cls) -> Iterator[ProcessorMeta]:
        """Iterate over stable metadata for registered processors.

        Yields:
            Serializable `ProcessorMeta` metadata about each processor.
        """
        with cls._lock:
            for name, proc in cls._compose().items():
                yield ProcessorMeta(
                    name=name,
                    description=getattr(proc, "description", "") or "",
                    line_prefix=getattr(proc, "line_prefix", "") or "",
                    line_suffix=getattr(proc, "line_suffix", "") or "",
                    block_prefix=getattr(proc, "block_prefix", "") or "",
                    block_suffix=getattr(proc, "block_suffix", "") or "",
                )

    # Optional: mutation
    @classmethod
    def register(
        cls,
        name: str,
        processor_class: type[HeaderProcessor],
        *,
        file_type: FileType,
    ) -> None:
        """Register a header processor class under a file type name.

        Args:
            name: File type name under which the processor appears in the registry.
            processor_class: Concrete `HeaderProcessor` class to instantiate.
            file_type: FileType instance to bind to the instantiated processor.

        Raises:
            DuplicateProcessorRegistrationError: If the file type name already has a
                registered processor in the composed view.

        Notes:
            - This mutates global state. Prefer temporary usage in tests with try/finally.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            # Check composed view to avoid dupes
            if name in cls._compose():
                raise DuplicateProcessorRegistrationError(
                    file_type=name,
                )

            # Instantiate the provided processor class and bind it to the file type.
            proc_obj: HeaderProcessor = processor_class()

            # Bind the processor to the FileType (mirror decorator behavior).
            proc_obj.file_type = file_type

            # If this name was previously removed, allow re-registration.
            cls._removals.discard(name)
            cls._overrides[name] = proc_obj
            cls._clear_cache()

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a header processor by name.

        Args:
            name: Registered processor name.

        Returns:
            True if removed, else False.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            existed = False
            if name in cls._overrides:
                cls._overrides.pop(name, None)
                existed = True
            # Mark for removal from the composed view (including base entries).
            if name in cls._compose():
                cls._removals.add(name)
                existed = True
            cls._clear_cache()
            return existed
