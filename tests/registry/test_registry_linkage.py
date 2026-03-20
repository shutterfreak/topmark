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
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor


def test_supported_vs_unsupported_partition() -> None:
    """FileType may exist without processor; supported/unsupported reflect that."""
    ft_name = "x_demo"
    ft: FileType = make_file_type(name=ft_name)

    proc_cls: type[HeaderProcessor] = registry_processor_class()

    try:
        # Register FT only (recognized, unsupported)
        FileTypeRegistry.register(ft)
        assert ft_name in FileTypeRegistry.names()
        assert ft_name in Registry.unsupported_filetype_names()
        assert ft_name not in Registry.supported_filetype_names()
        assert not HeaderProcessorRegistry.is_registered(ft_name)

        # Now register a processor -> becomes supported
        HeaderProcessorRegistry.register(
            processor_class=proc_cls,
            file_type=ft,
        )

        assert HeaderProcessorRegistry.is_registered(ft_name)
        assert ft_name in Registry.supported_filetype_names()
        assert ft_name not in Registry.unsupported_filetype_names()

        # The processor should be bound to the FT object
        proc_obj: HeaderProcessor = HeaderProcessorRegistry.as_mapping()[ft_name]
        assert getattr(proc_obj, "file_type", None) is not None
        assert proc_obj.file_type is not None
        assert proc_obj.file_type.local_key == ft_name
    finally:
        HeaderProcessorRegistry.unregister(ft_name)
        FileTypeRegistry.unregister(ft_name)


def test_register_processor_fails_for_unknown_filetype() -> None:
    """Reject registering a processor for a non-existent file type."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()

    with pytest.raises(UnknownFileTypeError):
        Registry.register_processor("nonexistent_ft", proc_cls)


def test_supported_unsupported_partition_coherent() -> None:
    """Partition coherence (disjoint & covers all names)."""
    all_names: set[str] = set(FileTypeRegistry.names())
    supp: set[str] = set(Registry.supported_filetype_names())
    unsupp: set[str] = set(Registry.unsupported_filetype_names())
    assert supp.isdisjoint(unsupp)
    assert supp.union(unsupp) == all_names
