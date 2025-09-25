# topmark:header:start
#
#   project      : TopMark
#   file         : processors.py
#   file_relpath : src/topmark/registry/processors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public header processor registry (advanced).

Exposes read-only views and optional mutation helpers for registered header
processors. Most users should prefer the stable facade
[`topmark.registry.Registry`][topmark.registry.Registry]. This module is intended
for plugins and tests.

Notes:
    * Public views (`as_mapping()`, `names()`, `get()`) are sourced from a **composed**
      registry (base + local overrides − removals) and exposed as `MappingProxyType`.
    * `register()` / `unregister()` apply **overlay-only** changes; they do not mutate
      the base processor mapping registered during import/decorator discovery.
    * When registering a processor, the target `FileType` is resolved from the composed
      file type view to ensure overlay-added types can be bound.
    * When the environment variable ``TOPMARK_VALIDATE`` is set to a truthy value
      (``1``, ``true``, ``yes``), lightweight developer validations will run on the
      composed processor mapping (see `_dev_validate_processors`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Iterator, Mapping

from topmark.filetypes.base import FileType
from topmark.filetypes.instances import get_file_type_registry
from topmark.pipeline.processors.base import NO_LINE_ANCHOR
from topmark.pipeline.processors.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


_validation_done: bool = False
_VALIDATION_ENV: Final[str] = "TOPMARK_VALIDATE"


def _dev_validate_processors(proc_map: Mapping[str, "HeaderProcessor"]) -> None:
    """Run lightweight developer validations when TOPMARK_VALIDATE=1.

    Checks:
        * Every registered processor key matches an existing FileType name.
        * XML-like processors (instances of XmlHeaderProcessor) report
          NO_LINE_ANCHOR for their line-based index.

    This function is a no-op unless the environment variable TOPMARK_VALIDATE
    is set to a truthy value ("1", "true", "yes"). It is executed at most once
    per process.
    """
    global _validation_done
    if _validation_done:
        return
    if os.getenv(_VALIDATION_ENV, "").lower() not in {"1", "true", "yes"}:
        return

    ft_reg: dict[str, FileType] = get_file_type_registry()

    # 1) All processors refer to existing file types
    missing: list[str] = [name for name in proc_map.keys() if name not in ft_reg]
    if missing:
        raise RuntimeError(f"Processors registered for unknown file types: {missing!r}")

    # 2) Xml-like processors use NO_LINE_ANCHOR for line-based index
    for name, proc in proc_map.items():
        if isinstance(proc, XmlHeaderProcessor):
            if proc.get_header_insertion_index(["<root/>"]) != NO_LINE_ANCHOR:
                raise RuntimeError(
                    "XmlHeaderProcessor must return NO_LINE_ANCHOR from "
                    "get_header_insertion_index(); offending type: "
                    f"{name!r}"
                )

    _validation_done = True


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
    _overrides: dict[str, "HeaderProcessor"] = {}
    _removals: set[str] = set()

    @classmethod
    def _compose(cls) -> dict[str, "HeaderProcessor"]:
        """Compose base processor registry with local overrides/removals."""
        from topmark.filetypes.registry import get_header_processor_registry as _get
        from topmark.pipeline.processors import register_all_processors

        register_all_processors()
        base: dict[str, HeaderProcessor] = dict(_get())
        base.update(cls._overrides)
        for name in cls._removals:
            base.pop(name, None)
        _dev_validate_processors(base)
        return base

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return all registered header processor names (sorted).

        Returns:
            tuple[str, ...]: Sorted processor names.
        """
        with cls._lock:
            return tuple(sorted(cls._compose().keys()))

    @classmethod
    def is_registered(cls, filetype_name: str) -> bool:
        """Return True if a processor is registered for the given file type name."""
        with cls._lock:
            return filetype_name in cls._compose()

    @classmethod
    def get(cls, name: str) -> HeaderProcessor | None:
        """Return a header processor by name.

        Args:
            name (str): Registered processor name.

        Returns:
            HeaderProcessor | None: The processor if found, else None.
        """
        with cls._lock:
            return cls._compose().get(name)

    @classmethod
    def as_mapping(cls) -> Mapping[str, HeaderProcessor]:
        """Return a read-only mapping of header processors.

        Returns:
            Mapping[str, HeaderProcessor]: Name -> HeaderProcessor mapping.

        Notes:
            The returned mapping is a `MappingProxyType` and must not be mutated.
        """
        with cls._lock:
            return MappingProxyType(cls._compose())

    @classmethod
    def iter_meta(cls) -> Iterator[ProcessorMeta]:
        """Iterate over stable metadata for registered processors.

        Yields:
            ProcessorMeta: Serializable metadata about each processor.
        """
        with cls._lock:
            for name, proc in cls._compose().items():
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
            name (str): File type name under which the processor appears in the registry.
            processor_class (type[HeaderProcessor]): A `HeaderProcessor` class. It will be
                instantiated with no arguments and bound to the file type.

        Raises:
            ValueError: If the file type name is unknown or already registered.

        Notes:
            - This mutates global state. Prefer temporary usage in tests with try/finally.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            # Resolve FileType from the composed registry (includes local overrides).
            from topmark.registry.filetypes import FileTypeRegistry as _FTReg

            ft_obj: FileType | None = _FTReg.get(name)
            if ft_obj is None:
                raise ValueError(f"Unknown file type: {name}")

            # Check composed view to avoid dupes
            if name in cls._compose():
                raise ValueError(f"File type '{name}' already has a registered processor.")

            # Instantiate if a class is provided
            proc_obj = processor_class()

            # Bind the processor to the FileType (mirror decorator behavior).
            proc_obj.file_type = ft_obj

            cls._overrides[name] = proc_obj

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a header processor by name.

        Args:
            name (str): Registered processor name.

        Returns:
            bool: True if removed, else False.

        Notes:
            - This mutates global registry state.
            - Thread safe via RLock; process-global state; do not mutate in long-lived
              multi-tenant processes.
        """
        with cls._lock:
            existed = False
            if name in cls._overrides:
                cls._overrides.pop(name, None)
                existed = True
            if name in cls._compose():
                cls._removals.add(name)
                existed = True
            return existed
