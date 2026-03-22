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
    from topmark.registry.registry import Registry

    filetypes = Registry.filetypes()
    processors = Registry.processors_by_qualified_key()
    bindings = Registry.bindings()
    ```

Warning:
    Registry mutations operate on process-global overlay state. In tests or
    temporary integration code, always clean them up explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import DuplicateProcessorRegistrationError
from topmark.core.errors import InvalidRegistryIdentityError
from topmark.core.errors import ProcessorBindingError
from topmark.core.errors import ReservedNamespaceError
from topmark.core.errors import UnknownFileTypeError
from topmark.registry.bindings import Binding
from topmark.registry.bindings import BindingRegistry
from topmark.registry.bindings import iter_bindings
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

    @staticmethod
    def bindings() -> tuple[Binding, ...]:
        """Return joined view of file types and their processor bindings.

        Each element contains the file type metadata and the optionally bound
        processor metadata (``None`` means recognized but unsupported).

        Returns:
            Immutable sequence of bindings.
        """
        return tuple(iter_bindings())

    @staticmethod
    def filetypes() -> Mapping[str, FileType]:
        """Return a read-only mapping of registered file types keyed by local_key.

        The mapping is a ``MappingProxyType`` (mutations are not allowed).
        Keys are file type names (local_key) ; values are concrete FileType instances.
        """
        return FileTypeRegistry.as_mapping()

    @staticmethod
    def filetypes_by_qualified_key() -> Mapping[str, FileType]:
        """Return a read-only mapping of registered file types keyed by qualified_key.

        The mapping is a ``MappingProxyType`` (mutations are not allowed).
        Keys are qualified keys of file types; values are concrete FileType instances.
        """
        return FileTypeRegistry.as_mapping_by_qualified_key()

    @staticmethod
    def processors_by_qualified_key() -> Mapping[str, ProcessorDefinition]:
        """Return the canonical processor-definition mapping keyed by qualified key.

        The mapping is a ``MappingProxyType`` and must not be mutated.
        Keys are processor qualified keys; values are `ProcessorDefinition`
        objects.
        """
        return HeaderProcessorRegistry.as_mapping_by_qualified_key()

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
    def is_supported(local_key: str) -> bool:
        """Return True if a processor is registered for the given file type local_key.

        Args:
            local_key: File type identifier to query.

        Returns:
            ``True`` if the file type has a registered processor; otherwise ``False``.
        """
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(local_key)
        if ft_obj is None:
            return False
        return BindingRegistry.is_bound(ft_obj.qualified_key)

    @staticmethod
    def bound_filetype_names() -> tuple[str, ...]:
        """Return file type names that currently have a registered processor."""
        return BindingRegistry.bound_filetype_names()

    @staticmethod
    def unsupported_filetype_names() -> tuple[str, ...]:
        """Return recognized file type names that currently lack a processor."""
        return BindingRegistry.unbound_filetype_names()

    @staticmethod
    def register_filetype(
        ft_obj: FileType,
        *,
        processor_class: type[HeaderProcessor] | None = None,
    ) -> None:
        """Register a file type and optionally bind a processor class (advanced).

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
        """Unregister a file type by local_key (advanced)."""
        return FileTypeRegistry.unregister(local_key)

    @staticmethod
    def register_processor(
        *,
        file_type_id: str,
        processor_class: type[HeaderProcessor],
    ) -> None:
        """Register a header processor class under a file type identifier (advanced).

        Prefer `try_register_processor()` if you want a boolean status instead of
        exceptions for unknown, ambiguous, or duplicate registrations.

        Passthrough to
        [`HeaderProcessorRegistry.register`][topmark.registry.processors.HeaderProcessorRegistry.register].

        Args:
            file_type_id: File type identifier that the processor should be registered
                under. Both ``"local_key"`` and ``"namespace:local_key"`` forms are
                accepted.
            processor_class: Concrete `HeaderProcessor` class to register and
                bind to the registered file type.

        Raises:
            AmbiguousFileTypeIdentifierError: If an unqualified `file_type_id`
                matches multiple file types.
            InvalidRegistryIdentityError: If `file_type_id` is malformed.
            UnknownFileTypeError: If `file_type_id` does not resolve to a
                registered file type.
            DuplicateProcessorRegistrationError: If the effective registry already contains a
                processor for the same qualified key.
            TypeError: If processor_class is not a valid HeaderProcessor subclass or if its identity
                is malformed.
            ReservedNamespaceError: If the reserved built-in topmark namespace is used by an
                ineligible external processor class.
        """
        try:
            # Propagate ambiguity explicitly so the public facade documents it accurately.
            ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        except (AmbiguousFileTypeIdentifierError, InvalidRegistryIdentityError):  # noqa: TRY203
            raise

        if ft_obj is None:
            # Keep the facade strict: callers asked to register against a specific
            # file type identifier; silently ignoring mistakes would be surprising.
            raise UnknownFileTypeError(file_type=file_type_id)

        proc_def: ProcessorDefinition | None = None
        try:
            proc_def = HeaderProcessorRegistry.register(
                processor_class=processor_class,
            )
            BindingRegistry.bind(
                filetype_qualified_key=ft_obj.qualified_key,
                processor_qualified_key=proc_def.qualified_key,
            )
        except (  # noqa: TRY203
            DuplicateProcessorRegistrationError,
            ReservedNamespaceError,
            TypeError,
        ):
            raise

        return None

    @staticmethod
    def try_register_processor(
        file_type_id: str,
        processor_class: type[HeaderProcessor],
    ) -> bool:
        """Try to register a header processor for a file type identifier.

        This is a lenient variant of `register_processor()` intended for callers
        that want a boolean success/failure signal rather than an exception.

        Behavior:
            - Returns ``False`` if the file type identifier does not resolve.
            - Returns ``False`` if an unqualified identifier resolves ambiguously.
            - Returns ``False`` if a processor is already registered for the
              resolved file type.
            - Returns ``True`` if the registration succeeds.

        Notes:
            This method is conservative and avoids raising for common caller
            mistakes. It still delegates to the underlying registry for the
            actual mutation.

        Args:
            file_type_id: File type identifier that the processor should be registered
                under. Both ``"local_key"`` and ``"namespace:local_key"`` forms are
                accepted.
            processor_class: Concrete `HeaderProcessor` class to instantiate and
                bind.

        Returns:
            `True` if the registration succeeds, `False` otherwise.
        """
        try:
            ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        except (AmbiguousFileTypeIdentifierError, InvalidRegistryIdentityError):
            return False

        if ft_obj is None:
            return False

        if BindingRegistry.is_bound(ft_obj.qualified_key):
            return False

        proc_def: ProcessorDefinition | None = None
        try:
            proc_def = HeaderProcessorRegistry.register(
                processor_class=processor_class,
            )
            BindingRegistry.bind(
                filetype_qualified_key=ft_obj.qualified_key,
                processor_qualified_key=proc_def.qualified_key,
            )
        except (
            DuplicateProcessorRegistrationError,
            ReservedNamespaceError,
            TypeError,
            RuntimeError,
        ):
            return False
        except (
            ProcessorBindingError,
            UnknownFileTypeError,
        ):
            # Roll-back
            if proc_def:
                HeaderProcessorRegistry.unregister_by_qualified_key(proc_def.qualified_key)
            return False

        return True

    @staticmethod
    def unregister_processor(local_key: str) -> bool:
        """Unregister a header processor by local_key (advanced)."""
        ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(local_key)
        if ft_obj is None:
            return False

        processor_qualified_key: str | None = BindingRegistry.get_processor_key_for_filetype(
            ft_obj.qualified_key,
        )
        if processor_qualified_key is None:
            return False

        BindingRegistry.unbind(ft_obj.qualified_key)
        return HeaderProcessorRegistry.unregister_by_qualified_key(processor_qualified_key)
