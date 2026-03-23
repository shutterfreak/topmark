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

A file type can be recognized (present in
[`topmark.registry.filetypes.FileTypeRegistry`][topmark.registry.filetypes.FileTypeRegistry])
while still being unsupported if no processor binding exists for it.

Typical usage:
    ```python
    from topmark.registry.processors import HeaderProcessorRegistry
    from topmark.registry.registry import Registry

    filetypes = Registry.filetypes()
    processors = Registry.processors_by_qualified_key()
    bindings = Registry.bindings()

    proc_def = HeaderProcessorRegistry.register(processor_class=MyProcessor)
    Registry.bind_processor(
        file_type_id="python",
        processor_qualified_key=proc_def.qualified_key,
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

    # --- Read-only registry views ---

    @staticmethod
    def bindings() -> tuple[Binding, ...]:
        """Return a joined view of file types and their processor bindings.

        Each element contains the file type metadata and the optionally bound
        processor metadata (``None`` means recognized but unsupported).

        Returns:
            Immutable tuple of joined binding entries.
        """
        return tuple(BindingRegistry.iter_bindings())

    @staticmethod
    def filetypes() -> Mapping[str, FileType]:
        """Return a read-only mapping of registered file types keyed by local key.

        Returns:
            Mapping of file type local key to concrete `FileType` instances.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be
            mutated.
        """
        return FileTypeRegistry.as_mapping()

    @staticmethod
    def filetypes_by_qualified_key() -> Mapping[str, FileType]:
        """Return a read-only mapping of registered file types keyed by qualified key.

        Returns:
            Mapping of file type qualified key to concrete `FileType`
            instances.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be
            mutated.
        """
        return FileTypeRegistry.as_mapping_by_qualified_key()

    @staticmethod
    def processors_by_qualified_key() -> Mapping[str, ProcessorDefinition]:
        """Return the canonical processor-definition mapping keyed by qualified key.

        Returns:
            Mapping of processor qualified key to `ProcessorDefinition`
            objects.

        Notes:
            The returned mapping is a ``MappingProxyType`` and must not be
            mutated.
        """
        return HeaderProcessorRegistry.as_mapping_by_qualified_key()

    @staticmethod
    def get_filetype_by_qualified_key(qualified_key: str) -> FileType | None:
        """Return a file type by qualified key.

        Args:
            qualified_key: File type qualified key.

        Returns:
            The matching `FileType`, or ``None`` if not found.
        """
        return FileTypeRegistry.get_by_qualified_key(qualified_key=qualified_key)

    @staticmethod
    def get_processor_by_qualified_key(qualified_key: str) -> ProcessorDefinition | None:
        """Return a processor definition by qualified key.

        Args:
            qualified_key: Processor qualified key.

        Returns:
            The matching `ProcessorDefinition`, or ``None`` if not found.
        """
        return HeaderProcessorRegistry.get_by_qualified_key(qualified_key)

    # --- Runtime resolution ---

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

        processor_qualified_key: str | None = BindingRegistry.get_processor_key_for_filetype(
            ft_obj.qualified_key,
        )
        if processor_qualified_key is None:
            return None

        proc_def: ProcessorDefinition | None = HeaderProcessorRegistry.get_by_qualified_key(
            processor_qualified_key,
        )
        if proc_def is None:
            return None

        proc_obj: HeaderProcessor = proc_def.processor_class()
        proc_obj.file_type = ft_obj
        return proc_obj

    # --- Binding/status inspection ---

    @staticmethod
    def is_filetype_bound(local_key: str) -> bool:
        """Return whether the given file type local key currently has a binding.

        Args:
            local_key: File type local key to query.

        Returns:
            ``True`` if the file type currently has a binding, else ``False``.
        """
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(local_key)
        if ft_obj is None:
            return False
        return BindingRegistry.is_bound(ft_obj.qualified_key)

    @staticmethod
    def is_processor_bound(qualified_key: str) -> bool:
        """Return whether a processor qualified key is referenced by any binding.

        Args:
            qualified_key: Processor qualified key to query.

        Returns:
            ``True`` if the processor is referenced by any binding, else ``False``.
        """
        return BindingRegistry.is_processor_bound(qualified_key)

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
    def get_bound_filetype_qualified_keys_for_processor(
        qualified_key: str,
    ) -> tuple[str, ...]:
        """Return file type qualified keys currently bound to a processor.

        Args:
            qualified_key: Processor qualified key.

        Returns:
            Sorted tuple of file type qualified keys currently bound to the
            processor.
        """
        return BindingRegistry.get_filetype_keys_for_processor(qualified_key)

    # --- File type mutation ---

    @staticmethod
    def register_filetype(
        ft_obj: FileType,
        *,
        processor_class: type[HeaderProcessor] | None = None,
    ) -> None:
        """Register a file type and optionally bind a processor class.

        This is a convenience passthrough to
        [`FileTypeRegistry.register`][topmark.registry.filetypes.FileTypeRegistry.register].
        If `processor_class` is provided, the processor class is also registered
        in the header processor overlay registry and bound to `ft_obj`.

        Args:
            ft_obj: File type definition to register.
            processor_class: Optional `HeaderProcessor` class to register and
                bind to the registered file type.

        Notes:
            This mutates global overlay state. Prefer temporary usage in tests or
            controlled initialization code, with explicit cleanup when needed.
        """
        FileTypeRegistry.register(ft_obj)
        if processor_class is not None:
            proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
                processor_class=processor_class,
            )
            BindingRegistry.bind(
                filetype_qualified_key=ft_obj.qualified_key,
                processor_qualified_key=proc_def.qualified_key,
            )
        return None

    @staticmethod
    def unregister_filetype(local_key: str) -> bool:
        """Unregister a file type by local key.

        Args:
            local_key: File type local key to remove.

        Returns:
            ``True`` if the file type was present in the effective registry,
            else ``False``.
        """
        return FileTypeRegistry.unregister(local_key)

    # --- Explicit binding mutation ---

    @staticmethod
    def bind_processor(
        *,
        file_type_id: str,
        processor_qualified_key: str,
    ) -> None:
        """Bind an existing processor definition to a registered file type.

        This is the public binding-oriented facade helper. Processor
        definitions must already exist in `HeaderProcessorRegistry`; callers
        that need to create one should first call
        `HeaderProcessorRegistry.register()` and then bind the resulting
        qualified key through this method.

        Args:
            file_type_id: File type identifier that should be bound. Both
                ``"local_key"`` and ``"namespace:local_key"`` forms are
                accepted.
            processor_qualified_key: Processor qualified key to bind.

        Raises:
            AmbiguousFileTypeIdentifierError: If an unqualified `file_type_id`
                matches multiple file types.
            InvalidRegistryIdentityError: If `file_type_id` is malformed.
            UnknownFileTypeError: If `file_type_id` does not resolve to a
                registered file type.
            ProcessorBindingError: If the processor qualified key is unknown or
                if the file type is already bound.
        """  # noqa: DOC503 - documents propagated exceptions from underlying registry helpers
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)

        if ft_obj is None:
            raise UnknownFileTypeError(file_type=file_type_id)

        BindingRegistry.bind(
            filetype_qualified_key=ft_obj.qualified_key,
            processor_qualified_key=processor_qualified_key,
        )

    @staticmethod
    def unbind_filetype_by_local_key(local_key: str) -> bool:
        """Remove the binding for a file type local key without deleting the processor definition.

        Args:
            local_key: File type local key whose binding should be removed.

        Returns:
            ``True`` if a binding existed and was removed, else ``False``.

        Notes:
            This helper intentionally only removes the binding from the resolved
            file type to its processor. Processor definitions are identity-level
            registry entries and may still be shared by other file types. Use
            `unregister_processor_by_qualified_key()` if you need to remove the
            processor definition itself.
        """
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(local_key)
        if ft_obj is None:
            return False
        return BindingRegistry.unbind(ft_obj.qualified_key)

    @staticmethod
    def unbind_processor_by_qualified_key(qualified_key: str) -> tuple[str, ...]:
        """Remove all bindings that currently reference a processor.

        Args:
            qualified_key: Processor qualified key.

        Returns:
            Sorted tuple of file type qualified keys that were unbound.

        Notes:
            This helper only removes bindings. It does not unregister the
            processor definition itself.
        """
        return BindingRegistry.unbind_processor(qualified_key)

    # --- Binding-aware processor removal ---

    @staticmethod
    def unregister_processor_by_qualified_key(
        qualified_key: str,
        *,
        remove_bindings: bool = False,
    ) -> bool:
        """Unregister a processor definition by qualified key.

        Args:
            qualified_key: Processor qualified key to unregister.
            remove_bindings: If ``True``, remove all existing bindings that point
                to the processor before unregistering it. If ``False``, the
                processor is only unregistered when no file types are currently
                bound to it.

        Returns:
            ``True`` if the processor definition was unregistered, else ``False``.

        Notes:
            This helper operates at the processor-identity level. Most callers
            that are working from a file type should prefer
            `unbind_filetype_by_local_key()` to remove a single file type
            binding. Use `remove_bindings=True` to explicitly clear all current
            bindings before unregistering the processor definition.
        """
        bound_filetype_qks: tuple[str, ...] = BindingRegistry.get_filetype_keys_for_processor(
            qualified_key,
        )

        if bound_filetype_qks and not remove_bindings:
            return False

        if remove_bindings:
            BindingRegistry.unbind_processor(qualified_key)

        return HeaderProcessorRegistry.unregister_by_qualified_key(qualified_key)
