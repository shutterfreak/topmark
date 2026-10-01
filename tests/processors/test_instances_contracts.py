# topmark:header:start
#
#   project      : TopMark
#   file         : test_instances_contracts.py
#   file_relpath : tests/processors/test_instances_contracts.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Composition and ownership contracts for built-in processor registries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.errors import ProcessorBindingError
from topmark.filetypes.instances import get_base_file_type_registry
from topmark.processors import instances
from topmark.processors.base import NO_LINE_ANCHOR
from topmark.processors.base import HeaderProcessor
from topmark.processors.bindings import ProcessorBinding
from topmark.processors.builtins.xml import XmlHeaderProcessor
from topmark.registry.identity import make_qualified_key

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator

    from pytest import MonkeyPatch

    from topmark.filetypes.model import FileType
    from topmark.registry.types import ProcessorDefinition


class _ProcessorA(HeaderProcessor):
    namespace = "pytest"
    local_key = "shared"


class _ProcessorB(HeaderProcessor):
    namespace = "pytest"
    local_key = "shared"


_CACHED_BUILDERS = (
    instances.get_base_processor_binding_registry,
    instances.get_base_processor_definition_registry,
    instances.get_base_header_processor_registry,
)


@pytest.fixture(autouse=True)
def _isolate_processor_instance_caches() -> Iterator[None]:
    """Clear all patched composition state before and after every test."""
    for builder in _CACHED_BUILDERS:
        builder.cache_clear()
    try:
        yield
    finally:
        for builder in _CACHED_BUILDERS:
            builder.cache_clear()


def _binding(file_type_name: str, processor_class: type[HeaderProcessor]) -> ProcessorBinding:
    return ProcessorBinding(
        file_type_name=file_type_name,
        processor_class=processor_class,
        namespace="pytest",
    )


def _patch_composition(
    monkeypatch: MonkeyPatch,
    *,
    filetypes: dict[str, FileType],
    bindings: tuple[ProcessorBinding, ...],
) -> None:
    monkeypatch.setattr(
        "topmark.filetypes.instances.get_base_file_type_registry",
        lambda: filetypes,
    )
    monkeypatch.setattr(instances, "get_builtin_processor_bindings", lambda: bindings)


def test_cached_base_registry_values_are_shared_and_documented_as_read_only() -> None:
    """Base helper caches return shared mappings, including legacy instances."""
    bindings: dict[str, str] = instances.get_base_processor_binding_registry()
    definitions: dict[str, ProcessorDefinition] = instances.get_base_processor_definition_registry()
    legacy: dict[str, HeaderProcessor] = instances.get_base_header_processor_registry()

    assert instances.get_base_processor_binding_registry() is bindings
    assert instances.get_base_processor_definition_registry() is definitions
    assert instances.get_base_header_processor_registry() is legacy


def test_composition_uses_qualified_keys_but_legacy_instances_use_local_keys(
    monkeypatch: MonkeyPatch,
) -> None:
    """Definitions/bindings use canonical identity while legacy keys stay compatible."""
    alpha: FileType = make_file_type(local_key="alpha")
    beta: FileType = make_file_type(local_key="beta")
    bindings: tuple[ProcessorBinding, ProcessorBinding] = (
        _binding("alpha", _ProcessorA),
        _binding("beta", _ProcessorA),
    )
    _patch_composition(
        monkeypatch,
        filetypes={alpha.qualified_key: alpha, beta.qualified_key: beta},
        bindings=bindings,
    )

    binding_registry: dict[str, str] = instances.get_base_processor_binding_registry()
    definition_registry: dict[str, ProcessorDefinition] = (
        instances.get_base_processor_definition_registry()
    )
    legacy_registry: dict[str, HeaderProcessor] = instances.get_base_header_processor_registry()

    assert binding_registry == {
        alpha.qualified_key: "pytest:shared",
        beta.qualified_key: "pytest:shared",
    }
    assert list(definition_registry) == ["pytest:shared"]
    assert list(legacy_registry) == ["alpha", "beta"]
    assert legacy_registry["alpha"] is not legacy_registry["beta"]
    assert legacy_registry["alpha"].file_type is alpha
    assert legacy_registry["beta"].file_type is beta


def test_duplicate_file_type_local_identity_is_rejected(monkeypatch: MonkeyPatch) -> None:
    """Composition cannot choose between distinct file types sharing a local key."""
    first: FileType = make_file_type(local_key="duplicate", namespace="pytest")
    second: FileType = make_file_type(local_key="duplicate", namespace="plugin")
    _patch_composition(
        monkeypatch,
        filetypes={first.qualified_key: first, second.qualified_key: second},
        bindings=(),
    )

    with pytest.raises(ProcessorBindingError, match="Duplicate file type local key"):
        instances.get_base_processor_binding_registry()


@pytest.mark.parametrize(
    "builder",
    [
        instances.get_base_processor_binding_registry,
        instances.get_base_header_processor_registry,
    ],
)
def test_unknown_file_type_binding_is_rejected(
    monkeypatch: MonkeyPatch,
    builder: Callable[[], object],
) -> None:
    """Both canonical and legacy composition reject unknown declarations."""
    _patch_composition(
        monkeypatch,
        filetypes={},
        bindings=(_binding("missing", _ProcessorA),),
    )

    with pytest.raises(ProcessorBindingError, match="Unknown file type"):
        builder()


@pytest.mark.parametrize(
    "builder",
    [
        instances.get_base_processor_binding_registry,
        instances.get_base_header_processor_registry,
    ],
)
def test_duplicate_file_type_binding_is_rejected(
    monkeypatch: MonkeyPatch,
    builder: Callable[[], object],
) -> None:
    """One file type cannot receive two built-in processor bindings."""
    file_type: FileType = make_file_type(local_key="alpha")
    _patch_composition(
        monkeypatch,
        filetypes={file_type.qualified_key: file_type},
        bindings=(
            _binding("alpha", _ProcessorA),
            _binding("alpha", _ProcessorA),
        ),
    )

    with pytest.raises(ProcessorBindingError, match="Duplicate processor binding"):
        builder()


def test_conflicting_processor_classes_for_one_identity_are_rejected(
    monkeypatch: MonkeyPatch,
) -> None:
    """Definition composition rejects conflicting classes with one qualified key."""
    _patch_composition(
        monkeypatch,
        filetypes={},
        bindings=(
            _binding("alpha", _ProcessorA),
            _binding("beta", _ProcessorB),
        ),
    )

    with pytest.raises(ProcessorBindingError, match="Duplicate processor definition"):
        instances.get_base_processor_definition_registry()


def test_repeated_compatible_processor_definitions_reuse_one_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    """Compatible repeated bindings compose one deterministic definition."""
    bindings: tuple[ProcessorBinding, ProcessorBinding] = (
        _binding("alpha", _ProcessorA),
        _binding("beta", _ProcessorA),
    )
    _patch_composition(monkeypatch, filetypes={}, bindings=bindings)

    registry: dict[str, ProcessorDefinition] = instances.get_base_processor_definition_registry()

    assert list(registry) == ["pytest:shared"]
    assert registry["pytest:shared"].processor_class is _ProcessorA


@pytest.mark.parametrize(
    "binding",
    instances.get_builtin_processor_bindings(),
    ids=lambda binding: f"{binding.file_type_name}->{binding.processor_class.local_key}",
)
def test_builtin_binding_resolves_to_its_declared_filetype_and_processor(
    binding: ProcessorBinding,
) -> None:
    """Each declarative built-in binding resolves through every registry layer."""
    filetypes: dict[str, FileType] = get_base_file_type_registry()
    bindings: dict[str, str] = instances.get_base_processor_binding_registry()
    definitions: dict[str, ProcessorDefinition] = instances.get_base_processor_definition_registry()

    filetype: FileType = filetypes[binding.file_type_name]
    processor_key: str = make_qualified_key(
        namespace=binding.namespace,
        local_key=binding.processor_class.local_key,
    )

    assert bindings[filetype.qualified_key] == processor_key
    assert definitions[processor_key].processor_class is binding.processor_class


_XML_BUILTIN_BINDINGS: tuple[ProcessorBinding, ...] = tuple(
    binding
    for binding in instances.get_builtin_processor_bindings()
    if issubclass(binding.processor_class, XmlHeaderProcessor)
)


@pytest.mark.parametrize(
    "binding",
    _XML_BUILTIN_BINDINGS,
    ids=lambda binding: binding.file_type_name,
)
def test_xml_builtin_bindings_use_character_offset_placement(
    binding: ProcessorBinding,
) -> None:
    """XML-family built-in bindings must opt out of line-based placement."""
    processor: HeaderProcessor = binding.processor_class()

    assert processor.get_header_insertion_index(["<root/>"]) == NO_LINE_ANCHOR
