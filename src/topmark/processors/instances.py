# topmark:header:start
#
#   project      : TopMark
#   file         : instances.py
#   file_relpath : src/topmark/processors/instances.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Declarative built-in processor definitions and binding-derived base registries.

This module centralizes TopMark's built-in processor binding declarations and
provides helpers that materialize those declarations into base registries for
bindings, processor definitions, and legacy bound processor instances.
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
from topmark.registry.identity import make_qualified_key
from topmark.registry.types import ProcessorDefinition

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
    """Return the explicit built-in processor bindings in declaration order.

    Returns:
        Tuple of built-in [`ProcessorBinding`][topmark.processors.bindings.ProcessorBinding]
        declarations.
    """
    return _BUILTIN_PROCESSOR_BINDINGS


@lru_cache(maxsize=1)
def get_base_processor_binding_registry() -> dict[str, str]:
    """Build and cache the base binding registry from explicit declarations.

    The returned mapping is keyed by file type qualified key and stores the
    bound processor qualified key as its value.

    Returns:
        Base mapping of file type qualified key to processor qualified key.

    Raises:
        ProcessorBindingError: If a binding references an unknown file type or
            if multiple bindings target the same file type qualified key.
    """
    from topmark.filetypes.instances import get_base_file_type_registry

    ft_registry: dict[str, FileType] = get_base_file_type_registry()
    registry: dict[str, str] = {}

    for binding in get_builtin_processor_bindings():
        file_type_name: str = binding.file_type_name
        file_type: FileType | None = ft_registry.get(file_type_name)
        if file_type is None:
            raise ProcessorBindingError(
                message=f"Unknown file type in processor binding: {file_type_name}",
                file_type=file_type_name,
            )

        filetype_qualified_key: str = file_type.qualified_key
        processor_qualified_key: str = make_qualified_key(
            namespace=binding.namespace,
            local_key=binding.processor_class.local_key,
        )

        if filetype_qualified_key in registry:
            raise ProcessorBindingError(
                message=(
                    "Duplicate processor binding for file type qualified key: "
                    f"{filetype_qualified_key}"
                ),
                file_type=filetype_qualified_key,
            )

        registry[filetype_qualified_key] = processor_qualified_key

    return registry


@lru_cache(maxsize=1)
def get_base_processor_definition_registry() -> dict[str, ProcessorDefinition]:
    """Build and cache the base processor-definition registry.

    The returned mapping is keyed by processor qualified key. Values are
    processor definitions derived directly from the explicit built-in processor
    bindings.

    Returns:
        Base mapping of processor qualified key to `ProcessorDefinition`.

    Raises:
        ProcessorBindingError: If multiple built-in bindings resolve to the same
            processor qualified key but reference different processor classes.
    """
    registry: dict[str, ProcessorDefinition] = {}

    for binding in get_builtin_processor_bindings():
        proc_def = ProcessorDefinition(
            namespace=binding.namespace,
            local_key=binding.processor_class.local_key,
            processor_class=binding.processor_class,
        )
        qualified_key: str = proc_def.qualified_key
        existing: ProcessorDefinition | None = registry.get(qualified_key)
        if existing is not None and existing.processor_class is not proc_def.processor_class:
            raise ProcessorBindingError(
                message=(f"Duplicate processor definition for qualified key: {qualified_key}"),
                file_type=qualified_key,
            )
        registry[qualified_key] = proc_def

    return registry


def _build_processor(binding: ProcessorBinding, file_type: FileType) -> HeaderProcessor:
    """Instantiate and bind a processor for a resolved file type.

    Args:
        binding: Declarative processor binding describing the processor class to instantiate.
        file_type: Resolved `FileType` instance to bind to the processor.

    Returns:
        Fresh `HeaderProcessor` instance bound to `file_type`.
    """
    processor: HeaderProcessor = binding.processor_class()
    processor.file_type = file_type
    return processor


@lru_cache(maxsize=1)
def get_base_header_processor_registry() -> dict[str, HeaderProcessor]:
    """Build and cache the legacy base processor registry of bound instances.

    Notes:
        This helper exists for compatibility with older resolution paths that
        still expect ready-to-use bound processor instances. New registry code
        should prefer `get_base_processor_definition_registry()` together with
        `get_base_processor_binding_registry()`.

    Returns:
        Base mapping of file type local key to bound `HeaderProcessor` instances.

    Raises:
        ProcessorBindingError: If a binding references an unknown file type or
            if multiple bindings target the same file type local key.
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
