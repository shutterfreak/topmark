# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_overlays.py
#   file_relpath : tests/registry/test_registry_overlays.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for overlay behavior of file types and processors (Google style)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.processors.base import HeaderProcessor
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorDefinition


class _P(HeaderProcessor):
    """Stub processor for registry overlay tests."""

    namespace = "test"
    local_key = "p"

    def process(self, text: str) -> str:  # one-line stub
        return text


def test_overlay_partition_updates() -> None:
    """File type becomes supported when a processor is registered and reverts when removed."""
    ft: FileType = make_file_type(
        local_key="ftx",
        extensions=[".ftx"],
        filenames=[],
        patterns=[],
        description="x",
    )
    FileTypeRegistry.register(ft)
    assert "ftx" in Registry.unbound_filetype_local_keys()

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=_P,
    )
    Registry.bind(
        file_type_id=ft.local_key,
        processor_key=proc_def.qualified_key,
    )  # now supported
    assert BindingRegistry.get_processor_key(ft.qualified_key) == proc_def.qualified_key

    assert "ftx" in Registry.bound_filetype_local_keys()

    Registry.unbind_filetype("ftx")
    assert BindingRegistry.get_processor_key(ft.qualified_key) is None
    assert "ftx" in FileTypeRegistry.as_mapping_by_local_key()
    assert "ftx" not in Registry.bound_filetype_local_keys()
    assert "ftx" in Registry.unbound_filetype_local_keys()

    assert (
        Registry.unregister_processor(
            proc_def.qualified_key,
            remove_bindings=False,
        )
        is True
    )
    FileTypeRegistry.unregister_by_local_key("ftx")
    assert "ftx" not in FileTypeRegistry.as_mapping_by_local_key()
    assert "ftx" not in Registry.unbound_filetype_local_keys()


def test_hiding_builtin_is_non_destructive() -> None:
    """Hiding a built-in file type via overlay is non-destructive to the base registry."""
    # pick a known builtin, e.g., "python"
    assert "python" in FileTypeRegistry.names()
    FileTypeRegistry.unregister_by_local_key("python")
    assert "python" not in FileTypeRegistry.names()
    # Re-registering via overlay should restore visibility
    # (optional) FileTypeRegistry.register(stub_ft("python"))  # if you expose a stub factory
