# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_facade.py
#   file_relpath : tests/api/test_registry_facade.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the Registry facade (read-only surface)."""

from __future__ import annotations

from collections.abc import Mapping

from topmark.registry import Registry


def test_bindings_shape() -> None:
    """Bindings are a tuple of pairs with filetype and optional processor."""
    bs = Registry.bindings()
    assert isinstance(bs, tuple)
    # If the system has at least one file type, each binding has a filetype
    for b in bs:
        assert hasattr(b, "filetype")
        assert hasattr(b, "processor")  # may be None


def test_filetypes_mapping_is_readonly() -> None:
    """Filetypes mapping is read-only (fails on attempted mutation)."""
    ft = Registry.filetypes()
    assert isinstance(ft, Mapping)
    # Mapping proxy should raise on mutation
    try:
        ft["__should_not_exist__"] = object()  # type: ignore[index]
        raised = False
    except TypeError:
        raised = True
    assert raised


def test_processors_mapping_is_readonly() -> None:
    """Processors mapping is read-only (fails on attempted mutation)."""
    procs = Registry.processors()
    assert isinstance(procs, Mapping)
    try:
        procs["__should_not_exist__"] = object()  # type: ignore[index]
        raised = False
    except TypeError:
        raised = True
    assert raised
