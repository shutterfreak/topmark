# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_linkage.py
#   file_relpath : tests/processors/test_registry_linkage.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Invariant tests linking the base file type and processor registries.

These tests verify that each registered base processor is bound to the
corresponding built-in file type named by its registry key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.filetypes.instances import get_base_file_type_registry
from topmark.processors.instances import get_base_header_processor_registry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor


def test_base_processor_registry_entries_are_bound_to_matching_filetypes() -> None:
    """Ensure each registered processor is bound to the file type named by its key."""
    ft_registry: dict[str, FileType] = get_base_file_type_registry()
    hp_registry: dict[str, HeaderProcessor] = get_base_header_processor_registry()

    for name, processor in hp_registry.items():
        assert name in ft_registry, f"Processor key {name!r} has no matching file type"
        assert processor.file_type is not None, (
            f"Processor key {name!r} is not bound to a file type"
        )

        assert processor.file_type.name == name
        assert processor.file_type is ft_registry[name]
