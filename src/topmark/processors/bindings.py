# topmark:header:start
#
#   project      : TopMark
#   file         : bindings.py
#   file_relpath : src/topmark/processors/bindings.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Declarative processor-to-file-type bindings.

This module defines small value objects and helpers used to declare how
[`HeaderProcessor`][topmark.processors.base.HeaderProcessor] implementations
should be bound to file type names when constructing the base processor
registry.

These bindings are intentionally declarative: they describe registry contents
without relying on import-time decorator side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.processors.base import HeaderProcessor


@dataclass(frozen=True, kw_only=True)
class ProcessorBinding:
    """Declarative binding from a file type name to a processor class.

    `kw_only=True` ensures call sites remain explicit and readable when
    constructing bindings, especially when multiple bindings are declared
    in processor instance lists.

    Attributes:
        file_type_name: Name of the file type the processor should be bound to.
        processor_class: Concrete `HeaderProcessor` class to instantiate for
            that file type.
        namespace: Namespace label identifying the binding source, typically the
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
        file_type_names: Iterable of file type names that should resolve to the
            same processor class.
        namespace: Namespace label identifying the binding source.

    Returns:
        Tuple of [`ProcessorBinding`][topmark.processors.bindings.ProcessorBinding]
        objects, preserving the input order of `file_type_names`.
    """
    return tuple(
        ProcessorBinding(
            file_type_name=file_type_name,
            processor_class=processor_class,
            namespace=namespace,
        )
        for file_type_name in file_type_names
    )
