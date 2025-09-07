# topmark:header:start
#
#   file         : test_registry_linkage.py
#   file_relpath : tests/api/test_registry_linkage.py
#   project      : TopMark
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
- Registering a processor for an unknown file type raises ``ValueError``.
"""

from __future__ import annotations

import pytest

from tests.api.conftest import stub_ft, stub_proc_cls
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry


def test_supported_vs_unsupported_partition() -> None:
    """FileType may exist without processor; supported/unsupported reflect that."""
    ft_name = "x_demo"
    ft = stub_ft(ft_name)

    proc_cls = stub_proc_cls()

    try:
        # Register FT only (recognized, unsupported)
        FileTypeRegistry.register(ft)
        assert ft_name in FileTypeRegistry.names()
        assert ft_name in FileTypeRegistry.unsupported_names()
        assert ft_name not in FileTypeRegistry.supported_names()
        assert not HeaderProcessorRegistry.is_registered(ft_name)

        # Now register a processor -> becomes supported
        HeaderProcessorRegistry.register(ft_name, proc_cls)

        assert HeaderProcessorRegistry.is_registered(ft_name)
        assert ft_name in FileTypeRegistry.supported_names()
        assert ft_name not in FileTypeRegistry.unsupported_names()

        # The processor should be bound to the FT object
        proc_obj = HeaderProcessorRegistry.as_mapping()[ft_name]
        assert getattr(proc_obj, "file_type", None) is not None
        assert proc_obj.file_type is not None
        assert proc_obj.file_type.name == ft_name
    finally:
        HeaderProcessorRegistry.unregister(ft_name)
        FileTypeRegistry.unregister(ft_name)


def test_register_processor_fails_for_unknown_filetype() -> None:
    """Reject registering a processor for a non-existent file type."""
    proc_cls = stub_proc_cls()

    with pytest.raises(ValueError):
        HeaderProcessorRegistry.register("nonexistent_ft", proc_cls)


def test_supported_unsupported_partition_coherent() -> None:
    """Partition coherence (disjoint & covers all names)."""
    all_names = set(FileTypeRegistry.names())
    supp = set(FileTypeRegistry.supported_names())
    unsupp = set(FileTypeRegistry.unsupported_names())
    assert supp.isdisjoint(unsupp)
    assert supp.union(unsupp) == all_names
