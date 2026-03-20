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

from tests.conftest import resolve_processor_for_path

if TYPE_CHECKING:
    from topmark.processors.base import HeaderProcessor


def test_get_processor_for_file_resolves_builtin_processor_for_python_path() -> None:
    """Resolver should return a processor for a known built-in file type."""
    filename_to_test: str = "example.py"

    proc: HeaderProcessor | None = resolve_processor_for_path(path=Path(filename_to_test))
    assert proc is not None
    assert proc.file_type is not None
    assert proc.file_type.local_key == "python"
