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

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition


def test_supported_vs_unsupported_partition() -> None:
    """FileType may exist without processor; supported/unsupported reflect that."""
    ft_name = "x_demo"
    ft: FileType = make_file_type(local_key=ft_name)

    proc_cls: type[HeaderProcessor] = registry_processor_class()

    try:
        # Register FT only (recognized, unsupported)
        FileTypeRegistry.register(ft)
        assert ft_name in FileTypeRegistry.names()
        assert ft_name in Registry.unsupported_filetype_names()
        assert ft_name not in Registry.bound_filetype_names()
        assert BindingRegistry.get_processor_key_for_filetype(ft.qualified_key) is None

        # Now register via the public facade -> becomes supported
        Registry.register_processor(
            file_type_id=ft_name,
            processor_class=proc_cls,
        )

        assert ft_name in Registry.bound_filetype_names()
        assert ft_name not in Registry.unsupported_filetype_names()

        processor_qualified_key: str | None = BindingRegistry.get_processor_key_for_filetype(
            ft.qualified_key,
        )
        assert processor_qualified_key is not None

        # The registry stores a processor definition; runtime resolution binds it to the FT object.
        proc_def: ProcessorDefinition | None = HeaderProcessorRegistry.get_by_qualified_key(
            processor_qualified_key,
        )
        assert proc_def is not None
        assert proc_def.local_key == proc_cls.local_key

        proc_obj: HeaderProcessor | None = Registry.resolve_processor(ft_name)
        assert proc_obj is not None
        assert proc_obj.file_type is not None
        assert proc_obj.file_type.local_key == ft_name
    finally:
        Registry.unregister_processor(ft_name)
        FileTypeRegistry.unregister(ft_name)


def test_register_processor_fails_for_unknown_filetype() -> None:
    """Reject registering a processor for a non-existent file type."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()

    with pytest.raises(UnknownFileTypeError):
        Registry.register_processor(
            file_type_id="nonexistent_ft",
            processor_class=proc_cls,
        )


def test_supported_unsupported_partition_coherent() -> None:
    """Partition coherence (disjoint & covers all names)."""
    all_names: set[str] = set(FileTypeRegistry.names())
    supp: set[str] = set(Registry.bound_filetype_names())
    unsupp: set[str] = set(Registry.unsupported_filetype_names())
    assert supp.isdisjoint(unsupp)
    assert supp.union(unsupp) == all_names
