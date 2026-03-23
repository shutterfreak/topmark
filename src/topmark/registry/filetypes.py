# topmark:header:start
#
#   project      : TopMark
#   file         : filetypes.py
#   file_relpath : src/topmark/registry/filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Advanced public registry for file type definitions.

This module exposes read-oriented views and limited mutation hooks for the
composed file type registry used by TopMark. Most callers should prefer the
stable facade in [`topmark.registry.registry.Registry`][topmark.registry.registry.Registry];
this module primarily serves advanced integrations, plugins, and tests.

Notes:
    * Public views such as `as_mapping()` and `iter_meta()` are derived from a
      composed registry (base built-ins + entry points + local overlays -
      removals) and are exposed as `MappingProxyType` where appropriate.
    * `register()` and `unregister()` apply overlay-only changes; they do not
      mutate the base registry built by
      [`topmark.filetypes.instances`][topmark.filetypes.instances].
    * Overlay state is process-local and guarded by an `RLock`.
"""

from __future__ import annotations

from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import InvalidRegistryIdentityError
from topmark.core.errors import ReservedNamespaceError
from topmark.filetypes.model import FileType
from topmark.registry.identity import make_qualified_key
from topmark.registry.identity import owner_label
from topmark.registry.identity import require_and_validate_registry_identity
from topmark.registry.identity import validate_reserved_topmark_namespace
from topmark.registry.types import FileTypeMeta

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping


class FileTypeRegistry:
    """Composed registry view for file type definitions.

    Notes:
        - Only validated `FileType` instances are admitted to the effective registry.
        - Mutation hooks are intended for plugin authors and test scaffolding.
          Most integrations should consume metadata and read-only views instead.
    """

    _lock: RLock = RLock()

    _overrides: dict[str, FileType] = {}
    """Local overlays; applied on top of the base (built-ins + plugins).
    These *do not* mutate the base registry returned by instances."""

    _removals: set[str] = set()
    """Local-key removals only. Qualified-key unregister helpers must normalize
    through the resolved FileType and store `ft.local_key` here."""

    _cache: Mapping[str, FileType] | None = None
    """Local-key cache."""

    _cache_by_qualified_key: Mapping[str, FileType] | None = None
    """Qualified-key cache."""

    @classmethod
    def _validate_ft(cls, ft: object) -> FileType:
        """Validate a file type instance for registry composition/registration.

        This method is the registry-layer validation boundary for `FileType`
        instances. It reuses the shared identity helpers from
        [`topmark.registry.identity`][topmark.registry.identity] but translates
        reserved-namespace violations into a registry-specific core error so
        callers of the registry API can distinguish malformed identities from
        disallowed namespace usage.

        Args:
            ft: Candidate registry entry.

        Returns:
            The validated `FileType` instance.

        Raises:
            TypeError: If `ft` is not a `FileType`, or if its namespace/local-key
                identity is malformed.
            ReservedNamespaceError: If the reserved built-in `topmark` namespace
                is used by an ineligible external file type.
        """
        if not isinstance(ft, FileType):
            raise TypeError(
                f"Expected instance of FileType, got {type(ft).__name__}. "
                "Only FileType instances can be registered."
            )

        owner: str = owner_label(type(ft))

        namespace: str
        local_key: str
        namespace, local_key = require_and_validate_registry_identity(
            namespace=ft.namespace,
            local_key=ft.local_key,
            owner=owner,
        )

        # Normalize validated identity values on the instance.
        ft.namespace = namespace
        ft.local_key = local_key

        try:
            validate_reserved_topmark_namespace(
                namespace=namespace,
                owner=owner,
                owner_module=type(ft).__module__,
                entities="file types",
            )
        except TypeError as exc:
            raise ReservedNamespaceError(
                namespace=namespace,
                owner=owner,
                entities="file types",
                owner_module=type(ft).__module__,
            ) from exc

        return ft

    @classmethod
    def _clear_cache(cls) -> None:
        """Clear any cached composed views.

        This is primarily used by tests and by mutation helpers to ensure that subsequent
        `as_mapping()` calls see updated overlays or base registry changes.
        """
        cls._cache = None
        cls._cache_by_qualified_key = None

    @classmethod
    def _compose_by_local_key(cls) -> dict[str, FileType]:
        """Compose the effective file type registry by unqualified local key.

        Returns:
            Mapping of file type local key to validated `FileType` built from the
            base registry plus local overlays minus removals.

        Raises:
            ValueError: If a base registry entry is keyed under a local key that
                does not match the validated `FileType.local_key`.
        """
        # Use cached MappingProxy if available for performance
        cached: Mapping[str, FileType] | None = cls._cache
        if cached is not None:
            return dict(cached)

        from topmark.filetypes.instances import get_base_file_type_registry

        # 1. Start from base (built-ins + entry points)
        # We validate the base registry here once to ensure plugins didn't inject junk
        raw_base: dict[str, FileType] = get_base_file_type_registry()
        base: dict[str, FileType] = {}

        for ft_local_key, ft in raw_base.items():
            # First validate
            validated: FileType = cls._validate_ft(ft)
            if ft_local_key != validated.local_key:
                raise ValueError(
                    f"FileType registry key {ft_local_key!r} "
                    f"does not match FileType.local_key {validated.local_key!r}"
                )

            if ft_local_key in cls._removals:
                # Skip removals
                continue

            # Add validated entry to base registry
            base[ft_local_key] = validated

        # 2. Apply overrides (Validated during register())
        base.update(cls._overrides)

        cls._cache = MappingProxyType(base)
        return base

    @classmethod
    def _compose(cls) -> dict[str, FileType]:
        """Compose the effective file type registry keyed by qualified key."""
        # Use cached MappingProxy if available for performance
        cached: Mapping[str, FileType] | None = cls._cache_by_qualified_key
        if cached is not None:
            return dict(cached)

        local_map: dict[str, FileType] = cls._compose_by_local_key()
        composed: dict[str, FileType] = {}
        for ft in local_map.values():
            composed[ft.qualified_key] = ft

        cls._cache_by_qualified_key = MappingProxyType(composed)
        return dict(composed)

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered file type names (sorted).

        Returns:
            Tuple with sorted file type names.
        """
        with cls._lock:
            return tuple(sorted(cls._compose_by_local_key().keys()))

    @classmethod
    def qualified_keys(cls) -> tuple[str, ...]:
        """Return the qualified keys of all registered file types (sorted).

        TODO: define a stable and sensible "prioritized" sort helper (builtins lowest precedence).

        Returns:
            Tuple with sorted file type qualified keys.
        """
        with cls._lock:
            return tuple(sorted(cls._compose().keys()))

    @classmethod
    def namespaces(cls) -> tuple[str, ...]:
        """Return the namespaces of all registered file types (sorted).

        TODO: define a stable and sensible "prioritized" sort helper (builtins lowest precedence).

        Returns:
            Tuple with sorted file type namepaces.
        """
        with cls._lock:
            # Use set comprehension to return "sorted set" of namespaces
            return tuple(sorted({ft.namespace for ft in cls._compose().values()}))

    @classmethod
    def resolve_filetype_id(
        cls,
        file_type_id: str,
        *,
        default_namespace: str | None = None,
    ) -> FileType | None:
        """Resolve a file type identifier to a `FileType` instance.

        This helper supports both *unqualified* and *qualified* identifiers:

        - Unqualified: ``"<local_key>"``
        - Qualified: ``"<namespace>:<local_key>"``

        Args:
            file_type_id: Identifier to resolve (unqualified or qualified).
            default_namespace: Optional namespace constraint applied when the identifier is
                unqualified.

        Returns:
            The resolved `FileType` instance, or ``None`` if no matching entry exists.

        Raises:
            AmbiguousFileTypeIdentifierError: If an unqualified identifier would match multiple
                file types in the composed registry.
            InvalidRegistryIdentityError: If registration is attempted with an invalid registry
                identifier.

        Notes:
            The composed registry is still keyed by unqualified file type local_key for
            compatibility, but this resolver treats ``namespace:local_key`` as the canonical stable
            identity and is the preferred lookup entry point for namespace-aware code.
        """
        raw: str = file_type_id.strip()
        if not raw:
            return None

        # Qualified form: "namespace:local_key"
        if ":" in raw:
            namespace, sep, local_key = raw.partition(":")
            if not sep or not namespace or not local_key or ":" in local_key:
                raise InvalidRegistryIdentityError(
                    message=f"Malformed file type identifier: {raw!r}",
                    identifier=raw,
                    namespace=namespace or None,
                    local_key=local_key or None,
                )

            with cls._lock:
                return cls._compose().get(
                    make_qualified_key(namespace, local_key),
                )

        # Unqualified form: "local_key"
        with cls._lock:
            candidates: list[FileType] = [
                file_type
                for file_type in cls._compose_by_local_key().values()
                if file_type.local_key == raw
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
    def get(cls, file_type_key: str) -> FileType | None:
        """Return a file type by qualified key.

        Args:
            file_type_key: Qualified key used as the registry key.

        Returns:
            The file type if found, else None.
        """
        with cls._lock:
            return cls._compose().get(file_type_key)

    @classmethod
    def as_mapping_by_local_key(cls) -> Mapping[str, FileType]:
        """Return a read-only local-key compatibility view of file types (keyed by local key).

        Returns:
            Mapping of file type local key to `FileType`.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be mutated.
        """
        with cls._lock:
            cached: Mapping[str, FileType] | None = cls._cache
            if cached is not None:
                return cached

            # Compose a fresh view and cache it.
            # NOTE: tests may monkeypatch `_compose()`; do not rely on `_compose()`
            # to populate `_cache`.
            composed: dict[str, FileType] = cls._compose_by_local_key()
            cls._cache = MappingProxyType(composed)
            return cls._cache

    @classmethod
    def as_mapping(cls) -> Mapping[str, FileType]:
        """Return a read-only qualified-key canonical view of file types (keyed by qualified key).

        Returns:
            Mapping of file type qualified key to `FileType`.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be mutated.
        """
        with cls._lock:
            cached: Mapping[str, FileType] | None = cls._cache_by_qualified_key
            if cached is not None:
                return cached

            # Compose a fresh view and cache it.
            # NOTE: tests may monkeypatch `_compose()`; do not rely on `_compose()`
            # to populate `_cache`.
            composed: dict[str, FileType] = cls._compose()
            cls._cache_by_qualified_key = MappingProxyType(composed)
            return cls._cache_by_qualified_key

    @classmethod
    def iter_meta_by_local_key(cls) -> Iterator[FileTypeMeta]:
        """Iterate over read-only local-key compatibility view for registered file types.

        No getattr needed because types are guaranteed.

        Yields:
            Serializable ``FileTypeMeta`` metadata about each file type.
        """
        with cls._lock:
            for ft in cls._compose_by_local_key().values():
                yield FileTypeMeta(
                    local_key=ft.local_key,
                    namespace=ft.namespace,
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
    def iter_meta(cls) -> Iterator[FileTypeMeta]:
        """Iterate over qualified-key canonical view for registered file types.

        No getattr needed because types are guaranteed.

        Yields:
            Serializable `FileTypeMeta` metadata about each file type.
        """
        with cls._lock:
            for ft in cls._compose().values():
                yield FileTypeMeta(
                    local_key=ft.local_key,
                    namespace=ft.namespace,
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
            ft_obj: A `FileType` with a unique, non-empty `.local_key`.

        Raises:
            ValueError: If `.local_key` is empty or already registered.

        Notes:
            - This mutates global registry state. Prefer temporary usage in tests with
              try/finally to ensure cleanup.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        # Strict validation of ft_obj type (`FileType``) and ft_obj.local_key (nonempty `str`)
        # before touching state
        _ = cls._validate_ft(ft_obj)

        with cls._lock:
            local_key: str = ft_obj.local_key
            if not local_key.strip():
                raise ValueError(
                    f"FileType.local_key must be a nonempty string (found {local_key!r})."
                )
            # Check against *composed* view to avoid dupes
            if local_key in cls._compose_by_local_key():
                raise ValueError(f"Duplicate FileType local_key: {local_key}")
            # Record override locally (no base mutation)
            cls._overrides[local_key] = ft_obj
            # If this local_key was previously removed, allow re-registration.
            cls._removals.discard(local_key)
            cls._clear_cache()

    @classmethod
    def unregister_by_local_key(cls, local_key: str) -> bool:
        """Unregister a file type by unqualified local key.

        Args:
            local_key: Registered file type local_key.

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
            if local_key in cls._overrides:
                cls._overrides.pop(local_key, None)
                existed = True
            # If present only in base, we still support hiding it
            if local_key in cls._compose_by_local_key():
                cls._removals.add(local_key)
                existed = True
            cls._clear_cache()
            return existed

    @classmethod
    def unregister(cls, file_type_key: str) -> bool:
        """Unregister a file type by qualified key.

        Args:
            file_type_key: Registered file type qualified key.

        Returns:
            `True` if the entry existed and was removed, else `False`.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            ft: FileType | None = cls._compose().get(file_type_key)
            if ft is None:
                return False

            # Remove local override (if any) and mark for removal from base
            local_key: str = ft.local_key
            existed = False
            if local_key in cls._overrides:
                cls._overrides.pop(local_key, None)
                existed = True
            # If present only in base, we still support hiding it
            if local_key in cls._compose_by_local_key():
                cls._removals.add(local_key)
                existed = True
            cls._clear_cache()
            return existed
