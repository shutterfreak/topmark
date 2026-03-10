# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/registry/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public registries for TopMark file types and header processors.

This module exposes structured, read-only oriented registries plus optional
mutation hooks. It is part of the public API and provides stable, serializable
metadata views without exposing internal implementation details.

The [`topmark.registry.registry.Registry`][] facade is the **stable public surface**
for read-only operations; the concrete registries remain available for advanced scenarios
and tests but are not part of the semver stability promise.

A FileType can be recognized (present in [`topmark.registry.filetypes.FileTypeRegistry`][])
but unsupported (no processor registered).

Typical usage:
    ```python
    from topmark.registry.filetypes import FileTypeRegistry, HeaderProcessorRegistry

    # Read-only introspection
    names = FileTypeRegistry.names()
    ft_map = FileTypeRegistry.as_mapping()  # read-only mapping proxy
    for meta in FileTypeRegistry.iter_meta():
        print(meta.name, meta.extensions)

    # Optional mutation (global state):
    # ALWAYS clean up after registering temporary entries.
    FileTypeRegistry.register(my_ft)
    try:
        ...
    finally:
        FileTypeRegistry.unregister(my_ft.name)
    ```

Warning:
    Mutations operate on global registries shared across the process. Use them
    sparingly in production; in tests, wrap them in ``try``/``finally``
    or a dedicated context manager to ensure cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import UnknownFileTypeError
from topmark.filetypes.model import FileType
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import FileTypeMeta
    from topmark.registry.types import ProcessorMeta


@dataclass(frozen=True)
class Binding:
    """Joined view of a file type and its (optional) processor.

    Attributes:
        filetype: Serializable metadata for the file type.
        processor: Serializable metadata for the bound processor,
            or ``None`` if the file type is recognized but currently unsupported.
    """

    filetype: FileTypeMeta
    processor: ProcessorMeta | None  # None => recognized but unsupported


def iter_bindings() -> Iterator[Binding]:
    """Iterate joined bindings of file types and processors.

    Yields:
        Binding: A pair containing file type metadata and the optionally
        bound processor metadata (``None`` for unsupported types).
    """
    proc: dict[str, ProcessorMeta] = {m.name: m for m in HeaderProcessorRegistry.iter_meta()}
    for ft in FileTypeRegistry.iter_meta():
        yield Binding(filetype=ft, processor=proc.get(ft.name))


class Registry:
    """Stable facade for read-only registry operations.

    It holds no state and composes the underlying registries into an effective, read-only view;
    all real mutations occur in the concrete registries it delegates to.
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
        """Return a **read-only** mapping of registered file types.

        The mapping is a ``MappingProxyType`` (mutations are not allowed).
        Keys are file type names; values are concrete FileType instances.
        """
        return FileTypeRegistry.as_mapping()

    @staticmethod
    def processors() -> Mapping[str, HeaderProcessor]:
        """Return a **read-only** mapping of registered header processors.

        The mapping is a ``MappingProxyType`` (mutations are not allowed).
        Keys are file type names; values are bound HeaderProcessor instances.
        """
        return HeaderProcessorRegistry.as_mapping()

    @staticmethod
    def is_supported(name: str) -> bool:
        """Return True if a processor is registered for the given file type name.

        Args:
            name: File type identifier to query.

        Returns:
            ``True`` if the file type has a registered processor; otherwise ``False``.
        """
        return HeaderProcessorRegistry.is_registered(name)

    @staticmethod
    def supported_filetype_names() -> tuple[str, ...]:
        """Return file type names that currently have a registered processor."""
        ft_names: set[str] = set(FileTypeRegistry.as_mapping().keys())
        proc_names: set[str] = set(HeaderProcessorRegistry.as_mapping().keys())
        return tuple(sorted(ft_names & proc_names))

    @staticmethod
    def unsupported_filetype_names() -> tuple[str, ...]:
        """Return recognized file type names that currently lack a processor."""
        ft_names: set[str] = set(FileTypeRegistry.as_mapping().keys())
        proc_names: set[str] = set(HeaderProcessorRegistry.as_mapping().keys())
        return tuple(sorted(ft_names - proc_names))

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
            processor_class: Optional `HeaderProcessor` class to instantiate and
                bind to the registered file type.

        Notes:
            This mutates global overlay state. Prefer temporary usage in tests or
            controlled initialization code, with explicit cleanup when needed.
        """
        FileTypeRegistry.register(ft_obj)
        if processor_class is not None:
            HeaderProcessorRegistry.register(
                file_type=ft_obj,
                processor_class=processor_class,
            )
        return None

    @staticmethod
    def unregister_filetype(name: str) -> bool:
        """Unregister a file type by name (advanced)."""
        return FileTypeRegistry.unregister(name)

    @staticmethod
    def register_processor(
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
                under. Both ``"name"`` and ``"namespace:name"`` forms are
                accepted.
            processor_class: Concrete `HeaderProcessor` class to instantiate and
                bind.

        Raises:
            UnknownFileTypeError: If `file_type_id` does not resolve to a registered file type.
            AmbiguousFileTypeIdentifierError: If an unqualified `file_type_id` matches
                multiple file types.
        """
        try:
            # Propagate ambiguity explicitly so the public facade documents it accurately.
            ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        except AmbiguousFileTypeIdentifierError:  # noqa: TRY203
            raise

        if ft_obj is None:
            # Keep the facade strict: callers asked to register against a specific
            # file type identifier; silently ignoring mistakes would be surprising.
            raise UnknownFileTypeError(file_type=file_type_id)

        HeaderProcessorRegistry.register(
            file_type=ft_obj,
            processor_class=processor_class,
        )
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
                under. Both ``"name"`` and ``"namespace:name"`` forms are
                accepted.
            processor_class: Concrete `HeaderProcessor` class to instantiate and
                bind.

        Returns:
            `True` if the registration succeeds, `False` otherwise.
        """
        try:
            ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        except AmbiguousFileTypeIdentifierError:
            return False

        if ft_obj is None:
            return False

        # The processor registry is keyed by file type *name* (unqualified) today.
        if HeaderProcessorRegistry.is_registered(ft_obj.name):
            return False

        HeaderProcessorRegistry.register(
            file_type=ft_obj,
            processor_class=processor_class,
        )
        return True

    @staticmethod
    def unregister_processor(name: str) -> bool:
        """Unregister a header processor by name (advanced)."""
        return HeaderProcessorRegistry.unregister(name)
