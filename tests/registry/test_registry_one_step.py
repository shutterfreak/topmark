# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_one_step.py
#   file_relpath : tests/registry/test_registry_one_step.py
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

from tests.helpers.registry import make_file_type
from tests.helpers.registry import registry_processor_class
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition


def test_register_filetype_with_processor_in_one_step() -> None:
    """Register FT and processor in one step; verify support and binding."""
    name = "one_step"
    ft: FileType = make_file_type(local_key=name)
    processor_qualified_key: str | None = None
    try:
        proc_cls: type[HeaderProcessor] = registry_processor_class()
        FileTypeRegistry.register(ft)
        proc_def: ProcessorDefinition | None = HeaderProcessorRegistry.register(
            processor_class=proc_cls,
        )
        Registry.bind(
            file_type_id=name,
            processor_key=proc_def.qualified_key,
        )
        assert name in Registry.bound_filetype_local_keys()

        processor_qualified_key = BindingRegistry.get_processor_key(
            ft.qualified_key,
        )
        assert processor_qualified_key is not None

        proc_def = HeaderProcessorRegistry.get(
            processor_qualified_key,
        )
        assert proc_def is not None
        assert proc_def.local_key == proc_cls.local_key

        proc: HeaderProcessor | None = Registry.resolve_processor(name)
        assert proc is not None
        assert proc.file_type is not None
        assert proc.file_type.local_key == name
    finally:
        Registry.unbind_filetype(name)
        if processor_qualified_key is not None:
            Registry.unregister_processor(
                processor_qualified_key,
                remove_bindings=False,
            )
        FileTypeRegistry.unregister_by_local_key(name)
