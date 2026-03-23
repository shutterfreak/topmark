# topmark:header:start
#
#   project      : TopMark
#   file         : bindings.py
#   file_relpath : src/topmark/registry/bindings.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Advanced registry for file type to processor bindings.

This module owns the effective relationship layer between registered file
types and registered processor definitions. It is intentionally separate from
both the file type and processor registries so identity and relationships can
be modeled independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING

from topmark.core.errors import ProcessorBindingError
from topmark.core.errors import UnknownFileTypeError
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.registry.types import FileTypeMeta
    from topmark.registry.types import ProcessorDefinition
    from topmark.registry.types import ProcessorMeta


@dataclass(frozen=True)
class Binding:
    """Joined metadata view of one file type and its optionally bound processor.

    Attributes:
        filetype: Serializable metadata for the file type.
        processor: Serializable metadata for the bound processor, or ``None``
            if the file type is currently unbound.
    """

    filetype: FileTypeMeta
    processor: ProcessorMeta | None


class BindingRegistry:
    """Composed registry of effective file type to processor bindings.

    The base binding view is derived from the explicit built-in processor
    bindings declared in `topmark.processors.instances`. Local overrides and
    removals are then layered on top.
    """

    _lock: RLock = RLock()
    _overrides: dict[str, str] = {}  # filetype_qk -> processor_qk
    _removals: set[str] = set()

    # --- Internal composition ---

    @classmethod
    def _compose(cls) -> dict[str, str]:
        """Compose the effective binding registry and validate referenced identities.

        Returns:
            Mapping of file type qualified key to processor qualified key.

        Raises:
            ProcessorBindingError: If a composed binding references an unknown
                file type or processor definition.
        """
        from topmark.processors.instances import get_base_processor_binding_registry

        base: dict[str, str] = dict(get_base_processor_binding_registry())

        for filetype_qualified_key in cls._removals:
            base.pop(filetype_qualified_key, None)

        base.update(cls._overrides)

        for filetype_qualified_key, processor_qualified_key in base.items():
            file_type: FileType | None = FileTypeRegistry.get_by_qualified_key(
                filetype_qualified_key,
            )
            if file_type is None:
                raise ProcessorBindingError(
                    message=(
                        "Binding registry contains an entry for unknown file type "
                        f"'{filetype_qualified_key}'."
                    ),
                    file_type=filetype_qualified_key,
                )

            processor: ProcessorDefinition | None = HeaderProcessorRegistry.get_by_qualified_key(
                processor_qualified_key,
            )
            if processor is None:
                raise ProcessorBindingError(
                    message=(
                        "Binding registry contains an entry for unknown processor "
                        f"'{processor_qualified_key}'."
                    ),
                    file_type=filetype_qualified_key,
                )

        return base

    @classmethod
    def as_mapping(cls) -> Mapping[str, str]:
        """Return a read-only mapping of effective file type to processor bindings.

        Returns:
            Mapping of file type qualified key to processor qualified key.
        """
        with cls._lock:
            composed: dict[str, str] = cls._compose()
            return MappingProxyType(composed)

    # --- Exact point lookups ---

    @classmethod
    def get_processor_key_for_filetype(cls, filetype_qualified_key: str) -> str | None:
        """Return the bound processor qualified key for a file type.

        Args:
            filetype_qualified_key: File type qualified key.

        Returns:
            The bound processor qualified key, or ``None`` if the file type is
            currently unbound.
        """
        with cls._lock:
            return cls._compose().get(filetype_qualified_key)

    @classmethod
    def get_filetype_keys_for_processor(cls, processor_qualified_key: str) -> tuple[str, ...]:
        """Return file type qualified keys currently bound to a processor.

        Args:
            processor_qualified_key: Processor qualified key.

        Returns:
            Sorted tuple of file type qualified keys currently bound to the
            processor.
        """
        with cls._lock:
            return tuple(
                sorted(
                    filetype_qk
                    for filetype_qk, processor_qk in cls._compose().items()
                    if processor_qk == processor_qualified_key
                )
            )

    # --- Predicates ---

    @classmethod
    def is_bound(cls, filetype_qualified_key: str) -> bool:
        """Return whether a file type qualified key currently has a binding.

        Args:
            filetype_qualified_key: File type qualified key.

        Returns:
            ``True`` if the file type currently has a binding, else ``False``.
        """
        with cls._lock:
            return filetype_qualified_key in cls._compose()

    @classmethod
    def is_processor_bound(cls, processor_qualified_key: str) -> bool:
        """Return whether a processor qualified key is referenced by any binding.

        Args:
            processor_qualified_key: Processor qualified key.

        Returns:
            ``True`` if at least one file type is currently bound to the
            processor, else ``False``.
        """
        with cls._lock:
            return any(
                processor_qk == processor_qualified_key for processor_qk in cls._compose().values()
            )

    # --- Mutations ---

    @classmethod
    def bind(cls, *, filetype_qualified_key: str, processor_qualified_key: str) -> None:
        """Bind a registered file type qualified key to a registered processor.

        Args:
            filetype_qualified_key: File type qualified key to bind.
            processor_qualified_key: Processor qualified key to bind to the file
                type.

        Raises:
            UnknownFileTypeError: If `filetype_qualified_key` does not resolve to
                a registered file type.
            ProcessorBindingError: If `processor_qualified_key` is unknown or if
                the file type is already bound.
        """
        with cls._lock:
            file_type: FileType | None = FileTypeRegistry.get_by_qualified_key(
                filetype_qualified_key,
            )
            if file_type is None:
                raise UnknownFileTypeError(file_type=filetype_qualified_key)

            processor: ProcessorDefinition | None = HeaderProcessorRegistry.get_by_qualified_key(
                processor_qualified_key,
            )
            if processor is None:
                raise ProcessorBindingError(
                    message=f"Unknown processor qualified key: {processor_qualified_key}",
                    file_type=filetype_qualified_key,
                )

            existing: str | None = cls._compose().get(filetype_qualified_key)
            if existing is not None:
                raise ProcessorBindingError(
                    message=(
                        f"File type '{filetype_qualified_key}' is already bound to "
                        f"processor '{existing}'."
                    ),
                    file_type=filetype_qualified_key,
                )

            cls._removals.discard(filetype_qualified_key)
            cls._overrides[filetype_qualified_key] = processor.qualified_key

    @classmethod
    def unbind(cls, filetype_qualified_key: str) -> bool:
        """Remove the effective binding for a file type qualified key.

        Args:
            filetype_qualified_key: File type qualified key whose binding should
                be removed.

        Returns:
            ``True`` if a binding existed in the effective view, else ``False``.
        """
        with cls._lock:
            existed: bool = (
                filetype_qualified_key in cls._overrides or filetype_qualified_key in cls._compose()
            )
            cls._overrides.pop(filetype_qualified_key, None)
            cls._removals.add(filetype_qualified_key)
            return existed

    @classmethod
    def unbind_processor(cls, processor_qualified_key: str) -> tuple[str, ...]:
        """Remove all bindings that currently reference a processor.

        Args:
            processor_qualified_key: Processor qualified key.

        Returns:
            Sorted tuple of file type qualified keys that were unbound.
        """
        with cls._lock:
            filetype_qks: tuple[str, ...] = tuple(
                sorted(
                    filetype_qk
                    for filetype_qk, processor_qk in cls._compose().items()
                    if processor_qk == processor_qualified_key
                )
            )
            for filetype_qk in filetype_qks:
                cls._overrides.pop(filetype_qk, None)
                cls._removals.add(filetype_qk)
            return filetype_qks

    # --- Iteration and reporting ---

    @classmethod
    def iter_bindings(cls) -> Iterator[Binding]:
        """Iterate the effective joined bindings of file types and processors.

        Yields:
            Binding: A pair containing file type metadata and the optionally
            bound processor metadata (``None`` for unbound types).
        """
        filetypes_by_qualified_key: dict[str, FileTypeMeta] = {
            meta.qualified_key: meta for meta in FileTypeRegistry.iter_meta()
        }
        processors_by_qualified_key: dict[str, ProcessorMeta] = {
            meta.qualified_key: meta for meta in HeaderProcessorRegistry.iter_meta()
        }

        for filetype_qualified_key, filetype_meta in sorted(filetypes_by_qualified_key.items()):
            processor_qualified_key: str | None = cls.get_processor_key_for_filetype(
                filetype_qualified_key,
            )
            yield Binding(
                filetype=filetype_meta,
                processor=(
                    processors_by_qualified_key.get(processor_qualified_key)
                    if processor_qualified_key is not None
                    else None
                ),
            )

    @classmethod
    def iter_meta(cls) -> Iterator[tuple[str, str]]:
        """Iterate over effective ``(filetype_qk, processor_qk)`` pairs.

        Yields:
            Tuples of ``(filetype_qualified_key, processor_qualified_key)`` in
            sorted order.
        """
        with cls._lock:
            yield from sorted(cls._compose().items())

    @classmethod
    def bound_filetype_local_keys(cls) -> tuple[str, ...]:
        """Return sorted local keys of file types that currently have a binding.

        Returns:
            Sorted tuple of file type local keys that are currently bound.
        """
        with cls._lock:
            return tuple(
                sorted(
                    ft.local_key
                    for ft in FileTypeRegistry.iter_meta()
                    if cls.is_bound(ft.qualified_key)
                )
            )

    @classmethod
    def unbound_filetype_local_keys(cls) -> tuple[str, ...]:
        """Return sorted local keys of recognized file types that currently lack a binding.

        Returns:
            Sorted tuple of file type local keys that are currently unbound.
        """
        with cls._lock:
            return tuple(
                sorted(
                    ft.local_key
                    for ft in FileTypeRegistry.iter_meta()
                    if not cls.is_bound(ft.qualified_key)
                )
            )
