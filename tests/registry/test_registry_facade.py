# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_facade.py
#   file_relpath : tests/registry/test_registry_facade.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the stable Registry facade (read-only surface)."""

from __future__ import annotations

from collections.abc import Mapping

from topmark.registry.registry import Binding
from topmark.registry.registry import Registry


def test_bindings_shape() -> None:
    """Registry bindings are a tuple of pairs with filetype and optional processor."""
    bs: tuple[Binding, ...] = Registry.bindings()
    assert isinstance(bs, tuple)
    # If the system has at least one file type, each binding has a filetype
    for b in bs:
        assert hasattr(b, "filetype")
        assert hasattr(b, "processor")  # may be None


def test_filetypes_mapping_is_readonly() -> None:
    """Registry filetypes mapping is read-only (raises on attempted mutation)."""
    ft: Mapping[str, object] = Registry.filetypes()
    assert isinstance(ft, Mapping)
    # Mapping proxy must raise on mutation
    try:
        ft["__should_not_exist__"] = object()  # type: ignore[index]
        raised = False
    except TypeError:
        raised = True
    assert raised


def test_processors_mapping_is_readonly() -> None:
    """Registry processors mapping is read-only (raises on attempted mutation)."""
    procs: Mapping[str, object] = Registry.processors()
    assert isinstance(procs, Mapping)
    # Mapping proxy must raise on mutation
    try:
        procs["__should_not_exist__"] = object()  # type: ignore[index]
        raised = False
    except TypeError:
        raised = True
    assert raised
