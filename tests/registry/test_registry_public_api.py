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

from tests.conftest import make_file_type
from tests.conftest import registry_processor_class
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
        assert dummy_name in FileTypeRegistry.as_mapping()
        # Visible via iter_meta()
        names: set[str] = {m.local_key for m in FileTypeRegistry.iter_meta()}
        assert dummy_name in names
    finally:
        # Cleanup
        assert FileTypeRegistry.unregister(dummy_name) is True
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
        FileTypeRegistry.unregister(name)


@pytest.mark.parametrize("proc_name", ["dummy_proc"])
def test_processor_register_unregister_roundtrip(proc_name: str) -> None:
    """Register a stub processor under a new name and then unregister it."""
    ft: FileType = make_file_type(local_key=proc_name)
    FileTypeRegistry.register(ft)

    proc_cls: type[HeaderProcessor] = registry_processor_class()

    try:
        HeaderProcessorRegistry.register(
            processor_class=proc_cls,
            file_type=ft,
        )
        proc_def: ProcessorDefinition = HeaderProcessorRegistry.as_mapping()[proc_name]
        names: set[str] = {m.local_key for m in HeaderProcessorRegistry.iter_meta()}
        assert proc_def.local_key in names
    finally:
        assert HeaderProcessorRegistry.unregister(proc_name) is True
        assert proc_name not in HeaderProcessorRegistry.names()
        FileTypeRegistry.unregister(proc_name)


def test_processor_register_duplicate_raises() -> None:
    """Registering a processor under an existing name should raise.

    Regustering under an expsting name raises DuplicateProcessorRegistrationError.
    """
    name = "dup_proc"

    ft: FileType = make_file_type(local_key=name)
    FileTypeRegistry.register(ft)

    proc_cls: type[HeaderProcessor] = registry_processor_class()

    try:
        HeaderProcessorRegistry.register(
            processor_class=proc_cls,
            file_type=ft,
        )
        with pytest.raises(DuplicateProcessorRegistrationError):
            HeaderProcessorRegistry.register(
                processor_class=proc_cls,
                file_type=ft,
            )
    finally:
        HeaderProcessorRegistry.unregister(name)
        FileTypeRegistry.unregister(name)


def test_replace_processor_requires_unregister() -> None:
    """Verifies you can’t register a second processor without first unregistering."""
    name = "replace_proc_demo"

    FileTypeRegistry.register(make_file_type(local_key=name))
    try:
        cls1: type[HeaderProcessor] = registry_processor_class()
        cls2: type[HeaderProcessor] = registry_processor_class()
        HeaderProcessorRegistry.register(
            processor_class=cls1,
            file_type=FileTypeRegistry.as_mapping()[name],
        )
        import pytest

        with pytest.raises(DuplicateProcessorRegistrationError):
            HeaderProcessorRegistry.register(
                processor_class=cls2,
                file_type=FileTypeRegistry.as_mapping()[name],
            )
        assert HeaderProcessorRegistry.unregister(name) is True
        HeaderProcessorRegistry.register(
            processor_class=cls2,
            file_type=FileTypeRegistry.as_mapping()[name],
        )  # now OK
    finally:
        HeaderProcessorRegistry.unregister(name)
        FileTypeRegistry.unregister(name)


def test_filetype_as_mapping_is_readonly() -> None:
    """Verify that as_mapping() is read-only."""
    import types

    m: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    assert isinstance(m, types.MappingProxyType)
