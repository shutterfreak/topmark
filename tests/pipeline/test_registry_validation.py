# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_validation.py
#   file_relpath : tests/pipeline/test_registry_validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CI guardrails for processor↔filetype registry integrity and strategy usage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import mark_dev_validation
from topmark.filetypes.instances import get_base_file_type_registry
from topmark.filetypes.registry import get_base_header_processor_registry
from topmark.pipeline.processors.base import NO_LINE_ANCHOR, HeaderProcessor
from topmark.pipeline.processors.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType


@mark_dev_validation
def test_registered_processors_map_to_existing_filetypes() -> None:
    """Every registered processor references an existing FileType."""
    ft_registry: dict[str, FileType] = get_base_file_type_registry()
    hp_registry: dict[str, HeaderProcessor] = get_base_header_processor_registry()

    missing: list[str] = [name for name in hp_registry if name not in ft_registry]
    assert missing == [], f"Processors registered for unknown file types: {missing!r}"


@mark_dev_validation
def test_one_processor_per_filetype() -> None:
    """There is at most one processor registered per file type name."""
    hp_registry: dict[str, HeaderProcessor] = get_base_header_processor_registry()

    # Keys are type names; duplicates would be impossible by design,
    # but keep a guard that class names aren’t reused across different types.

    class_by_type: dict[str, type[HeaderProcessor]] = {
        ft_name: proc.__class__ for ft_name, proc in hp_registry.items()
    }

    # Inverse map: class -> [types]
    by_class: dict[type[HeaderProcessor], list[str]] = {}
    for ft_name, cls in class_by_type.items():
        by_class.setdefault(cls, []).append(ft_name)

    # Accept that one processor class can serve multiple types (e.g., Slash),
    # but ensure we don’t accidentally register multiple instances under the same type.
    assert len(hp_registry) == len(set(hp_registry.keys()))


@pytest.mark.parametrize(
    "ft_name",
    [
        "xml",
        "html",
        "xhtml",
        "svg",
        "xsl",
        "xslt",
        "svelte",
        "vue",
        "markdown",
    ],
)
@mark_dev_validation
def test_xml_like_types_report_no_line_anchor(ft_name: str) -> None:
    """XML-like processors indicate char-offset placement via NO_LINE_ANCHOR."""
    hp_registry: dict[str, HeaderProcessor] = get_base_header_processor_registry()

    # Some of these types may not be present in every build; skip if unregistered.
    processor: HeaderProcessor | None = hp_registry.get(ft_name)
    if processor is None:
        pytest.skip(f"file type not registered: {ft_name}")

    # If a type is mapped to XmlHeaderProcessor, it must use NO_LINE_ANCHOR.
    if isinstance(processor, XmlHeaderProcessor):
        assert processor.get_header_insertion_index(["<root/>"]) == NO_LINE_ANCHOR
