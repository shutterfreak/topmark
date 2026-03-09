# topmark:header:start
#
#   project      : TopMark
#   file         : test_base_registry.py
#   file_relpath : tests/filetypes/test_base_registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Smoke tests for the base file type registry.

These tests verify that representative built-in file types are loaded into the
cached base registry exposed by `topmark.filetypes.instances`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.filetypes.instances import get_base_file_type_registry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


def test_base_file_type_registry_contains_expected_builtins() -> None:
    """Smoke-test that built-in file types are loaded into the base registry."""
    registry: dict[str, FileType] = get_base_file_type_registry()

    # Representative known built-ins; keep this small and stable.
    expected_names: set[str] = {
        "python",
        "markdown",
        "xml",
    }

    missing: set[str] = expected_names.difference(registry)
    assert not missing, f"Missing built-in file types: {sorted(missing)}"
