# topmark:header:start
#
#   project      : TopMark
#   file         : processors.py
#   file_relpath : src/topmark/registry/processors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Advanced public registry for processor definitions.

This module exposes read-oriented views and limited mutation hooks for the
composed processor registry used by TopMark. Most callers should prefer the
stable facade in [`topmark.registry.registry.Registry`][topmark.registry.registry.Registry];
this module primarily serves advanced integrations, plugins, and tests.

Notes:
    * Public views such as `as_mapping()`, `as_mapping_by_qualified_key()`, and
      `iter_meta()` are derived from a composed registry (base built-ins + local
      overlays - removals) and are exposed as `MappingProxyType` where
      appropriate.
    * `register()` and `unregister()` apply overlay-only changes; they do not
      mutate the base processor-definition registry built from explicit
      built-in bindings.
    * During the current migration phase, the compatibility mapping returned by
      `as_mapping()` is still keyed by `FileType.local_key`, while the canonical
      identity-oriented processor view is `as_mapping_by_qualified_key()`.
    * When the environment variable ``TOPMARK_VALIDATE`` is set to a truthy
      value (``1``, ``true``, ``yes``), lightweight developer validations run
      on the composed processor mapping.
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
from topmark.registry.types import ProcessorDefinition
from topmark.registry.types import ProcessorMeta

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor


_validation_done: bool = False
_VALIDATION_ENV: Final = "TOPMARK_VALIDATE"


def _dev_validate_processors(proc_map: Mapping[str, ProcessorDefinition]) -> None:
    """Run lightweight developer validations when TOPMARK_VALIDATE is enabled.

    The current checks are intentionally minimal and primarily act as a guard
    rail during development while the registry model is being refactored.

    Args:
        proc_map: Composed processor-definition mapping to validate.
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
    """Validate a processor class for registry registration and composition.

    This is the registry-layer runtime validation boundary for processor
    classes. It reuses the shared identity helpers from
    [`topmark.registry.identity`][topmark.registry.identity] and translates
    reserved-namespace violations into registry-specific core errors so callers
    of the registry API can distinguish malformed identities from disallowed
    namespace usage.

    Args:
        processor_class: Candidate processor class.

    Returns:
        The validated concrete `HeaderProcessor` subclass.

    Raises:
        TypeError: If `processor_class` is not a `HeaderProcessor` subclass or
            if its namespace/local-key identity is malformed.
        ReservedNamespaceError: If the reserved built-in ``topmark`` namespace
            is used by an ineligible external processor class.
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


class HeaderProcessorRegistry:
    """Composed registry view for processor definitions.

    Notes:
        - Only validated `HeaderProcessor` subclasses are admitted to the
          effective registry.
        - Mutation hooks are intended for plugin authors and test scaffolding.
          Most integrations should consume metadata and read-only views instead.
        - The compatibility mapping keyed by file type local key exists only
          during the current migration phase; the qualified-key mapping is the
          canonical identity-oriented view.
    """

    _lock: RLock = RLock()
    _overrides: dict[str, ProcessorDefinition] = {}
    _removals: set[str] = set()
    _cache: Mapping[str, ProcessorDefinition] | None = None
    _cache_by_qualified_key: Mapping[str, ProcessorDefinition] | None = None

    @classmethod
    def _clear_cache(cls) -> None:
        """Clear cached composed processor-registry views."""
        cls._cache = None
        cls._cache_by_qualified_key = None

    @classmethod
    def _compose(cls) -> dict[str, ProcessorDefinition]:
        """Compose the effective compatibility processor registry.

        Returns:
            Mapping of file type local key to `ProcessorDefinition`, built from
            the base processor-definition registry plus local overlays minus
            removals.

        Raises:
            DuplicateProcessorKeyError: If the composed compatibility mapping
                contains the same processor qualified key for different
                processor classes.
        """
        cached: Mapping[str, ProcessorDefinition] | None = cls._cache
        if cached is not None:
            return dict(cached)

        from topmark.processors.instances import get_base_processor_definition_registry

        raw_base: dict[str, ProcessorDefinition] = dict(get_base_processor_definition_registry())
        base: dict[str, ProcessorDefinition] = {}

        for file_type_local_key, proc_def in raw_base.items():
            proc_cls: type[HeaderProcessor] = _validate_processor_class(proc_def.processor_class)
            base[file_type_local_key] = ProcessorDefinition(
                namespace=proc_cls.namespace,
                local_key=proc_cls.local_key,
                processor_class=proc_cls,
            )

        base.update(cls._overrides)
        for name in cls._removals:
            base.pop(name, None)

        seen: dict[str, type[HeaderProcessor]] = {}
        for proc_def in base.values():
            qk: str = proc_def.qualified_key
            proc_cls = proc_def.processor_class
            existing: type[HeaderProcessor] | None = seen.get(qk)
            if existing is not None and existing is not proc_cls:
                raise DuplicateProcessorKeyError(
                    qualified_key=qk,
                    existing_class=owner_label(existing),
                    new_class=owner_label(proc_cls),
                )
            seen[qk] = proc_cls

        _dev_validate_processors(base)

        cls._cache = MappingProxyType(base)
        return dict(base)

    @classmethod
    def _compose_by_qualified_key(cls) -> dict[str, ProcessorDefinition]:
        """Compose the effective processor registry keyed by qualified key."""
        cached: Mapping[str, ProcessorDefinition] | None = cls._cache_by_qualified_key
        if cached is not None:
            return dict(cached)

        local_map: dict[str, ProcessorDefinition] = cls._compose()
        composed: dict[str, ProcessorDefinition] = {}
        for proc_def in local_map.values():
            existing: ProcessorDefinition | None = composed.get(proc_def.qualified_key)
            if existing is not None and existing.processor_class is not proc_def.processor_class:
                raise DuplicateProcessorKeyError(
                    qualified_key=proc_def.qualified_key,
                    existing_class=owner_label(existing.processor_class),
                    new_class=owner_label(proc_def.processor_class),
                )
            composed[proc_def.qualified_key] = proc_def

        cls._cache_by_qualified_key = MappingProxyType(composed)
        return dict(composed)

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return local keys from the compatibility processor mapping.

        Returns:
            Sorted tuple of file type local keys currently present in the
            compatibility mapping.
        """
        with cls._lock:
            return tuple(sorted(cls._compose().keys()))

    @classmethod
    def qualified_keys(cls) -> tuple[str, ...]:
        """Return qualified keys of all registered processor definitions.

        Returns:
            Sorted tuple of processor qualified keys.
        """
        with cls._lock:
            # NOTE: keys are already unique
            return tuple(sorted(cls._compose_by_qualified_key().keys()))

    @classmethod
    def namespaces(cls) -> tuple[str, ...]:
        """Return namespaces represented in the processor-definition registry.

        Returns:
            Sorted tuple of unique processor namespaces.
        """
        with cls._lock:
            # Use set comprehension to return "sorted set" of namespaces
            return tuple(
                sorted({proc.namespace for proc in cls._compose_by_qualified_key().values()})
            )

    @classmethod
    def is_registered(cls, file_type_name: str) -> bool:
        """Return whether the compatibility mapping contains a given local key."""
        with cls._lock:
            return file_type_name in cls._compose()

    @classmethod
    def get(cls, local_key: str) -> ProcessorDefinition | None:
        """Return a processor definition from the compatibility mapping.

        Args:
            local_key: File type local key used by the compatibility mapping.

        Returns:
            Matching `ProcessorDefinition`, or ``None`` if not found.
        """
        with cls._lock:
            return cls._compose().get(local_key)

    @classmethod
    def get_by_qualified_key(cls, qualified_key: str) -> ProcessorDefinition | None:
        """Return a processor definition by canonical qualified key.

        Args:
            qualified_key: Processor qualified key.

        Returns:
            Matching `ProcessorDefinition`, or ``None`` if not found.
        """
        with cls._lock:
            return cls._compose_by_qualified_key().get(qualified_key)

    @classmethod
    def as_mapping(cls) -> Mapping[str, ProcessorDefinition]:
        """Return the compatibility processor-definition mapping keyed by local key.

        Returns:
            Mapping of file type local key to `ProcessorDefinition`.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be
            mutated. This compatibility view exists during the current registry
            migration; the canonical identity-oriented processor view is
            `as_mapping_by_qualified_key()`.
        """
        with cls._lock:
            cached: Mapping[str, ProcessorDefinition] | None = cls._cache
            if cached is not None:
                return cached

            # Compose a fresh view and cache it.
            # NOTE: tests may monkeypatch `_compose()`; do not rely on `_compose()`
            # to populate `_cache`.
            composed: dict[str, ProcessorDefinition] = cls._compose()
            cls._cache = MappingProxyType(composed)
            return cls._cache

    @classmethod
    def as_mapping_by_qualified_key(cls) -> Mapping[str, ProcessorDefinition]:
        """Return the canonical processor-definition mapping keyed by qualified key.

        Returns:
            Mapping of processor qualified key to `ProcessorDefinition`.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be
            mutated.
        """
        with cls._lock:
            cached: Mapping[str, ProcessorDefinition] | None = cls._cache_by_qualified_key
            if cached is not None:
                return cached

            # Compose a fresh view and cache it.
            # NOTE: tests may monkeypatch `_compose()`; do not rely on `_compose()`
            # to populate `_cache`.
            composed: dict[str, ProcessorDefinition] = cls._compose_by_qualified_key()
            cls._cache_by_qualified_key = MappingProxyType(composed)
            return cls._cache_by_qualified_key

    @classmethod
    def iter_meta(cls) -> Iterator[ProcessorMeta]:
        """Iterate over stable metadata for processor definitions.

        Yields:
            Serializable `ProcessorMeta` metadata about each registered
            processor definition.
        """
        with cls._lock:
            for proc_def in cls._compose_by_qualified_key().values():
                proc_obj: HeaderProcessor = proc_def.processor_class()
                yield ProcessorMeta(
                    namespace=proc_def.namespace,
                    local_key=proc_def.local_key,
                    description=getattr(proc_obj, "description", "") or "",
                    block_prefix=getattr(proc_obj, "block_prefix", "") or "",
                    block_suffix=getattr(proc_obj, "block_suffix", "") or "",
                    line_indent=getattr(proc_obj, "line_indent", "") or "",
                    line_prefix=getattr(proc_obj, "line_prefix", "") or "",
                    line_suffix=getattr(proc_obj, "line_suffix", "") or "",
                )

    @classmethod
    def resolve_for_filetype(cls, file_type: FileType) -> HeaderProcessor | None:
        """Instantiate the processor currently registered for a file type.

        Args:
            file_type: File type for which a runtime processor instance is
                requested.

        Returns:
            Newly instantiated `HeaderProcessor` bound to `file_type`, or
            ``None`` if the compatibility mapping contains no processor for that
            file type.

        Notes:
            This is a legacy compatibility resolver. Binding-aware runtime
            resolution belongs in the higher-level registry facade.
        """
        with cls._lock:
            proc_def: ProcessorDefinition | None = cls._compose().get(file_type.local_key)
            if proc_def is None:
                return None

            proc_obj: HeaderProcessor = proc_def.processor_class()
            proc_obj.file_type = file_type
            return proc_obj

    @classmethod
    def register(
        cls,
        *,
        processor_class: type[HeaderProcessor],
        file_type: FileType,
    ) -> None:
        """Register a processor definition under a compatibility local key.

        Args:
            processor_class: Concrete `HeaderProcessor` subclass to register.
            file_type: File type whose `local_key` is used as the compatibility
                registry key during the current migration phase.

        Raises:
            DuplicateProcessorRegistrationError: If the compatibility mapping
                already contains a processor for `file_type.local_key`.
        """
        with cls._lock:
            file_type_local_key: str = file_type.local_key
            proc_cls: type[HeaderProcessor] = _validate_processor_class(processor_class)

            # Check composed view to avoid dupes
            if file_type_local_key in cls._compose():
                raise DuplicateProcessorRegistrationError(
                    file_type=file_type_local_key,
                )

            proc_def = ProcessorDefinition(
                namespace=proc_cls.namespace,
                local_key=proc_cls.local_key,
                processor_class=proc_cls,
            )

            cls._removals.discard(file_type_local_key)
            cls._overrides[file_type_local_key] = proc_def
            cls._clear_cache()

    @classmethod
    def unregister(cls, local_key: str) -> bool:
        """Remove a processor definition from the compatibility mapping.

        Args:
            local_key: Compatibility key to remove.

        Returns:
            ``True`` if the processor definition was present in the effective
            compatibility view, else ``False``.

        Notes:
            This mutates process-global registry overlay state.
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
