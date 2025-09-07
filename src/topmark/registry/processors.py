# topmark:header:start
#
#   file         : processors.py
#   file_relpath : src/topmark/registry/processors.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public header processor registry (advanced).

Exposes read-only views and optional mutation helpers for registered header
processors. Most users should prefer the stable facade
:class:`topmark.registry.Registry`. This module is intended for plugins and
tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Iterator, Mapping, MutableMapping

if TYPE_CHECKING:
    from topmark.pipeline.processors.base import HeaderProcessor


@dataclass(frozen=True)
class ProcessorMeta:
    """Stable, serializable metadata about a registered HeaderProcessor."""

    name: str
    description: str = ""
    line_prefix: str = ""
    line_suffix: str = ""
    block_prefix: str = ""
    block_suffix: str = ""


class HeaderProcessorRegistry:
    """Stable, read-only oriented view with optional mutation hooks.

    Notes:
        - Mutation hooks are intended for plugin authors and test scaffolding;
          most integrations should use metadata views only.
    """

    _lock = RLock()

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered header processor names (sorted).

        Returns:
            tuple[str, ...]: Sorted processor names.
        """
        from topmark.filetypes.registry import get_header_processor_registry as _get
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
        with cls._lock:
            return tuple(sorted(_get().keys()))

    @classmethod
    def is_registered(cls, filetype_name: str) -> bool:
        """Return True if a processor is registered for the given file type name."""
        from topmark.filetypes.registry import get_header_processor_registry as _get
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
        with cls._lock:
            return filetype_name in _get()

    @classmethod
    def get(cls, name: str) -> HeaderProcessor | None:
        """Return a header processor by name.

        Args:
            name: Registered processor name.

        Returns:
            HeaderProcessor | None: The processor if found, else None.
        """
        from topmark.filetypes.registry import get_header_processor_registry as _get
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
        with cls._lock:
            return _get().get(name)

    @classmethod
    def as_mapping(cls) -> Mapping[str, HeaderProcessor]:
        """Return a read-only mapping of header processors.

        Returns:
            Mapping[str, HeaderProcessor]: Name -> HeaderProcessor mapping.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be mutated.
        """
        from topmark.filetypes.registry import get_header_processor_registry as _get
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
        with cls._lock:
            return MappingProxyType(_get())

    @classmethod
    def iter_meta(cls) -> Iterator[ProcessorMeta]:
        """Iterate over stable metadata for registered processors.

        Yields:
            ProcessorMeta: Serializable metadata about each processor.
        """
        from topmark.filetypes.registry import get_header_processor_registry as _get
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
        with cls._lock:
            for name, proc in _get().items():
                yield ProcessorMeta(
                    name=name,
                    description=getattr(proc, "description", "") or "",
                    line_prefix=getattr(proc, "line_prefix", "") or "",
                    line_suffix=getattr(proc, "line_suffix", "") or "",
                    block_prefix=getattr(proc, "block_prefix", "") or "",
                    block_suffix=getattr(proc, "block_suffix", "") or "",
                )

    # Optional: mutation
    @classmethod
    def register(
        cls,
        name: str,
        processor_class: type[HeaderProcessor],
    ) -> None:
        """Register a header processor under a file type name.

        Args:
            name: File type name under which the processor appears in the registry.
            processor_class: A `HeaderProcessor` class. It will be instantiated
                with no arguments and bound to the file type.

        Raises:
            ValueError: If the file type name is unknown or already registered.

        Notes:
            - This mutates global state. Prefer temporary usage in tests with try/finally.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        from topmark.filetypes.instances import get_file_type_registry as _get_ft
        from topmark.filetypes.registry import get_header_processor_registry as _get

        with cls._lock:
            ft_reg = _get_ft()
            if name not in ft_reg:
                raise ValueError(f"Unknown file type: {name}")

            reg: MutableMapping[str, "HeaderProcessor"] = _get()
            if name in reg:
                raise ValueError(f"File type '{name}' already has a registered processor.")

            # Instantiate if a class is provided
            proc_obj = processor_class()

            # Bind the processor to the FileType (mirror decorator behavior).
            proc_obj.file_type = ft_reg[name]

            reg[name] = proc_obj

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a header processor by name.

        Args:
            name: Registered processor name.

        Returns:
            bool: True if removed, else False.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        from topmark.filetypes.registry import get_header_processor_registry as _get

        with cls._lock:
            reg: MutableMapping[str, HeaderProcessor] = _get()
            return reg.pop(name, None) is not None
