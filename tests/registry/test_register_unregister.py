# topmark:header:start
#
#   project      : TopMark
#   file         : test_register_unregister.py
#   file_relpath : tests/registry/test_register_unregister.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for registering and unregistering processors and filetypes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import make_file_type
from topmark.processors.base import HeaderProcessor
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


def test_register_and_unregister_filetypes() -> None:
    """Verify that the registry mutators change behavior via overlays."""
    ft: FileType = make_file_type(
        name="tmp",
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
    """Verify that processor overlay mutators change behavior."""
    # Ensure the target file type exists before processor registration.
    ft: FileType = make_file_type(
        name="tmp",
        extensions=[".tmp"],
        filenames=[],
        patterns=[],
        description="tmp",
    )
    FileTypeRegistry.register(ft)
    assert "tmp" in FileTypeRegistry.as_mapping()

    class TmpProcessor(HeaderProcessor):
        key = "tmp_processor"
        namespace = "test"

        def process(self, text: str) -> str:
            return text

    HeaderProcessorRegistry.register(
        file_type=ft,
        processor_class=TmpProcessor,
    )
    assert "tmp" in HeaderProcessorRegistry.as_mapping()

    HeaderProcessorRegistry.unregister("tmp")
    assert "tmp" not in HeaderProcessorRegistry.as_mapping()

    FileTypeRegistry.unregister("tmp")
    assert "tmp" not in FileTypeRegistry.as_mapping()
