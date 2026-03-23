# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/registry/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable public facade over TopMark's composed registries.

This module exposes the semver-stable registry surface for file types,
processors, and bindings. The concrete registries remain available for advanced
scenarios and tests, but the [`Registry`][topmark.registry.registry.Registry]
facade is the intended public entry point for read operations and controlled
mutation helpers.

Identity registries are used directly. The `Registry` façade is only for
cross-registry coordination.

A file type can be recognized (present in
[`topmark.registry.filetypes.FileTypeRegistry`][topmark.registry.filetypes.FileTypeRegistry])
while still being unbound if no effective binding exists for it in
[`topmark.registry.bindings.BindingRegistry`][topmark.registry.bindings.BindingRegistry].

Typical usage:
    ```python
    from topmark.registry.processors import HeaderProcessorRegistry
    from topmark.registry.registry import Registry

    filetypes = Registry.filetypes()
    processors = Registry.processors()
    bindings = Registry.bindings()

    proc_def = HeaderProcessorRegistry.register(processor_class=MyProcessor)
    Registry.bind(
        file_type_id="python",
        processor_key=proc_def.qualified_key,
    )
    ```

Warning:
    Registry mutations operate on process-global overlay state. In tests or
    temporary integration code, always clean them up explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.errors import UnknownFileTypeError
from topmark.registry.bindings import Binding
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition


class Registry:
    """Stable facade over the effective file type, processor, and binding registries.

    The facade itself is stateless. It delegates to the concrete registries and
    exposes the supported public read operations plus a small set of advanced
    mutation helpers.
    """

    # --- Queries ---

    @staticmethod
    def bindings() -> tuple[Binding, ...]:
        """Return a joined view of file types and their processor bindings.

        Each element contains the file type metadata and the optionally bound
        processor metadata (``None`` means recognized but currently unbound).

        Returns:
            Immutable tuple of joined binding entries.
        """
        return tuple(BindingRegistry.iter_bindings())

    @staticmethod
    def filetypes_by_local_key() -> Mapping[str, FileType]:
        """Return a read-only mapping of registered file types keyed by local key.

        Returns:
            Mapping of file type local key to concrete `FileType` instances.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be
            mutated.
        """
        return FileTypeRegistry.as_mapping_by_local_key()

    @staticmethod
    def filetypes() -> Mapping[str, FileType]:
        """Return a read-only mapping of registered file types keyed by qualified key.

        Returns:
            Mapping of file type qualified key to concrete `FileType`
            instances.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be
            mutated.
        """
        return FileTypeRegistry.as_mapping()

    @staticmethod
    def processors() -> Mapping[str, ProcessorDefinition]:
        """Return the canonical processor-definition mapping keyed by qualified key.

        Returns:
            Mapping of processor qualified key to `ProcessorDefinition`
            objects.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be
            mutated.
        """
        return HeaderProcessorRegistry.as_mapping()

    @staticmethod
    def get_filetype(file_type_key: str) -> FileType | None:
        """Return a file type by canonical file type key.

        Args:
            file_type_key: Canonical file type key.

        Returns:
            The matching `FileType`, or ``None`` if not found.
        """
        return FileTypeRegistry.get(file_type_key=file_type_key)

    @staticmethod
    def get_processor(processor_key: str) -> ProcessorDefinition | None:
        """Return a processor definition by canonical processor key.

        Args:
            processor_key: Canonical processor key.

        Returns:
            The matching `ProcessorDefinition`, or ``None`` if not found.
        """
        return HeaderProcessorRegistry.get(processor_key)

    # --- Resolution ---

    @staticmethod
    def resolve_processor(file_type_id: str) -> HeaderProcessor | None:
        """Resolve a runtime processor instance for a file type identifier.

        Args:
            file_type_id: File type identifier in local or qualified form.

        Returns:
            A newly instantiated processor bound to the resolved file type, or
            ``None`` if no processor is registered for that file type.
        """
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        if ft_obj is None:
            return None

        processor_qualified_key: str | None = BindingRegistry.get_processor_key(
            ft_obj.qualified_key,
        )
        if processor_qualified_key is None:
            return None

        proc_def: ProcessorDefinition | None = HeaderProcessorRegistry.get(
            processor_qualified_key,
        )
        if proc_def is None:
            return None

        proc_obj: HeaderProcessor = proc_def.processor_class()
        proc_obj.file_type = ft_obj
        return proc_obj

    # --- Binding/status inspection ---

    @staticmethod
    def is_filetype_bound(file_type_id: str) -> bool:
        """Return whether a file type identifier currently has a binding.

        Args:
            file_type_id: File type identifier in local or qualified form.

        Returns:
            ``True`` if the resolved file type currently has a binding, else ``False``.
        """
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        if ft_obj is None:
            return False
        return BindingRegistry.is_bound(ft_obj.qualified_key)

    @staticmethod
    def is_processor_bound(processor_key: str) -> bool:
        """Return whether a canonical processor key is referenced by any binding.

        Args:
            processor_key: Canonical processor key to query.

        Returns:
            ``True`` if the processor is referenced by any binding, else ``False``.
        """
        return BindingRegistry.is_processor_bound(processor_key)

    @staticmethod
    def bound_filetype_local_keys() -> tuple[str, ...]:
        """Return local keys of file types that currently have a binding.

        Returns:
            Sorted tuple of file type local keys that are currently bound.
        """
        return BindingRegistry.bound_filetype_local_keys()

    @staticmethod
    def unbound_filetype_local_keys() -> tuple[str, ...]:
        """Return local keys of recognized file types that currently lack a binding.

        Returns:
            Sorted tuple of file type local keys that are currently unbound.
        """
        return BindingRegistry.unbound_filetype_local_keys()

    @staticmethod
    def get_filetype_keys(
        processor_key: str,
    ) -> tuple[str, ...]:
        """Return the canonical file type keys currently bound to a processor.

        Args:
            processor_key: Canonical processor key.

        Returns:
            Sorted tuple of canonical file type keys currently bound to the
            processor.
        """
        return BindingRegistry.get_filetype_keys(processor_key)

    # --- Explicit binding mutation ---

    @staticmethod
    def bind(
        *,
        file_type_id: str,
        processor_key: str,
    ) -> None:
        """Bind an existing processor definition to a registered file type.

        This is the public binding-oriented facade helper. Processor
        definitions must already exist in `HeaderProcessorRegistry`; callers
        that need to create one should first call
        `HeaderProcessorRegistry.register()` and then bind the resulting
        canonical processor key through this method.

        Args:
            file_type_id: File type identifier that should be bound. Both
                ``"local_key"`` and qualified ``"namespace:local_key"`` forms are
                accepted.
            processor_key: Canonical processor key to bind.

        Raises:
            AmbiguousFileTypeIdentifierError: If an unqualified `file_type_id`
                matches multiple file types.
            InvalidRegistryIdentityError: If `file_type_id` is malformed.
            UnknownFileTypeError: If `file_type_id` does not resolve to a
                registered file type.
            ProcessorBindingError: If the processor key is unknown or
                if the file type is already bound.
        """  # noqa: DOC503 - documents propagated exceptions from underlying registry helpers
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)

        if ft_obj is None:
            raise UnknownFileTypeError(file_type=file_type_id)

        BindingRegistry.bind(
            file_type_key=ft_obj.qualified_key,
            processor_key=processor_key,
        )

    @staticmethod
    def unbind_filetype(file_type_id: str) -> bool:
        """Remove the binding for a file type identifier, keeping the processor definition.

        Args:
            file_type_id: File type identifier that should be bound. Both
                ``"local_key"`` and qualified ``"namespace:local_key"`` forms are
                accepted.

        Returns:
            ``True`` if a binding existed and was removed, else ``False``.

        Notes:
            This helper intentionally only removes the binding from the resolved
            file type to its processor. Processor definitions are identity-level
            registry entries and may still be shared by other file types. Use
            `unregister_processor()` if you need to remove the processor
            definition itself.
        """
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        if ft_obj is None:
            return False
        return BindingRegistry.unbind(ft_obj.qualified_key)

    @staticmethod
    def unbind_processor(processor_key: str) -> tuple[str, ...]:
        """Remove all bindings that currently reference a processor.

        Args:
            processor_key: Canonical processor key.

        Returns:
            Sorted tuple of canonical file type keys that were unbound.

        Notes:
            This helper only removes bindings. It does not unregister the
            processor definition itself.
        """
        return BindingRegistry.unbind_processor(processor_key)

    # --- Binding-aware processor removal ---

    @staticmethod
    def unregister_processor(
        processor_key: str,
        *,
        remove_bindings: bool = False,
    ) -> bool:
        """Unregister a processor definition by canonical processor key.

        Args:
            processor_key: Canonical processor key to unregister.
            remove_bindings: If ``True``, remove all existing bindings that point
                to the processor before unregistering it. If ``False``, the
                processor is only unregistered when no file types are currently
                bound to it.

        Returns:
            ``True`` if the processor definition was unregistered, else ``False``.

        Notes:
            This helper operates at the processor-identity level. Most callers
            that are working from a file type should prefer `unbind_filetype()`
            to remove a single file type binding. Use `remove_bindings=True` to
            explicitly clear all current bindings before unregistering the
            processor definition.
        """
        bound_filetype_qks: tuple[str, ...] = BindingRegistry.get_filetype_keys(
            processor_key,
        )

        if bound_filetype_qks and not remove_bindings:
            return False

        if remove_bindings:
            BindingRegistry.unbind_processor(processor_key)

        return HeaderProcessorRegistry.unregister(processor_key)
