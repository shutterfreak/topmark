# topmark:header:start
#
#   project      : TopMark
#   file         : test_resolver.py
#   file_relpath : tests/registry/test_resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Focused tests for path-to-processor resolution.

These tests verify that the registry resolver can map representative file paths
onto built-in header processors using the composed registries.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.registry.resolver import get_processor_for_file

if TYPE_CHECKING:
    from topmark.processors.base import HeaderProcessor


def test_get_processor_for_file_resolves_builtin_processor_for_python_path() -> None:
    """Resolver should return a processor for a known built-in file type."""
    filename_to_test: str = "example.py"

    processor: HeaderProcessor | None = get_processor_for_file(Path(filename_to_test))

    assert processor is not None
    assert processor.file_type is not None
    assert processor.file_type.name == "python"
