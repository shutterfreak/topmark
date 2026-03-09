# topmark:header:start
#
#   project      : TopMark
#   file         : instances.py
#   file_relpath : src/topmark/processors/instances.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Explicit built-in processor bindings for the base processor registry.

This module declares the built-in mapping from file type names to concrete
[`HeaderProcessor`][topmark.processors.base.HeaderProcessor] classes using
[`ProcessorBinding`][topmark.processors.bindings.ProcessorBinding] value
objects.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING
from typing import Final

from topmark.constants import TOPMARK_NAMESPACE
from topmark.core.errors import ProcessorBindingError
from topmark.processors.base import HeaderProcessor
from topmark.processors.bindings import ProcessorBinding
from topmark.processors.bindings import bindings_for
from topmark.processors.builtins.cblock import CBlockHeaderProcessor
from topmark.processors.builtins.markdown import MarkdownHeaderProcessor
from topmark.processors.builtins.pound import PoundHeaderProcessor
from topmark.processors.builtins.slash import SlashHeaderProcessor
from topmark.processors.builtins.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor

# Declarative built-in processor bindings used to construct the base registry.
_BUILTIN_PROCESSOR_BINDINGS: Final[tuple[ProcessorBinding, ...]] = (
    *bindings_for(
        processor_class=CBlockHeaderProcessor,
        namespace=TOPMARK_NAMESPACE,
        file_type_names=[
            "css",
            "less",
            "scss",
            "solidity",
            "sql",
            "stylus",
        ],
    ),
    *bindings_for(
        processor_class=MarkdownHeaderProcessor,
        namespace=TOPMARK_NAMESPACE,
        file_type_names=[
            "markdown",
        ],
    ),
    *bindings_for(
        processor_class=PoundHeaderProcessor,
        namespace=TOPMARK_NAMESPACE,
        file_type_names=[
            "dockerfile",
            "env",
            "git-meta",
            "ini",
            "julia",
            "makefile",
            "perl",
            "python",
            "python-requirements",
            "python-stub",
            "r",
            "ruby",
            "shell",
            "toml",
            "yaml",
        ],
    ),
    *bindings_for(
        processor_class=SlashHeaderProcessor,
        namespace=TOPMARK_NAMESPACE,
        file_type_names=[
            "c",
            "cpp",
            "cs",
            "go",
            "java",
            "javascript",
            "jsonc",
            "kotlin",
            "rust",
            "swift",
            "typescript",
            "vscode-jsonc",
        ],
    ),
    *bindings_for(
        processor_class=XmlHeaderProcessor,
        namespace=TOPMARK_NAMESPACE,
        file_type_names=[
            "html",
            "svelte",
            "svg",
            "vue",
            "xhtml",
            "xml",
            "xsl",
            "xslt",
        ],
    ),
)


def get_builtin_processor_bindings() -> tuple[ProcessorBinding, ...]:
    """Return the explicit built-in processor bindings in declaration order."""
    return _BUILTIN_PROCESSOR_BINDINGS


def _build_processor(binding: ProcessorBinding, file_type: FileType) -> HeaderProcessor:
    """Instantiate and bind a processor for a resolved file type.

    Args:
        binding: Declarative processor binding describing which processor class
            should be instantiated.
        file_type: Resolved `FileType` instance to bind to the processor.

    Returns:
        A freshly-instantiated `HeaderProcessor` bound to `file_type`.
    """
    processor: HeaderProcessor = binding.processor_class()
    processor.file_type = file_type
    return processor


@lru_cache(maxsize=1)
def get_base_header_processor_registry() -> dict[str, HeaderProcessor]:
    """Build and cache the base processor registry from explicit bindings.

    The returned mapping is keyed by file type name and contains ready-to-use
    `HeaderProcessor` instances already bound to the corresponding base
    [`FileType`][topmark.filetypes.model.FileType].

    Returns:
        Base mapping of file type names to bound `HeaderProcessor` instances.

    Raises:
        ProcessorBindingError: If a binding references an unknown file type
            name or if multiple bindings target the same file type name.
    """
    from topmark.filetypes.instances import get_base_file_type_registry

    ft_registry: dict[str, FileType] = get_base_file_type_registry()
    registry: dict[str, HeaderProcessor] = {}

    for binding in get_builtin_processor_bindings():
        file_type_name: str = binding.file_type_name
        file_type: FileType | None = ft_registry.get(file_type_name)
        if file_type is None:
            raise ProcessorBindingError(
                message=f"Unknown file type in processor binding: {file_type_name}",
                file_type=file_type_name,
            )
        if file_type_name in registry:
            raise ProcessorBindingError(
                message=f"Duplicate processor binding for file type: {file_type_name}",
                file_type=file_type_name,
            )
        registry[file_type_name] = _build_processor(binding, file_type)

    return registry
