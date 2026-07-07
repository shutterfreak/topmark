# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_types.py
#   file_relpath : tests/registry/test_registry_types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for registry metadata and definition value objects."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from topmark.processors.base import HeaderProcessor
from topmark.registry.types import FileTypeMeta
from topmark.registry.types import ProcessorDefinition
from topmark.registry.types import ProcessorMeta


def test_filetype_meta_exposes_qualified_key_and_default_metadata() -> None:
    """File type metadata should expose stable defaults and canonical identity."""
    meta = FileTypeMeta(namespace="pytest", local_key="sample")

    assert meta.qualified_key == "pytest:sample"
    assert meta.description == ""
    assert meta.extensions == ()
    assert meta.filenames == ()
    assert meta.patterns == ()
    assert meta.skip_processing is False
    assert meta.content_matcher is False
    assert meta.header_policy == {}


def test_filetype_meta_header_policy_default_is_not_shared() -> None:
    """Header policy defaults should be independent mutable payloads."""
    first = FileTypeMeta(namespace="pytest", local_key="first")
    second = FileTypeMeta(namespace="pytest", local_key="second")

    first.header_policy["allow_header_in_empty_files"] = True

    assert first.header_policy == {"allow_header_in_empty_files": True}
    assert second.header_policy == {}


def test_filetype_meta_preserves_explicit_metadata_payloads() -> None:
    """File type metadata should preserve explicit serializable payload fields."""
    header_policy: dict[str, object] = {"allow_content_probe": False}
    meta = FileTypeMeta(
        namespace="pytest",
        local_key="rich",
        description="rich file type",
        extensions=(".rich",),
        filenames=("Richfile",),
        patterns=("*.rich",),
        skip_processing=True,
        content_matcher=True,
        header_policy=header_policy,
    )

    assert meta.qualified_key == "pytest:rich"
    assert meta.description == "rich file type"
    assert meta.extensions == (".rich",)
    assert meta.filenames == ("Richfile",)
    assert meta.patterns == ("*.rich",)
    assert meta.skip_processing is True
    assert meta.content_matcher is True
    assert meta.header_policy is header_policy


def test_processor_meta_exposes_qualified_key_and_default_presentation_fields() -> None:
    """Processor metadata should expose stable defaults and canonical identity."""
    meta = ProcessorMeta(namespace="pytest", local_key="sample")

    assert meta.qualified_key == "pytest:sample"
    assert meta.description == ""
    assert meta.block_prefix == ""
    assert meta.block_suffix == ""
    assert meta.line_indent == ""
    assert meta.line_prefix == ""
    assert meta.line_suffix == ""


def test_processor_meta_preserves_explicit_presentation_fields() -> None:
    """Processor metadata should preserve explicit presentation fields."""
    meta = ProcessorMeta(
        namespace="pytest",
        local_key="rich",
        description="rich processor",
        block_prefix="/*",
        block_suffix="*/",
        line_indent="  ",
        line_prefix="* ",
        line_suffix=" !",
    )

    assert meta.qualified_key == "pytest:rich"
    assert meta.description == "rich processor"
    assert meta.block_prefix == "/*"
    assert meta.block_suffix == "*/"
    assert meta.line_indent == "  "
    assert meta.line_prefix == "* "
    assert meta.line_suffix == " !"


def test_processor_definition_exposes_qualified_key_and_processor_class() -> None:
    """Processor definitions should preserve identity and implementation class."""

    class RegistryTypesProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "registry_types_processor"

    definition = ProcessorDefinition(
        namespace="pytest",
        local_key="registry_types_processor",
        processor_class=RegistryTypesProcessor,
    )

    assert definition.qualified_key == "pytest:registry_types_processor"
    assert definition.processor_class is RegistryTypesProcessor


@pytest.mark.parametrize(
    "value",
    [
        FileTypeMeta(namespace="pytest", local_key="frozen_filetype"),
        ProcessorMeta(namespace="pytest", local_key="frozen_processor"),
    ],
)
def test_registry_metadata_objects_are_frozen_and_slotted(
    value: FileTypeMeta | ProcessorMeta,
) -> None:
    """Registry metadata value objects should be immutable and slotted."""
    with pytest.raises(FrozenInstanceError):
        setattr(value, "local_key", "changed")  # noqa: B010

    assert not hasattr(value, "__dict__")


def test_processor_definition_is_frozen_and_slotted() -> None:
    """Processor definitions should be immutable and slotted."""

    class FrozenDefinitionProcessor(HeaderProcessor):
        namespace = "pytest"
        local_key = "frozen_definition_processor"

    definition = ProcessorDefinition(
        namespace="pytest",
        local_key="frozen_definition_processor",
        processor_class=FrozenDefinitionProcessor,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(definition, "local_key", "changed")  # noqa: B010

    assert not hasattr(definition, "__dict__")
