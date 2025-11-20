# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_public_api.py
#   file_relpath : tests/api/test_registry_public_api.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# tests/api/test_registry_public_api.py
"""Tests for the public registry classes (FileTypeRegistry, HeaderProcessorRegistry).

These tests verify read-only views, metadata iteration, and the optional
mutation hooks (register/unregister). Mutations operate on global registries,
so every test that registers a temporary entry must ensure cleanup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.api.conftest import stub_ft, stub_proc_cls
from topmark.filetypes.base import FileType
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor

# ---------- helpers (duck-typed stubs) ----------


@pytest.mark.parametrize("dummy_name", ["dummy_ft", "dummy_ft_2"])
def test_filetype_register_unregister_roundtrip(dummy_name: str) -> None:
    """Register a stub file type and then unregister it."""
    ft: FileType = stub_ft(dummy_name, description="Stub FT")

    try:
        # Register
        FileTypeRegistry.register(ft)
        # Visible via names() and as_mapping()
        assert dummy_name in FileTypeRegistry.names()
        assert dummy_name in FileTypeRegistry.as_mapping().keys()
        # Visible via iter_meta()
        names: set[str] = {m.name for m in FileTypeRegistry.iter_meta()}
        assert dummy_name in names
    finally:
        # Cleanup
        assert FileTypeRegistry.unregister(dummy_name) is True
        assert dummy_name not in FileTypeRegistry.names()


def test_filetype_register_duplicate_raises() -> None:
    """Registering the same file type name twice should raise ValueError."""
    name = "dup_ft"
    ft1: FileType = stub_ft(name)
    ft2: FileType = stub_ft(name)
    try:
        FileTypeRegistry.register(ft1)
        with pytest.raises(ValueError):
            FileTypeRegistry.register(ft2)
    finally:
        FileTypeRegistry.unregister(name)


@pytest.mark.parametrize("proc_name", ["dummy_proc"])
def test_processor_register_unregister_roundtrip(proc_name: str) -> None:
    """Register a stub processor under a new name and then unregister it."""
    ft: FileType = stub_ft(proc_name)
    FileTypeRegistry.register(ft)

    proc_cls: type[HeaderProcessor] = stub_proc_cls()

    try:
        HeaderProcessorRegistry.register(proc_name, proc_cls)
        assert proc_name in HeaderProcessorRegistry.names()
        assert proc_name in HeaderProcessorRegistry.as_mapping().keys()
        # Iter meta should include it
        names: set[str] = {m.name for m in HeaderProcessorRegistry.iter_meta()}
        assert proc_name in names
    finally:
        assert HeaderProcessorRegistry.unregister(proc_name) is True
        assert proc_name not in HeaderProcessorRegistry.names()
        FileTypeRegistry.unregister(proc_name)


def test_processor_register_duplicate_raises() -> None:
    """Registering a processor under an existing name should raise ValueError."""
    name = "dup_proc"

    ft: FileType = stub_ft(name)
    FileTypeRegistry.register(ft)

    proc_cls: type[HeaderProcessor] = stub_proc_cls()

    try:
        HeaderProcessorRegistry.register(name, proc_cls)
        with pytest.raises(ValueError):
            HeaderProcessorRegistry.register(name, proc_cls)
    finally:
        HeaderProcessorRegistry.unregister(name)
        FileTypeRegistry.unregister(name)


def test_replace_processor_requires_unregister() -> None:
    """Verifies you can’t register a second processor without first unregistering."""
    name = "replace_proc_demo"

    FileTypeRegistry.register(stub_ft(name))
    try:
        cls1: type[HeaderProcessor] = stub_proc_cls()
        cls2: type[HeaderProcessor] = stub_proc_cls()
        HeaderProcessorRegistry.register(name, cls1)
        import pytest

        with pytest.raises(ValueError):
            HeaderProcessorRegistry.register(name, cls2)
        assert HeaderProcessorRegistry.unregister(name) is True
        HeaderProcessorRegistry.register(name, cls2)  # now OK
    finally:
        HeaderProcessorRegistry.unregister(name)
        FileTypeRegistry.unregister(name)


def test_filetype_as_mapping_is_readonly() -> None:
    """Verify that as_mapping() is read-only."""
    import types

    m: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    assert isinstance(m, types.MappingProxyType)
