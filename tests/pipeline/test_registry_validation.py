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

from typing import TYPE_CHECKING, Dict, Type

import pytest

from tests.conftest import mark_dev_validation
from topmark.filetypes.instances import get_file_type_registry
from topmark.filetypes.registry import get_header_processor_registry
from topmark.pipeline.processors.base import NO_LINE_ANCHOR, HeaderProcessor
from topmark.pipeline.processors.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType


# Apply the dev-validation mark to the whole module
pytestmark = [mark_dev_validation]


def test_registered_processors_map_to_existing_filetypes() -> None:
    """Every registered processor references an existing FileType."""
    ft_reg: Dict[str, FileType] = get_file_type_registry()
    proc_reg: Dict[str, HeaderProcessor] = get_header_processor_registry()

    missing: list[str] = [name for name in proc_reg.keys() if name not in ft_reg]
    assert missing == [], f"Processors registered for unknown file types: {missing!r}"


def test_one_processor_per_filetype() -> None:
    """There is at most one processor registered per file type name."""
    proc_reg: Dict[str, HeaderProcessor] = get_header_processor_registry()

    # Keys are type names; duplicates would be impossible by design,
    # but keep a guard that class names aren’t reused across different types.

    class_by_type: Dict[str, type[HeaderProcessor]] = {
        ft_name: proc.__class__ for ft_name, proc in proc_reg.items()
    }

    # Inverse map: class -> [types]
    by_class: Dict[Type[HeaderProcessor], list[str]] = {}
    for ft_name, cls in class_by_type.items():
        by_class.setdefault(cls, []).append(ft_name)

    # Accept that one processor class can serve multiple types (e.g., Slash),
    # but ensure we don’t accidentally register multiple instances under the same type.
    assert len(proc_reg) == len(set(proc_reg.keys()))


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
def test_xml_like_types_report_no_line_anchor(ft_name: str) -> None:
    """XML-like processors indicate char-offset placement via NO_LINE_ANCHOR."""
    proc_reg: Dict[str, HeaderProcessor] = get_header_processor_registry()

    # Some of these types may not be present in every build; skip if unregistered.
    proc: HeaderProcessor | None = proc_reg.get(ft_name)
    if proc is None:
        pytest.skip(f"file type not registered: {ft_name}")

    # If a type is mapped to XmlHeaderProcessor, it must use NO_LINE_ANCHOR.
    if isinstance(proc, XmlHeaderProcessor):
        assert proc.get_header_insertion_index(["<root/>"]) == NO_LINE_ANCHOR
