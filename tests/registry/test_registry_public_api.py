# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_public_api.py
#   file_relpath : tests/registry/test_registry_public_api.py
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

from tests.helpers.registry import make_file_type
from tests.helpers.registry import registry_processor_class
from topmark.core.errors import DuplicateProcessorRegistrationError
from topmark.filetypes.model import FileType
from topmark.processors.base import HeaderProcessor
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition


# ---------- helpers (duck-typed stubs) ----------


@pytest.mark.parametrize("dummy_name", ["dummy_ft", "dummy_ft_2"])
def test_filetype_register_unregister_roundtrip(dummy_name: str) -> None:
    """Register a stub file type and then unregister it."""
    ft: FileType = make_file_type(
        local_key=dummy_name,
        description="Stub FT",
    )

    try:
        # Register
        FileTypeRegistry.register(ft)
        # Visible via names() and as_mapping()
        assert dummy_name in FileTypeRegistry.names()
        assert dummy_name in FileTypeRegistry.as_mapping_by_local_key()
        # Visible via iter_meta()
        names: set[str] = {m.local_key for m in FileTypeRegistry.iter_meta_by_local_key()}
        assert dummy_name in names
    finally:
        # Cleanup
        assert FileTypeRegistry.unregister_by_local_key(dummy_name) is True
        assert dummy_name not in FileTypeRegistry.names()


def test_filetype_register_duplicate_raises() -> None:
    """Registering the same file type name twice should raise ValueError."""
    name = "dup_ft"
    ft1: FileType = make_file_type(local_key=name)
    ft2: FileType = make_file_type(local_key=name)
    try:
        FileTypeRegistry.register(ft1)
        with pytest.raises(ValueError):
            FileTypeRegistry.register(ft2)
    finally:
        FileTypeRegistry.unregister_by_local_key(name)


@pytest.mark.parametrize("proc_name", ["dummy_proc"])
def test_processor_register_unregister_roundtrip(proc_name: str) -> None:
    """Register a stub processor definition and then unregister it by qualified key."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=proc_cls,
    )
    try:
        assert proc_def.qualified_key in HeaderProcessorRegistry.as_mapping()
        names: set[str] = {m.local_key for m in HeaderProcessorRegistry.iter_meta()}
        assert proc_def.local_key in names
    finally:
        assert HeaderProcessorRegistry.unregister(proc_def.qualified_key) is True
        assert proc_def.qualified_key not in HeaderProcessorRegistry.as_mapping()


def test_processor_register_duplicate_raises() -> None:
    """Registering the same processor qualified key twice should raise."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()
    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=proc_cls,
    )
    try:
        with pytest.raises(DuplicateProcessorRegistrationError):
            HeaderProcessorRegistry.register(
                processor_class=proc_cls,
            )
    finally:
        HeaderProcessorRegistry.unregister(proc_def.qualified_key)


def test_replace_processor_requires_unregister() -> None:
    """Verifies you can’t register the same processor twice without first unregistering it."""
    cls1: type[HeaderProcessor] = registry_processor_class()
    proc_def1: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=cls1,
    )
    try:
        with pytest.raises(DuplicateProcessorRegistrationError):
            HeaderProcessorRegistry.register(
                processor_class=cls1,
            )
        assert HeaderProcessorRegistry.unregister(proc_def1.qualified_key) is True
        proc_def2: ProcessorDefinition = HeaderProcessorRegistry.register(
            processor_class=cls1,
        )
        HeaderProcessorRegistry.unregister(proc_def2.qualified_key)
    finally:
        HeaderProcessorRegistry.unregister(proc_def1.qualified_key)


def test_filetype_as_mapping_is_readonly() -> None:
    """Verify that as_mapping() is read-only."""
    import types

    m: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()
    assert isinstance(m, types.MappingProxyType)
