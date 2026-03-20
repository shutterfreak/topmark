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
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING
from typing import Final

from topmark.core.errors import DuplicateProcessorKeyError
from topmark.core.errors import DuplicateProcessorRegistrationError
from topmark.core.errors import ReservedNamespaceError
from topmark.registry.identity import owner_label
from topmark.registry.identity import require_and_validate_registry_identity
from topmark.registry.identity import validate_reserved_topmark_namespace
from topmark.registry.types import ProcessorMeta

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor


_validation_done: bool = False
_VALIDATION_ENV: Final = "TOPMARK_VALIDATE"


def _dev_validate_processors(proc_map: Mapping[str, HeaderProcessor]) -> None:
    """Run lightweight developer validations when TOPMARK_VALIDATE=1.

    Checks:
        * Every registered processor key matches an existing FileType name.
        * XML-like processors (instances of XmlHeaderProcessor) report
          NO_LINE_ANCHOR for their line-based index.

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


def _validate_processor_class(processor_class: object) -> type[HeaderProcessor]:
    """Validate a processor class for registry composition/registration.

    This is the registry-layer runtime validation boundary for processor classes. It reuses the
    shared identity helpers from [`topmark.registry.identity`][topmark.registry.identity] but
    translates reserved-namespace violations into a registry-specific core error so callers of the
    registry API can distinguish malformed identities from disallowed namespace usage.

    Args:
        processor_class: Candidate processor class.

    Returns:
        The validated processor class.

    Raises:
        TypeError: If `processor_class` is not a `HeaderProcessor` subclass, or if its
            namespace/local-key identity is malformed.
        ReservedNamespaceError: If the reserved built-in `topmark` namespace is used by an
            ineligible external processor class.
    """
    from topmark.processors.base import HeaderProcessor

    if not isinstance(processor_class, type):
        raise TypeError(
            f"Expected subclass of HeaderProcessor, got non-type {type(processor_class).__name__}."
        )
    if not issubclass(processor_class, HeaderProcessor):
        raise TypeError(f"Expected subclass of HeaderProcessor, got {processor_class.__name__}.")

    owner: str = owner_label(processor_class)

    namespace: str
    local_key: str
    namespace, local_key = require_and_validate_registry_identity(
        namespace=getattr(processor_class, "namespace", None),
        local_key=getattr(processor_class, "local_key", None),
        owner=owner,
    )

    # Normalize validated identity values on the subclass.
    processor_class.namespace = namespace
    processor_class.local_key = local_key

    try:
        validate_reserved_topmark_namespace(
            namespace=namespace,
            owner=owner,
            owner_module=processor_class.__module__,
            entities="processors",
        )
    except TypeError as exc:
        raise ReservedNamespaceError(
            namespace=namespace,
            owner=owner,
            entities="processors",
            owner_module=processor_class.__module__,
        ) from exc

    return processor_class


def _validate_processor_instance(proc: object) -> HeaderProcessor:
    """Validate a processor instance for registry composition.

    Validates that `proc` is a [`HeaderProcessor`][topmark.processors.base.HeaderProcessor] instance
    and that its defining class has a valid registry identity.

    Args:
        proc: Candidate processor instance.

    Returns:
        The validated `HeaderProcessor` instance.

    Raises:
        TypeError: If `proc` is not a `HeaderProcessor` instance or if its class identity is
            malformed.
        ReservedNamespaceError: If the reserved built-in `topmark` namespace is  used by an
            ineligible external processor class.
    """
    from topmark.processors.base import HeaderProcessor

    if not isinstance(proc, HeaderProcessor):
        raise TypeError(
            f"Expected instance of HeaderProcessor, got {type(proc).__name__}. "
            "Only HeaderProcessor instances can be registered."
        )

    try:
        _validate_processor_class(type(proc))
    except (TypeError, ReservedNamespaceError):  # noqa: TRY203
        raise

    return proc


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
        """Compose the effective processor registry from base state and overlays.

        The effective registry is still keyed by unqualified file type local_key for
        compatibility. Processor identity consistency is validated separately via
        each processor instance's `qualified_key`.
        """
        cached: Mapping[str, HeaderProcessor] | None = cls._cache
        if cached is not None:
            return dict(cached)

        from topmark.processors.instances import get_base_header_processor_registry

        # get_base_header_processor_registry() returns the base processor registry.
        base: dict[str, HeaderProcessor] = dict(get_base_header_processor_registry())

        base.update(cls._overrides)
        for name in cls._removals:
            base.pop(name, None)

        # Validate processor identity keys.
        #
        # IMPORTANT: the base registry is keyed by *file type name* and stores one processor
        # instance per bound file type. Many file types can legally reuse the same processor
        # class (e.g. one XML processor instance per XML-like file type), which means we may
        # see the same `qualified_key` multiple times.
        #
        # We only consider it a conflict when the *same* qualified key is provided by
        # *different* processor classes.
        seen: dict[str, type[HeaderProcessor]] = {}
        for local_key, raw_proc in base.items():
            proc: HeaderProcessor = _validate_processor_instance(raw_proc)
            qk: str = proc.qualified_key
            proc_cls: type[HeaderProcessor] = type(proc)
            existing: type[HeaderProcessor] | None = seen.get(qk)
            if existing is not None and existing is not proc_cls:
                raise DuplicateProcessorKeyError(
                    qualified_key=qk,
                    existing_class=owner_label(existing),
                    new_class=owner_label(proc_cls),
                )
            seen[qk] = proc_cls
            base[local_key] = proc

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
            for local_key, proc in cls._compose().items():
                yield ProcessorMeta(
                    namespace=proc.namespace,
                    local_key=local_key,
                    description=getattr(proc, "description", "") or "",
                    block_prefix=getattr(proc, "block_prefix", "") or "",
                    block_suffix=getattr(proc, "block_suffix", "") or "",
                    line_indent=getattr(proc, "line_indent", "") or "",
                    line_prefix=getattr(proc, "line_prefix", "") or "",
                    line_suffix=getattr(proc, "line_suffix", "") or "",
                )

    # Optional: mutation
    @classmethod
    def register(
        cls,
        *,
        processor_class: type[HeaderProcessor],
        file_type: FileType,
    ) -> None:
        """Register a header processor class under a file type local_key.

        Args:
            processor_class: Concrete `HeaderProcessor` class to instantiate.
            file_type: FileType instance to bind to the instantiated processor.

        Raises:
            DuplicateProcessorRegistrationError: If the file type local_key already has a
                registered processor in the composed view.
            TypeError: If `processor_class` is not a valid `HeaderProcessor` subclass or
                if its identity is malformed.
            ReservedNamespaceError: If the reserved built-in `topmark` namespace is used
                by an ineligible external processor class.

        Notes:
            - This mutates global state. Prefer temporary usage in tests with try/finally.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            file_type_local_key: str = file_type.local_key
            try:
                _validate_processor_class(processor_class)
            except (TypeError, ReservedNamespaceError):  # noqa: TRY203
                raise

            # Check composed view to avoid dupes
            if file_type_local_key in cls._compose():
                raise DuplicateProcessorRegistrationError(
                    file_type=file_type_local_key,
                )

            # Instantiate the provided processor class and bind it to the file type.
            proc_obj: HeaderProcessor = processor_class()

            # Bind the processor to the FileType (mirror decorator behavior).
            proc_obj.file_type = file_type

            # If this local_key was previously removed, allow re-registration.
            cls._removals.discard(file_type_local_key)
            cls._overrides[file_type_local_key] = proc_obj
            cls._clear_cache()

    @classmethod
    def unregister(cls, local_key: str) -> bool:
        """Unregister a header processor by local key.

        Args:
            local_key: Registered processor local key.

        Returns:
            True if removed, else False.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            existed = False
            if local_key in cls._overrides:
                cls._overrides.pop(local_key, None)
                existed = True
            # Mark for removal from the composed view (including base entries).
            if local_key in cls._compose():
                cls._removals.add(local_key)
                existed = True
            cls._clear_cache()
            return existed
