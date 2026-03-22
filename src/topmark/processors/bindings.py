# topmark:header:start
#
#   project      : TopMark
#   file         : bindings.py
#   file_relpath : src/topmark/processors/bindings.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Declarative built-in processor binding helpers.

This module defines small value objects and expansion helpers used to declare
how [`HeaderProcessor`][topmark.processors.base.HeaderProcessor]
implementations are associated with file type names in TopMark's built-in
registry data.

The bindings are intentionally declarative: they describe built-in registry
contents without relying on import-time decorator side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.processors.base import HeaderProcessor


@dataclass(frozen=True, kw_only=True)
class ProcessorBinding:
    """Declarative association between one file type name and one processor class.

    ``kw_only=True`` keeps call sites explicit and readable when many bindings
    are declared together.

    Attributes:
        file_type_name: Local key of the file type the processor should be bound to.
        processor_class: Concrete `HeaderProcessor` class associated with that file type.
        namespace: Namespace label identifying the binding source, usually the
            built-in TopMark namespace or a plugin namespace.
    """

    file_type_name: str
    processor_class: type[HeaderProcessor]
    namespace: str


def bindings_for(
    processor_class: type[HeaderProcessor],
    file_type_names: Iterable[str],
    *,
    namespace: str,
) -> tuple[ProcessorBinding, ...]:
    """Expand one processor class across multiple file type names.

    Args:
        processor_class: Concrete `HeaderProcessor` class to bind.
        file_type_names: File type local keys that should resolve to the same
            processor class.
        namespace: Namespace label identifying the binding source.

    Returns:
        Tuple of [`ProcessorBinding`][topmark.processors.bindings.ProcessorBinding]
        objects preserving the input order of `file_type_names`.
    """
    return tuple(
        ProcessorBinding(
            file_type_name=file_type_name,
            processor_class=processor_class,
            namespace=namespace,
        )
        for file_type_name in file_type_names
    )
