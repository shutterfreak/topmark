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
    * Public views such as `as_mapping()` and `iter_meta()`
      are derived from a composed registry (base built-ins + local
      overlays - removals) and are exposed as `MappingProxyType` where
      appropriate.
    * `register()` and `unregister()` apply overlay-only
      changes; they do not mutate the base processor-definition registry built
      from explicit built-in bindings.
    * The canonical identity-oriented processor view is keyed by canonical
      processor key and exposed via `as_mapping()`.
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
    """

    _lock: RLock = RLock()
    _overrides: dict[str, ProcessorDefinition] = {}
    _removals: set[str] = set()
    _cache_by_qualified_key: Mapping[str, ProcessorDefinition] | None = None

    @classmethod
    def _clear_cache(cls) -> None:
        """Clear cached composed processor-registry views."""
        cls._cache_by_qualified_key = None

    @classmethod
    def _compose(cls) -> dict[str, ProcessorDefinition]:
        """Compose the effective processor-definition registry keyed by qualified key."""
        cached: Mapping[str, ProcessorDefinition] | None = cls._cache_by_qualified_key
        if cached is not None:
            return dict(cached)

        from topmark.processors.instances import get_base_processor_definition_registry

        raw_base: dict[str, ProcessorDefinition] = dict(get_base_processor_definition_registry())
        base: dict[str, ProcessorDefinition] = {}

        for qualified_key, proc_def in raw_base.items():
            proc_cls: type[HeaderProcessor] = _validate_processor_class(proc_def.processor_class)
            normalized = ProcessorDefinition(
                namespace=proc_cls.namespace,
                local_key=proc_cls.local_key,
                processor_class=proc_cls,
            )
            if qualified_key != normalized.qualified_key:
                raise DuplicateProcessorKeyError(
                    qualified_key=qualified_key,
                    existing_class=owner_label(proc_cls),
                    new_class=owner_label(proc_cls),
                )
            base[qualified_key] = normalized

        base.update(cls._overrides)
        for qualified_key in cls._removals:
            base.pop(qualified_key, None)

        seen: dict[str, type[HeaderProcessor]] = {}
        for qualified_key, proc_def in base.items():
            proc_cls = proc_def.processor_class
            existing: type[HeaderProcessor] | None = seen.get(qualified_key)
            if existing is not None and existing is not proc_cls:
                raise DuplicateProcessorKeyError(
                    qualified_key=qualified_key,
                    existing_class=owner_label(existing),
                    new_class=owner_label(proc_cls),
                )
            seen[qualified_key] = proc_cls

        _dev_validate_processors(base)

        cls._cache_by_qualified_key = MappingProxyType(base)
        return dict(base)

    @classmethod
    def qualified_keys(cls) -> tuple[str, ...]:
        """Return qualified keys of all registered processor definitions.

        Returns:
            Sorted tuple of processor qualified keys.
        """
        with cls._lock:
            # NOTE: keys are already unique
            return tuple(sorted(cls._compose().keys()))

    @classmethod
    def namespaces(cls) -> tuple[str, ...]:
        """Return namespaces represented in the processor-definition registry.

        Returns:
            Sorted tuple of unique processor namespaces.
        """
        with cls._lock:
            # Use set comprehension to return "sorted set" of namespaces
            return tuple(sorted({proc.namespace for proc in cls._compose().values()}))

    @classmethod
    def get(cls, processor_key: str) -> ProcessorDefinition | None:
        """Return a processor definition by canonical processor key.

        Args:
            processor_key: Canonical processor key.

        Returns:
            Matching `ProcessorDefinition`, or ``None`` if not found.
        """
        with cls._lock:
            return cls._compose().get(processor_key)

    @classmethod
    def as_mapping(cls) -> Mapping[str, ProcessorDefinition]:
        """Return the canonical processor-definition mapping keyed by qualified key.

        Returns:
            Mapping of canonical processor key to `ProcessorDefinition` objects.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be mutated.
        """
        with cls._lock:
            cached: Mapping[str, ProcessorDefinition] | None = cls._cache_by_qualified_key
            if cached is not None:
                return cached

            composed: dict[str, ProcessorDefinition] = cls._compose()
            cls._cache_by_qualified_key = MappingProxyType(composed)
            return cls._cache_by_qualified_key

    @classmethod
    def iter_meta(cls) -> Iterator[ProcessorMeta]:
        """Iterate over stable metadata for processor definitions.

        Yields:
            Serializable `ProcessorMeta` values describing each registered
            processor definition.
        """
        with cls._lock:
            for proc_def in cls._compose().values():
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
    def register(
        cls,
        *,
        processor_class: type[HeaderProcessor],
    ) -> ProcessorDefinition:
        """Register a processor definition.

        Args:
            processor_class: Concrete `HeaderProcessor` subclass to register.

        Returns:
            The registered `ProcessorDefinition`.

        Raises:
            DuplicateProcessorRegistrationError: If the effective registry
                already contains a processor for the same qualified key.
            TypeError: If `processor_class` is not a valid `HeaderProcessor`
                subclass or if its identity is malformed.
            ReservedNamespaceError: If the reserved built-in ``topmark``
                namespace is used by an ineligible external processor class.
        """  # noqa: DOC503 - documents propagated exceptions from underlying registry helpers
        with cls._lock:
            proc_cls: type[HeaderProcessor] = _validate_processor_class(processor_class)
            proc_def = ProcessorDefinition(
                namespace=proc_cls.namespace,
                local_key=proc_cls.local_key,
                processor_class=proc_cls,
            )
            qualified_key: str = proc_def.qualified_key

            if qualified_key in cls._compose():
                raise DuplicateProcessorRegistrationError(qualified_key=qualified_key)

            cls._removals.discard(qualified_key)
            cls._overrides[qualified_key] = proc_def
            cls._clear_cache()
            return proc_def

    @classmethod
    def unregister(cls, processor_key: str) -> bool:
        """Remove a processor definition from the effective registry by canonical processor key.

        Args:
            processor_key: Canonical processor key to remove.

        Returns:
            ``True`` if the processor definition was present in the effective
            registry, else ``False``.

        Notes:
            This mutates process-global registry overlay state.
        """
        with cls._lock:
            existed = False
            if processor_key in cls._overrides:
                cls._overrides.pop(processor_key, None)
                existed = True
            if processor_key in cls._compose():
                cls._removals.add(processor_key)
                existed = True
            cls._clear_cache()
            return existed
