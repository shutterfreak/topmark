# topmark:header:start
#
#   project      : TopMark
#   file         : test_register_unregister.py
#   file_relpath : tests/registry/test_register_unregister.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for registering and unregistering processors and filetypes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.processors.base import HeaderProcessor
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorDefinition


def test_register_and_unregister_filetypes() -> None:
    """Verify that the registry mutators change behavior via overlays."""
    ft: FileType = make_file_type(
        local_key="tmp",
        extensions=[".tmp"],
        filenames=[],
        patterns=[],
        description="tmp",
    )

    FileTypeRegistry.register(ft)
    assert "tmp" in FileTypeRegistry.as_mapping_by_local_key()

    FileTypeRegistry.unregister_by_local_key("tmp")
    # Composed view should reflect removal immediately
    assert "tmp" not in FileTypeRegistry.as_mapping_by_local_key()


def test_register_filetype_exposes_normalized_filename_rules() -> None:
    """Registered file types expose canonical POSIX filename rules."""
    ft: FileType = make_file_type(
        local_key="tmp_tail_rule",
        extensions=[],
        filenames=[r".vscode\settings.json"],
        patterns=[],
        description="tmp tail rule",
    )

    FileTypeRegistry.register(ft)
    try:
        registered: FileType = FileTypeRegistry.as_mapping_by_local_key()["tmp_tail_rule"]
        assert registered.filenames == [".vscode/settings.json"]
    finally:
        FileTypeRegistry.unregister_by_local_key("tmp_tail_rule")


def test_register_and_unregister_processors() -> None:
    """Verify that processor registration and binding mutators change behavior."""
    # Ensure the target file type exists before processor registration.
    ft: FileType = make_file_type(
        local_key="tmp",
        extensions=[".tmp"],
        filenames=[],
        patterns=[],
        description="tmp",
    )

    FileTypeRegistry.register(ft)
    assert "tmp" in FileTypeRegistry.as_mapping_by_local_key()

    class TmpProcessor(HeaderProcessor):
        key = "tmp_processor"
        namespace = "test"

        def process(self, text: str) -> str:
            return text

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=TmpProcessor,
    )
    assert proc_def.qualified_key in HeaderProcessorRegistry.as_mapping()

    BindingRegistry.bind(
        file_type_key=ft.qualified_key,
        processor_key=proc_def.qualified_key,
    )
    assert BindingRegistry.get_processor_key(ft.qualified_key) == proc_def.qualified_key

    BindingRegistry.unbind(ft.qualified_key)
    assert BindingRegistry.get_processor_key(ft.qualified_key) is None

    HeaderProcessorRegistry.unregister(proc_def.qualified_key)
    assert proc_def.qualified_key not in HeaderProcessorRegistry.as_mapping()

    FileTypeRegistry.unregister_by_local_key("tmp")
    assert "tmp" not in FileTypeRegistry.as_mapping_by_local_key()


def test_binding_registry_rejects_unknown_processor() -> None:
    """Binding a known file type to an unknown processor should fail explicitly."""
    import pytest

    from topmark.core.errors import ProcessorBindingError

    ft: FileType = make_file_type(
        local_key="tmp_unknown_processor",
        extensions=[".tup"],
        filenames=[],
        patterns=[],
        description="tmp unknown processor",
    )

    FileTypeRegistry.register(ft)
    try:
        with pytest.raises(ProcessorBindingError, match="Unknown processor qualified key"):
            BindingRegistry.bind(
                file_type_key=ft.qualified_key,
                processor_key="pytest:missing_processor",
            )
    finally:
        FileTypeRegistry.unregister_by_local_key(ft.local_key)


def test_binding_registry_rejects_duplicate_binding() -> None:
    """A file type cannot be rebound without removing the existing binding first."""
    import pytest

    from topmark.core.errors import ProcessorBindingError

    ft: FileType = make_file_type(
        local_key="tmp_duplicate_binding",
        extensions=[".tdb"],
        filenames=[],
        patterns=[],
        description="tmp duplicate binding",
    )

    class DuplicateBindingProcessor(HeaderProcessor):
        namespace = "test"
        local_key = "duplicate_binding_processor"

    proc_def: ProcessorDefinition | None = None
    FileTypeRegistry.register(ft)
    try:
        proc_def = HeaderProcessorRegistry.register(
            processor_class=DuplicateBindingProcessor,
        )
        BindingRegistry.bind(
            file_type_key=ft.qualified_key,
            processor_key=proc_def.qualified_key,
        )

        with pytest.raises(ProcessorBindingError, match="already bound"):
            BindingRegistry.bind(
                file_type_key=ft.qualified_key,
                processor_key=proc_def.qualified_key,
            )
    finally:
        BindingRegistry.unbind(ft.qualified_key)
        if proc_def is not None:
            HeaderProcessorRegistry.unregister(proc_def.qualified_key)
        FileTypeRegistry.unregister_by_local_key(ft.local_key)


def test_binding_registry_unbind_reports_absent_binding() -> None:
    """Unbinding an absent key should be an idempotent no-op signal."""
    assert BindingRegistry.unbind("pytest:not_bound") is False


def test_binding_registry_unbind_processor_removes_all_references() -> None:
    """Unbinding by processor removes every effective binding referencing it."""
    fts: list[FileType] = [
        make_file_type(
            local_key="tmp_bulk_unbind_a",
            extensions=[".tba"],
            filenames=[],
            patterns=[],
            description="tmp bulk a",
        ),
        make_file_type(
            local_key="tmp_bulk_unbind_b",
            extensions=[".tbb"],
            filenames=[],
            patterns=[],
            description="tmp bulk b",
        ),
    ]

    class BulkUnbindProcessor(HeaderProcessor):
        namespace = "test"
        local_key = "bulk_unbind_processor"

    proc_def: ProcessorDefinition | None = None
    for ft in fts:
        FileTypeRegistry.register(ft)
    try:
        proc_def = HeaderProcessorRegistry.register(processor_class=BulkUnbindProcessor)
        for ft in fts:
            BindingRegistry.bind(
                file_type_key=ft.qualified_key,
                processor_key=proc_def.qualified_key,
            )

        removed: tuple[str, ...] = BindingRegistry.unbind_processor(proc_def.qualified_key)

        assert removed == tuple(sorted(ft.qualified_key for ft in fts))
        assert all(BindingRegistry.get_processor_key(ft.qualified_key) is None for ft in fts)
        assert not BindingRegistry.is_processor_bound(proc_def.qualified_key)
    finally:
        for ft in fts:
            BindingRegistry.unbind(ft.qualified_key)
        if proc_def is not None:
            HeaderProcessorRegistry.unregister(proc_def.qualified_key)
        for ft in fts:
            FileTypeRegistry.unregister_by_local_key(ft.local_key)
