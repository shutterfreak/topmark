# topmark:header:start
#
#   project      : TopMark
#   file         : test_public_api_views.py
#   file_relpath : tests/api/test_public_api_views.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the public API facade (read-only views and mutators)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

from tests.conftest import make_file_type
from topmark.processors.base import HeaderProcessor
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorDefinition


def test_register_and_unregister_filetypes() -> None:
    """Verify that the registry mutators change behavior via overlays."""
    ft: FileType = make_file_type(
        local_key="tmp",
        extensions=[".tmp"],
        filenames=[],
        patterns=[],
        description="tmp",
    )

    FileTypeRegistry.register(ft)
    assert "tmp" in FileTypeRegistry.as_mapping()

    FileTypeRegistry.unregister("tmp")
    # Composed view should reflect removal immediately
    assert "tmp" not in FileTypeRegistry.as_mapping()


def test_register_and_unregister_processors() -> None:
    """Verify that processor registration and binding mutators change behavior."""
    # Ensure the target file type exists before processor registration.
    ft: FileType = make_file_type(
        local_key="tmp",
        extensions=[".tmp"],
        filenames=[],
        patterns=[],
        description="tmp",
    )
    FileTypeRegistry.register(ft)
    assert "tmp" in FileTypeRegistry.as_mapping()

    class TmpProcessor(HeaderProcessor):
        name: ClassVar = "test_proc"
        namespace = "pytest"

        def process(self, text: str) -> str:
            return text

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=TmpProcessor,
    )
    assert proc_def.qualified_key in HeaderProcessorRegistry.as_mapping_by_qualified_key()

    BindingRegistry.bind(
        filetype_qualified_key=ft.qualified_key,
        processor_qualified_key=proc_def.qualified_key,
    )
    assert (
        BindingRegistry.get_processor_key_for_filetype(ft.qualified_key) == proc_def.qualified_key
    )

    BindingRegistry.unbind(ft.qualified_key)
    assert BindingRegistry.get_processor_key_for_filetype(ft.qualified_key) is None

    HeaderProcessorRegistry.unregister_by_qualified_key(proc_def.qualified_key)
    assert proc_def.qualified_key not in HeaderProcessorRegistry.as_mapping_by_qualified_key()

    FileTypeRegistry.unregister("tmp")
    assert "tmp" not in FileTypeRegistry.as_mapping()
