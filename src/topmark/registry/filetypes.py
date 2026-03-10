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
[`topmark.registry.registry.Registry`][topmark.registry.registry.Registry]. This module is intended
for plugins and tests.

Notes:
    * All public views (`as_mapping()`, `names()`, etc.) are derived from a **composed**
      registry (base built-ins + entry points + local overlays − removals) and are
      returned as `MappingProxyType` to prevent accidental mutation.
    * `register()` / `unregister()` perform **overlay-only** changes. They do not mutate
      the internal base registry built by
      [`topmark.filetypes.instances`][topmark.filetypes.instances].
      Overlays are process-local and guarded by an `RLock`.
"""

from __future__ import annotations

import re
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

from topmark.constants import PACKAGE_NAME
from topmark.constants import TOPMARK_NAMESPACE
from topmark.constants import VALID_REGISTRY_TOKEN_RE
from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.filetypes.model import FileType
from topmark.registry.types import FileTypeMeta

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping


class FileTypeRegistry:
    """Stable, read-only oriented view with optional mutation hooks.

    Notes:
        - Guarantees that it only registers `FileType` instances;
        - Mutation hooks are intended for plugin authors and test scaffolding; most integrations
          should use metadata views only.
    """

    _lock: RLock = RLock()

    # Local overlays; applied on top of the base (built-ins + plugins).
    # These *do not* mutate the base registry returned by instances.
    _overrides: dict[str, FileType] = {}
    _removals: set[str] = set()
    _cache: Mapping[str, FileType] | None = None

    @classmethod
    def _validate_ft(cls, ft: object) -> FileType:
        """Centralized validation for FileType instances."""
        if not isinstance(ft, FileType):
            raise TypeError(
                f"Expected instance of FileType, got {type(ft).__name__}. "
                "Only FileType instances can be registered."
            )
        if not ft.name:
            raise ValueError("FileType instance must have a non-empty '.name' property.")

        namespace: str = ft.namespace
        if not namespace:
            raise TypeError(
                f"{cls.__module__}.{cls.__name__}: "
                "instance variable 'namespace' must be a non-empty str"
            )

        name: str = ft.name
        if not name:
            raise TypeError(
                f"{cls.__module__}.{cls.__name__}: instance variable 'name' must be a non-empty str"
            )

        def _is_valid_token(value: str) -> bool:
            # Lowercase, no colon, stable serialization.
            if value != value.lower():
                return False
            if ":" in value:
                return False
            return bool(re.fullmatch(VALID_REGISTRY_TOKEN_RE, value))

        if not _is_valid_token(namespace):
            raise TypeError(
                f"{cls.__module__}.{cls.__name__}: "
                f"'namespace' must match {VALID_REGISTRY_TOKEN_RE}, "
                "be lowercase, and not contain ':' "
                f"(found {namespace!r})"
            )
        if not _is_valid_token(name):
            raise TypeError(
                f"{cls.__module__}.{cls.__name__}: "
                f"'name' must match {VALID_REGISTRY_TOKEN_RE}, "
                "be lowercase, and not contain ':' "
                f"(found {name!r})"
            )

        # Reserve the builtin namespace for TopMark itself.
        if namespace == TOPMARK_NAMESPACE and not type(ft).__module__.startswith(
            f"{PACKAGE_NAME}."
        ):
            raise TypeError(
                f"{cls.__module__}.{cls.__name__}: "
                f"namespace '{TOPMARK_NAMESPACE}' is reserved for built-in TopMark file types"
            )

        return ft

    @classmethod
    def _clear_cache(cls) -> None:
        """Clear any cached composed views.

        This is primarily used by tests and by mutation helpers to ensure that subsequent
        `as_mapping()` calls see updated overlays or base registry changes.
        """
        cls._cache = None

    @classmethod
    def _compose(cls) -> dict[str, FileType]:
        """Compose base registry with local overlays/removals."""
        # Use cached MappingProxy if available for performance
        cached: Mapping[str, FileType] | None = cls._cache
        if cached is not None:
            return dict(cached)

        from topmark.filetypes.instances import get_base_file_type_registry

        # 1. Start from base (built-ins + entry points)
        # We validate the base registry here once to ensure plugins didn't inject junk
        raw_base: dict[str, FileType] = get_base_file_type_registry()
        base: dict[str, FileType] = {}

        for name, ft in raw_base.items():
            # First validate
            validated: FileType = cls._validate_ft(ft)
            if name != validated.name:
                raise ValueError(
                    f"FileType registry key {name!r} "
                    f"does not match FileType.name {validated.name!r}"
                )

            if name in cls._removals:
                # Skip removals
                continue

            # Add validated entry to base registry
            base[name] = validated

        # 2. Apply overrides (Validated during register())
        base.update(cls._overrides)

        cls._cache = MappingProxyType(base)
        return base

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered file type names (sorted).

        Returns:
            Tuple with sorted file type names.
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
    def resolve_filetype_id(
        cls,
        file_type_name: str,
        *,
        default_namespace: str | None = None,
    ) -> FileType | None:
        """Resolve a file type identifier to a `FileType` instance.

        This helper supports both *unqualified* and *qualified* identifiers:

        - Unqualified: ``"<name>"``
        - Qualified: ``"<namespace>:<name>"``

        Args:
            file_type_name: Identifier to resolve (unqualified or qualified).
            default_namespace: Optional namespace constraint applied when the
                identifier is unqualified.

        Returns:
            The resolved `FileType` instance, or ``None`` if no matching entry
            exists.

        Raises:
            AmbiguousFileTypeIdentifierError: If an unqualified identifier would
                match multiple file types in the composed registry.

        Notes:
            The composed registry is still keyed by unqualified file type name for
            compatibility, but this resolver treats ``namespace:name`` as the
            canonical stable identity and is the preferred lookup entry point for
            namespace-aware code.
        """
        raw: str = file_type_name.strip()
        if not raw:
            return None

        # Qualified form: "namespace:name"
        if ":" in raw:
            # Keep parsing strict: only one separator is allowed.
            namespace, sep, name = raw.partition(":")
            if not sep or not namespace or not name or ":" in name:
                return None
            with cls._lock:
                for file_type in cls._compose().values():
                    if file_type.name == name and file_type.namespace == namespace:
                        return file_type
                return None

        # Unqualified form: "name"
        with cls._lock:
            candidates: list[FileType] = [
                file_type
                for file_type in cls._compose().values()
                if file_type.name == raw
                and (default_namespace is None or file_type.namespace == default_namespace)
            ]
            if not candidates:
                return None
            if len(candidates) > 1:
                raise AmbiguousFileTypeIdentifierError(
                    file_type=raw,
                    candidates=tuple(sorted(ft.qualified_key for ft in candidates)),
                )
            return candidates[0]

    @classmethod
    def as_mapping(cls) -> Mapping[str, FileType]:
        """Return a read-only mapping of file types.

        Returns:
            Name -> FileType mapping.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be mutated.
        """
        with cls._lock:
            cached: Mapping[str, FileType] | None = cls._cache
            if cached is not None:
                return cached

            # Compose a fresh view and cache it.
            # NOTE: tests may monkeypatch `_compose()`; do not rely on `_compose()`
            # to populate `_cache`.
            composed: dict[str, FileType] = cls._compose()
            cls._cache = MappingProxyType(composed)
            return cls._cache

    @classmethod
    def iter_meta(cls) -> Iterator[FileTypeMeta]:
        """Iterate over stable metadata for registered file types.

        No getattr needed because types are guaranteed.

        Yields:
            Serializable `FileTypeMeta` metadata about each file type.
        """
        with cls._lock:
            for name, ft in cls._compose().items():
                yield FileTypeMeta(
                    name=name,
                    description=ft.description or "",
                    extensions=tuple(ft.extensions or ()),
                    filenames=tuple(ft.filenames or ()),
                    patterns=tuple(ft.patterns or ()),
                    skip_processing=ft.skip_processing,
                    content_matcher=ft.content_matcher is not None,
                    header_policy=ft.header_policy.to_dict()
                    if ft.header_policy is not None
                    else {},
                )

    @classmethod
    def register(
        cls,
        ft_obj: FileType,
    ) -> None:
        """Register a new file type.

        Args:
            ft_obj: A `FileType` with a unique, non-empty `.name`.

        Raises:
            ValueError: If `.name` is empty or already registered.

        Notes:
            - This mutates global registry state. Prefer temporary usage in tests with
              try/finally to ensure cleanup.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        # Strict validation of ft_obj type (`FileType``) and ft_obj.name (nonempty `str`)
        # before touching state
        _ = cls._validate_ft(ft_obj)

        with cls._lock:
            name: str = ft_obj.name
            if not name.strip():
                raise ValueError(f"FileType.name must be a nonempty string (found {name!r}).")
            # Check against *composed* view to avoid dupes
            if name in cls._compose():
                raise ValueError(f"Duplicate FileType name: {name}")
            # Record override locally (no base mutation)
            cls._overrides[name] = ft_obj
            # If this name was previously removed, allow re-registration.
            cls._removals.discard(name)
            cls._clear_cache()

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a file type by name.

        Args:
            name: Registered file type name.

        Returns:
            `True` if the entry existed and was removed, else `False`.

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
            cls._clear_cache()
            return existed
