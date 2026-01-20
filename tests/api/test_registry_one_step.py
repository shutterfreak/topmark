# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_one_step.py
#   file_relpath : tests/api/test_registry_one_step.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""One-step convenience registration tests for the public registry API.

Covers `FileTypeRegistry.register(..., processor=...)` to ensure it chains to
`HeaderProcessorRegistry.register`, creates a bound processor instance, and
marks the file type as supported. These tests focus on the convenience path
rather than the two-step registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.api.conftest import stub_ft, stub_proc_cls
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


def test_register_filetype_with_processor_in_one_step() -> None:
    """Register FT and processor in one step; verify support and binding."""
    name = "one_step"
    ft: FileType = stub_ft(name)
    try:
        FileTypeRegistry.register(ft, processor=stub_proc_cls())
        assert name in FileTypeRegistry.supported_names()
        assert HeaderProcessorRegistry.is_registered(name)
        proc: HeaderProcessor = HeaderProcessorRegistry.as_mapping()[name]
        assert proc.file_type is not None and proc.file_type.name == name
    finally:
        HeaderProcessorRegistry.unregister(name)
        FileTypeRegistry.unregister(name)
