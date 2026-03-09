# topmark:header:start
#
#   project      : TopMark
#   file         : test_base_registry.py
#   file_relpath : tests/processors/test_base_registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Smoke tests for the base header processor registry.

These tests verify that representative built-in processors are imported and
registered into the base processor registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.processors.builtins.markdown import MarkdownHeaderProcessor
from topmark.processors.builtins.pound import PoundHeaderProcessor
from topmark.processors.builtins.xml import XmlHeaderProcessor
from topmark.processors.instances import get_base_header_processor_registry

if TYPE_CHECKING:
    from topmark.processors.base import HeaderProcessor


def test_base_processor_registry_contains_expected_builtins() -> None:
    """Smoke-test that built-in processors are loaded into the base registry."""
    registry: dict[str, HeaderProcessor] = get_base_header_processor_registry()

    assert "python" in registry
    assert "markdown" in registry
    assert "xml" in registry

    assert isinstance(registry["python"], PoundHeaderProcessor)
    assert isinstance(registry["markdown"], MarkdownHeaderProcessor)
    assert isinstance(registry["xml"], XmlHeaderProcessor)
