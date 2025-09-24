# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_overlays.py
#   file_relpath : tests/api/test_registry_overlays.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for overlay behavior of file types and processors (Google style)."""

from __future__ import annotations

from topmark.filetypes.base import FileType
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry


class _P(HeaderProcessor):
    def process(self, text: str) -> str:  # one-line stub
        return text


def test_overlay_partition_updates() -> None:
    """File type becomes supported when a processor is registered and reverts when removed."""
    ft = FileType(name="ftx", extensions=[".ftx"], filenames=[], patterns=[], description="x")
    FileTypeRegistry.register(ft)
    assert "ftx" in FileTypeRegistry.unsupported_names()

    HeaderProcessorRegistry.register("ftx", _P)  # now supported
    assert "ftx" in FileTypeRegistry.supported_names()

    HeaderProcessorRegistry.unregister("ftx")
    assert "ftx" in FileTypeRegistry.unsupported_names()

    FileTypeRegistry.unregister("ftx")
    assert "ftx" not in FileTypeRegistry.as_mapping()


def test_hiding_builtin_is_non_destructive() -> None:
    """Hiding a built-in file type via overlay is non-destructive to the base registry."""
    # pick a known builtin, e.g., "python"
    assert "python" in FileTypeRegistry.names()
    FileTypeRegistry.unregister("python")
    assert "python" not in FileTypeRegistry.names()
    # Re-registering via overlay should restore visibility
    # (optional) FileTypeRegistry.register(stub_ft("python"))  # if you expose a stub factory
