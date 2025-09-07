# topmark:header:start
#
#   file         : registry.py
#   file_relpath : src/topmark/registry/registry.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Public registries for TopMark file types and header processors.

This module exposes structured, read-only oriented registries plus optional
mutation hooks. It is part of the public API and provides stable, serializable
metadata views without exposing internal implementation details.

The :class:`Registry` facade is the **stable public surface** for read-only
operations; the concrete registries remain available for advanced scenarios
and tests but are not part of the semver stability promise.

A FileType can be recognized (present in FileTypeRegistry) but unsupported
(no processor registered).

Typical usage:
    ```python
    from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

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
    sparingly in production; in tests, wrap them in try/finally or a dedicated
    context manager to ensure cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, Mapping

from topmark.registry.filetypes import FileTypeMeta, FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry, ProcessorMeta

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


@dataclass(frozen=True)
class Binding:
    """Joined view of a file type and its (optional) processor.

    Attributes:
        filetype: Serializable metadata for the file type.
        processor: Serializable metadata for the bound processor, or ``None``
            if the file type is recognized but currently unsupported.
    """

    filetype: FileTypeMeta
    processor: ProcessorMeta | None  # None => recognized but unsupported


def iter_bindings() -> Iterator[Binding]:
    """Iterate joined bindings of file types and processors.

    Yields:
        Binding: A pair containing file type metadata and the optionally
        bound processor metadata (``None`` for unsupported types).
    """
    proc = {m.name: m for m in HeaderProcessorRegistry.iter_meta()}
    for ft in FileTypeRegistry.iter_meta():
        yield Binding(filetype=ft, processor=proc.get(ft.name))


class Registry:
    """Stable facade for read-only registry operations.

    It holds no state and composes the underlying registries; all real
    mutations occur in the concrete registries it delegates to.
    """

    @staticmethod
    def bindings() -> tuple[Binding, ...]:
        """Return joined view of file types and their processor bindings.

        Each element contains the file type metadata and the optionally bound
        processor metadata (``None`` means recognized but unsupported).

        Returns:
            tuple[Binding, ...]: Immutable sequence of bindings.
        """
        return tuple(iter_bindings())

    @staticmethod
    def filetypes() -> Mapping[str, object]:
        """Return a **read-only** mapping of registered file types.

        The mapping is a ``MappingProxyType`` (mutations are not allowed).
        Keys are file type names; values are concrete FileType instances.
        """
        return FileTypeRegistry.as_mapping()

    @staticmethod
    def processors() -> Mapping[str, object]:
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
            bool: ``True`` if the file type has a registered processor; otherwise ``False``.
        """
        return HeaderProcessorRegistry.is_registered(name)

    @staticmethod
    def register_filetype(
        ft_obj: "FileType", *, processor: type["HeaderProcessor"] | None = None
    ) -> None:
        """Register a file type and optionally bind a processor (advanced).

        This is a convenience passthrough to :class:`FileTypeRegistry.register`.
        Mutates global state; prefer using in tests or controlled plugin init.
        """
        return FileTypeRegistry.register(ft_obj, processor=processor)

    @staticmethod
    def unregister_filetype(name: str) -> bool:
        """Unregister a file type by name (advanced)."""
        return FileTypeRegistry.unregister(name)

    @staticmethod
    def register_processor(name: str, processor_class: type["HeaderProcessor"]) -> None:
        """Register a header processor under a file type name (advanced).

        Passthrough to :class:`HeaderProcessorRegistry.register`.
        """
        return HeaderProcessorRegistry.register(name, processor_class)

    @staticmethod
    def unregister_processor(name: str) -> bool:
        """Unregister a header processor by name (advanced)."""
        return HeaderProcessorRegistry.unregister(name)

    @staticmethod
    def ensure_processors_registered() -> None:
        """Ensure all built-in processors are registered (idempotent).

        Typically unnecessary because read methods call into the underlying
        registry which self-registers. Exposed for callers that want to
        pre-warm the registry explicitly.
        """
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
