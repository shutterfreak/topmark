# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_facade.py
#   file_relpath : tests/registry/test_registry_facade.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the stable Registry facade."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.processors.base import HeaderProcessor
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from pytest import MonkeyPatch

    from topmark.filetypes.model import FileType
    from topmark.registry.bindings import Binding
    from topmark.registry.types import ProcessorDefinition


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
    ft: Mapping[str, object] = Registry.filetypes_by_local_key()
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


def test_missing_entries_have_null_or_noop_facade_contracts() -> None:
    """Absent registry entries should resolve to stable null/no-op values."""
    assert Registry.get_filetype("pytest:missing_facade_filetype") is None
    assert Registry.get_processor("pytest:missing_facade_processor") is None
    assert Registry.resolve_processor("pytest:missing_facade_filetype") is None

    assert Registry.is_filetype_bound("pytest:missing_facade_filetype") is False
    assert Registry.is_processor_bound("pytest:missing_facade_processor") is False
    assert Registry.get_filetype_keys("pytest:missing_facade_processor") == ()

    assert Registry.unbind_filetype("pytest:missing_facade_filetype") is False
    assert Registry.unbind_processor("pytest:missing_facade_processor") == ()
    assert Registry.unregister_processor("pytest:missing_facade_processor") is False


def test_resolve_processor_returns_none_when_processor_disappears_mid_resolution(
    monkeypatch: MonkeyPatch,
) -> None:
    """Processor resolution should fail closed if a binding becomes stale mid-call."""
    ft: FileType = make_file_type(
        local_key="facade_stale_bound_filetype",
        extensions=[".fstale"],
        description="facade stale bound file type",
    )

    class StaleFacadeProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "facade_stale_processor"

    proc_def: ProcessorDefinition | None = None
    FileTypeRegistry.register(ft)
    try:
        proc_def = HeaderProcessorRegistry.register(
            processor_class=StaleFacadeProcessor,
        )
        Registry.bind(
            file_type_id=ft.qualified_key,
            processor_key=proc_def.qualified_key,
        )

        def _get_processor_key_for_filetype(file_type_key: str) -> str | None:
            assert file_type_key == ft.qualified_key
            return proc_def.qualified_key

        def _get_processor_for_key(processor_key: str) -> ProcessorDefinition | None:
            assert processor_key == proc_def.qualified_key
            return None

        monkeypatch.setattr(
            BindingRegistry,
            "get_processor_key",
            _get_processor_key_for_filetype,
        )
        monkeypatch.setattr(
            HeaderProcessorRegistry,
            "get",
            _get_processor_for_key,
        )

        assert Registry.resolve_processor(ft.qualified_key) is None
    finally:
        Registry.unbind_filetype(ft.qualified_key)
        if proc_def is not None:
            HeaderProcessorRegistry.unregister(proc_def.qualified_key)
        FileTypeRegistry.unregister_by_local_key(ft.local_key)


def test_unregister_processor_preserves_or_removes_bindings_explicitly() -> None:
    """Processor removal should only clear bindings when explicitly requested."""
    ft: FileType = make_file_type(
        local_key="facade_bound_filetype",
        extensions=[".facade"],
        description="facade bound file type",
    )

    class FacadeProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "facade_processor"

    proc_def: ProcessorDefinition | None = None
    FileTypeRegistry.register(ft)
    try:
        proc_def = HeaderProcessorRegistry.register(processor_class=FacadeProcessor)
        Registry.bind(
            file_type_id=ft.local_key,
            processor_key=proc_def.qualified_key,
        )

        proc_obj: HeaderProcessor | None = Registry.resolve_processor(ft.qualified_key)

        assert proc_obj is not None
        assert proc_obj.file_type is ft
        assert Registry.is_filetype_bound(ft.local_key) is True
        assert Registry.is_processor_bound(proc_def.qualified_key) is True
        assert Registry.get_filetype_keys(proc_def.qualified_key) == (ft.qualified_key,)

        assert Registry.unregister_processor(proc_def.qualified_key) is False
        assert Registry.get_processor(proc_def.qualified_key) is proc_def
        assert Registry.is_filetype_bound(ft.qualified_key) is True

        assert (
            Registry.unregister_processor(
                proc_def.qualified_key,
                remove_bindings=True,
            )
            is True
        )
        assert Registry.get_processor(proc_def.qualified_key) is None
        assert Registry.is_filetype_bound(ft.qualified_key) is False
    finally:
        Registry.unbind_filetype(ft.qualified_key)
        if proc_def is not None:
            HeaderProcessorRegistry.unregister(proc_def.qualified_key)
        FileTypeRegistry.unregister_by_local_key(ft.local_key)
