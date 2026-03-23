# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_linkage.py
#   file_relpath : tests/registry/test_registry_linkage.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests registry linkage between file types and processors.

This module verifies how `FileTypeRegistry` and `HeaderProcessorRegistry`
interact:

- File types can exist without a registered header processor and are then
  considered unsupported.
- Registering a corresponding processor transitions a file type to supported and
  binds the processor to the file type object.
- Registering a processor for an unknown file type raises ``UnknownFileTypeError``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import make_file_type
from tests.conftest import registry_processor_class
from topmark.core.errors import UnknownFileTypeError
from topmark.processors.base import HeaderProcessor
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry
from topmark.registry.types import ProcessorDefinition

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition


def test_supported_vs_unsupported_partition() -> None:
    """FileType may exist without processor; supported/unsupported reflect that."""
    ft_name = "x_demo"
    ft: FileType = make_file_type(local_key=ft_name)

    proc_cls: type[HeaderProcessor] = registry_processor_class()
    processor_qualified_key: str | None = None

    try:
        # Register FT only (recognized, unsupported)
        FileTypeRegistry.register(ft)
        assert ft_name in FileTypeRegistry.names()
        assert ft_name in Registry.unbound_filetype_local_keys()
        assert ft_name not in Registry.bound_filetype_local_keys()
        assert BindingRegistry.get_processor_key_for_filetype(ft.qualified_key) is None

        # Register the processor definition, then bind it via the public facade.
        proc_def: ProcessorDefinition | None = HeaderProcessorRegistry.register(
            processor_class=proc_cls,
        )
        Registry.bind_processor(
            file_type_id=ft_name,
            processor_qualified_key=proc_def.qualified_key,
        )

        assert ft_name in Registry.bound_filetype_local_keys()
        assert ft_name not in Registry.unbound_filetype_local_keys()

        processor_qualified_key = BindingRegistry.get_processor_key_for_filetype(
            ft.qualified_key,
        )
        assert processor_qualified_key is not None

        # The registry stores a processor definition; runtime resolution binds it to the FT object.
        proc_def = HeaderProcessorRegistry.get_by_qualified_key(
            processor_qualified_key,
        )
        assert proc_def is not None
        assert proc_def.local_key == proc_cls.local_key

        proc_obj: HeaderProcessor | None = Registry.resolve_processor(ft_name)
        assert proc_obj is not None
        assert proc_obj.file_type is not None
        assert proc_obj.file_type.local_key == ft_name
    finally:
        Registry.unbind_filetype_by_local_key(ft_name)
        if processor_qualified_key is not None:
            Registry.unregister_processor_by_qualified_key(
                processor_qualified_key,
                remove_bindings=False,
            )
        FileTypeRegistry.unregister(ft_name)


def test_register_processor_fails_for_unknown_filetype() -> None:
    """Reject registering a processor for a non-existent file type."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=proc_cls,
    )
    try:
        with pytest.raises(UnknownFileTypeError):
            Registry.bind_processor(
                file_type_id="nonexistent_ft",
                processor_qualified_key=proc_def.qualified_key,
            )
    finally:
        HeaderProcessorRegistry.unregister_by_qualified_key(proc_def.qualified_key)


def test_supported_unsupported_partition_coherent() -> None:
    """Partition coherence (disjoint & covers all names)."""
    all_names: set[str] = set(FileTypeRegistry.names())
    supp: set[str] = set(Registry.bound_filetype_local_keys())
    unsupp: set[str] = set(Registry.unbound_filetype_local_keys())
    assert supp.isdisjoint(unsupp)
    assert supp.union(unsupp) == all_names
