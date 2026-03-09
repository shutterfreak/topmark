# topmark:header:start
#
#   project      : TopMark
#   file         : resolver.py
#   file_relpath : src/topmark/registry/resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Path-to-processor resolution against the composed registries.

This module resolves a concrete file path to the first registered
[`HeaderProcessor`][topmark.processors.base.HeaderProcessor] whose associated
[`FileType`][topmark.filetypes.model.FileType] matches that path.

Resolution is performed against the effective public registries exposed by
[`topmark.registry.filetypes.FileTypeRegistry`][topmark.registry.filetypes.FileTypeRegistry]
and
[`topmark.registry.processors.HeaderProcessorRegistry`][topmark.registry.processors.HeaderProcessorRegistry],
not directly against the internal base registries used to construct the composed public views. This
ensures overlay registrations and removals performed through the public registry layer are honored
during lookup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)


def get_processor_for_file(path: Path) -> HeaderProcessor | None:
    """Return the first registered processor whose file type matches `path`.

    The processor registry is keyed by file type name. For each registered
    processor in the composed processor view, this helper looks up the
    corresponding composed [`FileType`][topmark.filetypes.model.FileType] and
    evaluates `matches(path)`.

    The local `file_type_lookup` variable represents the current registry entry
    under inspection. The outer `file_type` variable is only populated when a
    candidate actually matches `path`. This preserves correct end-of-scan
    diagnostics: if no match is found, the helper must not report the file as
    resolved to whichever file type happened to be visited last.

    Args:
        path: File path to resolve against the effective registered file types.

    Returns:
        The matching registered processor, or `None` when the path does not
        resolve to any registered file type or when the resolved file type has
        no processor.
    """
    from topmark.registry.filetypes import FileTypeRegistry
    from topmark.registry.processors import HeaderProcessorRegistry

    # Use the composed public registries so overlays and removals are respected.
    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    hp_registry: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()

    logger.debug("Looking up file type for file '%s'", path)
    logger.debug(
        "  %3d registered file types: %s",
        len(ft_registry),
        ", ".join(sorted(ft_registry.keys())),
    )
    header_processor_list: list[str] = sorted(
        {processor.__class__.__name__ for processor in hp_registry.values()},
    )
    logger.debug(
        "  %3d registered header processors: %s",
        len(header_processor_list),
        ", ".join(header_processor_list),
    )
    logger.trace("header_processor_registry: %s", hp_registry)

    # Track the file type that actually matched `path`, if any.
    file_type: FileType | None = None

    # Scan the composed processor registry and test the corresponding file type for each entry.
    for file_type_name, processor in hp_registry.items():
        file_type_lookup: FileType | None = ft_registry.get(file_type_name)
        if not file_type_lookup:
            logger.warning(
                "No FileType found for registered processor '%s'",
                processor.__class__.__name__,
            )
            continue

        # Only persist the resolved file type when this concrete candidate matches.
        if file_type_lookup.matches(path):
            file_type = file_type_lookup
            logger.debug("File type '%s' detected for file: %s", file_type_lookup.name, path)
            if processor:
                return processor

    # Emit a precise diagnostic based on whether any file type matched at all.
    if file_type:
        logger.warning(
            "File '%s' is resolved to file type '%s' but has no registered header processor",
            path,
            file_type.name,
        )
    else:
        logger.warning("File '%s' cannot be resolved to a registered file type", path)
    return None
