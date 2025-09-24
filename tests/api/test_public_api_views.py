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

from topmark.filetypes.base import FileType
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry


def test_register_and_unregister_filetypes() -> None:
    """Verify that the registry mutators change behavior via overlays."""
    ft = FileType(
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
    ft = FileType(
        name="tmp",
        extensions=[".tmp"],
        filenames=[],
        patterns=[],
        description="tmp",
    )
    FileTypeRegistry.register(ft)
    assert "tmp" in FileTypeRegistry.as_mapping()

    class TmpProcessor(HeaderProcessor):
        def process(self, text: str) -> str:
            return text

    HeaderProcessorRegistry.register("tmp", TmpProcessor)
    assert "tmp" in HeaderProcessorRegistry.as_mapping()

    HeaderProcessorRegistry.unregister("tmp")
    assert "tmp" not in HeaderProcessorRegistry.as_mapping()

    FileTypeRegistry.unregister("tmp")
    assert "tmp" not in FileTypeRegistry.as_mapping()
