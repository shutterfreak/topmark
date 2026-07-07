# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_public_api.py
#   file_relpath : tests/registry/test_registry_public_api.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# tests/api/test_registry_public_api.py
"""Tests for the public registry classes (FileTypeRegistry, HeaderProcessorRegistry).

These tests verify read-only views, metadata iteration, and the optional
mutation hooks (register/unregister). Mutations operate on global registries,
so every test that registers a temporary entry must ensure cleanup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

import pytest
from pytest import MonkeyPatch

from tests.helpers.registry import make_file_type
from tests.helpers.registry import registry_processor_class
from topmark.core.errors import DuplicateProcessorKeyError
from topmark.core.errors import DuplicateProcessorRegistrationError
from topmark.core.errors import ReservedNamespaceError
from topmark.processors.base import HeaderProcessor
from topmark.registry import processors as processor_registry_module
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.types import ProcessorDefinition

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorMeta


# ---------- helpers (duck-typed stubs) ----------


@pytest.mark.parametrize("dummy_name", ["dummy_ft", "dummy_ft_2"])
def test_filetype_register_unregister_roundtrip(dummy_name: str) -> None:
    """Register a stub file type and then unregister it."""
    ft: FileType = make_file_type(
        local_key=dummy_name,
        description="Stub FT",
    )

    try:
        # Register
        FileTypeRegistry.register(ft)
        # Visible via names() and as_mapping()
        assert dummy_name in FileTypeRegistry.names()
        assert dummy_name in FileTypeRegistry.as_mapping_by_local_key()
        # Visible via iter_meta()
        names: set[str] = {m.local_key for m in FileTypeRegistry.iter_meta_by_local_key()}
        assert dummy_name in names
    finally:
        # Cleanup
        assert FileTypeRegistry.unregister_by_local_key(dummy_name) is True
        assert dummy_name not in FileTypeRegistry.names()


def test_filetype_register_duplicate_raises() -> None:
    """Registering the same file type name twice should raise ValueError."""
    name = "dup_ft"
    ft1: FileType = make_file_type(local_key=name)
    ft2: FileType = make_file_type(local_key=name)
    try:
        FileTypeRegistry.register(ft1)
        with pytest.raises(ValueError):
            FileTypeRegistry.register(ft2)
    finally:
        FileTypeRegistry.unregister_by_local_key(name)


@pytest.mark.parametrize("proc_name", ["dummy_proc"])
def test_processor_register_unregister_roundtrip(proc_name: str) -> None:
    """Register a stub processor definition and then unregister it by qualified key."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=proc_cls,
    )
    try:
        assert proc_def.qualified_key in HeaderProcessorRegistry.as_mapping()
        names: set[str] = {m.local_key for m in HeaderProcessorRegistry.iter_meta()}
        assert proc_def.local_key in names
    finally:
        assert HeaderProcessorRegistry.unregister(proc_def.qualified_key) is True
        assert proc_def.qualified_key not in HeaderProcessorRegistry.as_mapping()


def test_processor_register_duplicate_raises() -> None:
    """Registering the same processor qualified key twice should raise."""
    proc_cls: type[HeaderProcessor] = registry_processor_class()
    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=proc_cls,
    )
    try:
        with pytest.raises(DuplicateProcessorRegistrationError):
            HeaderProcessorRegistry.register(
                processor_class=proc_cls,
            )
    finally:
        HeaderProcessorRegistry.unregister(proc_def.qualified_key)


def test_replace_processor_requires_unregister() -> None:
    """Verifies you can't register the same processor twice without first unregistering it."""
    cls1: type[HeaderProcessor] = registry_processor_class()
    proc_def1: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=cls1,
    )
    try:
        with pytest.raises(DuplicateProcessorRegistrationError):
            HeaderProcessorRegistry.register(
                processor_class=cls1,
            )
        assert HeaderProcessorRegistry.unregister(proc_def1.qualified_key) is True
        proc_def2: ProcessorDefinition = HeaderProcessorRegistry.register(
            processor_class=cls1,
        )
        HeaderProcessorRegistry.unregister(proc_def2.qualified_key)
    finally:
        HeaderProcessorRegistry.unregister(proc_def1.qualified_key)


def test_filetype_as_mapping_is_readonly() -> None:
    """Verify that as_mapping() is read-only."""
    import types

    m: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()
    assert isinstance(m, types.MappingProxyType)


def test_processor_register_rejects_non_type_candidate() -> None:
    """Processor registration should reject non-class candidates at runtime."""
    # Deliberately bypass the static API type to verify the runtime guard.
    candidate: type[HeaderProcessor] = cast("type[HeaderProcessor]", object())

    with pytest.raises(
        TypeError, match="Expected subclass of HeaderProcessor, got non-type object"
    ):
        HeaderProcessorRegistry.register(processor_class=candidate)


def test_processor_register_rejects_non_processor_class() -> None:
    """Processor registration should reject classes outside the processor hierarchy."""
    # Deliberately bypass the static API type to verify the runtime guard.
    candidate: type[HeaderProcessor] = cast("type[HeaderProcessor]", object)

    with pytest.raises(TypeError, match="Expected subclass of HeaderProcessor, got object"):
        HeaderProcessorRegistry.register(processor_class=candidate)


def test_processor_class_definition_rejects_external_topmark_namespace() -> None:
    """External processor subclasses should not be allowed to claim `topmark`."""
    with pytest.raises(TypeError, match="reserved for built-in TopMark processors"):

        class ExternalTopmarkProcessor(HeaderProcessor):
            namespace = "topmark"
            local_key = "external_reserved_processor"

        assert ExternalTopmarkProcessor.namespace == "topmark"


def test_processor_iter_meta_projects_registered_processor_attributes() -> None:
    """Processor metadata iteration should expose stable processor presentation fields."""

    class MetadataProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "metadata_processor"
        description = "metadata processor"
        block_prefix = "/*"
        block_suffix = "*/"
        line_indent = "  "
        line_prefix = "* "
        line_suffix = " !"

    proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
        processor_class=MetadataProcessor,
    )
    try:
        meta: ProcessorMeta = next(
            item
            for item in HeaderProcessorRegistry.iter_meta()
            if item.qualified_key == proc_def.qualified_key
        )

        assert meta.namespace == "pytest"
        assert meta.local_key == "metadata_processor"
        assert meta.description == "metadata processor"
        assert meta.block_prefix == "/*"
        assert meta.block_suffix == "*/"
        assert meta.line_indent == "  "
        assert meta.line_prefix == "* "
        assert meta.line_suffix == " !"
    finally:
        HeaderProcessorRegistry.unregister(proc_def.qualified_key)


def test_processor_get_returns_none_for_unknown_key() -> None:
    """Unknown processor keys should resolve to a stable null value."""
    assert HeaderProcessorRegistry.get("pytest:missing_processor_public_api") is None


def test_processor_as_mapping_is_readonly_and_reuses_composed_cache() -> None:
    """Processor mappings should be immutable and reuse the composed cache."""
    import types

    first: Mapping[str, ProcessorDefinition] = HeaderProcessorRegistry.as_mapping()
    second: Mapping[str, ProcessorDefinition] = HeaderProcessorRegistry.as_mapping()

    assert isinstance(first, types.MappingProxyType)
    assert first is second

    # Preserves the read-only contract:
    assert not hasattr(first, "__setitem__")


def test_processor_qualified_keys_are_sorted_and_include_registered_overlays() -> None:
    """Processor qualified-key iteration should be sorted and include overlays."""

    class ZetaProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "zeta_processor"

    class AlphaProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "alpha_processor"

    first_def: ProcessorDefinition | None = None
    second_def: ProcessorDefinition | None = None
    try:
        first_def = HeaderProcessorRegistry.register(processor_class=ZetaProcessor)
        second_def = HeaderProcessorRegistry.register(processor_class=AlphaProcessor)

        keys: tuple[str, ...] = HeaderProcessorRegistry.qualified_keys()

        assert keys == tuple(sorted(keys))
        assert first_def.qualified_key in keys
        assert second_def.qualified_key in keys
    finally:
        if first_def is not None:
            HeaderProcessorRegistry.unregister(first_def.qualified_key)
        if second_def is not None:
            HeaderProcessorRegistry.unregister(second_def.qualified_key)


def test_processor_namespaces_are_sorted_unique_and_include_registered_overlays() -> None:
    """Processor namespace iteration should return a sorted unique namespace set."""

    class ZedNamespaceProcessor(HeaderProcessor):
        namespace = "zpytest"
        local_key = "namespace_processor"

    class AlphaNamespaceProcessor(HeaderProcessor):
        namespace = "apytest"
        local_key = "namespace_processor"

    first_def: ProcessorDefinition | None = None
    second_def: ProcessorDefinition | None = None
    try:
        first_def = HeaderProcessorRegistry.register(processor_class=ZedNamespaceProcessor)
        second_def = HeaderProcessorRegistry.register(processor_class=AlphaNamespaceProcessor)

        namespaces: tuple[str, ...] = HeaderProcessorRegistry.namespaces()

        assert namespaces == tuple(sorted(set(namespaces)))
        assert "apytest" in namespaces
        assert "zpytest" in namespaces
    finally:
        if first_def is not None:
            HeaderProcessorRegistry.unregister(first_def.qualified_key)
        if second_def is not None:
            HeaderProcessorRegistry.unregister(second_def.qualified_key)


def test_processor_unregister_returns_false_for_unknown_key() -> None:
    """Unregistering an unknown processor should be a no-op."""
    assert HeaderProcessorRegistry.unregister("pytest:missing_processor_public_api") is False


def test_processor_registry_translates_reserved_namespace_validation_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    """Registry validation should expose reserved namespace failures as core errors."""

    class PatchedReservedProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "patched_reserved_processor"

    def _reject_reserved_namespace(
        *,
        namespace: str,
        owner: str,
        owner_module: str,
        entities: str,
    ) -> None:
        assert namespace == "pytest"
        assert owner.endswith("PatchedReservedProcessor")
        assert owner_module == PatchedReservedProcessor.__module__
        assert entities == "processors"
        raise TypeError("forced reserved namespace failure")

    monkeypatch.setattr(
        processor_registry_module,
        "validate_reserved_topmark_namespace",
        _reject_reserved_namespace,
    )

    with pytest.raises(ReservedNamespaceError):
        HeaderProcessorRegistry.register(processor_class=PatchedReservedProcessor)


def test_processor_compose_rejects_base_key_that_disagrees_with_processor_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    """Base registry composition should reject mismatched canonical keys."""

    class MismatchedBaseProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "mismatched_base_processor"

    proc_def = ProcessorDefinition(
        namespace="pytest",
        local_key="mismatched_base_processor",
        processor_class=MismatchedBaseProcessor,
    )

    def _base_registry() -> dict[str, ProcessorDefinition]:
        return {"pytest:wrong_processor_key": proc_def}

    monkeypatch.setattr(
        "topmark.processors.instances.get_base_processor_definition_registry",
        _base_registry,
    )
    HeaderProcessorRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
    try:
        with pytest.raises(DuplicateProcessorKeyError):
            HeaderProcessorRegistry.qualified_keys()
    finally:
        HeaderProcessorRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
