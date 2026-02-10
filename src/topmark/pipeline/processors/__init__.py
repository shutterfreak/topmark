# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/pipeline/processors/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Auto-import all processor modules in the current package."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.filetypes.base import FileType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.config.logging import TopmarkLogger
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)


def get_processor_for_file(path: Path) -> HeaderProcessor | None:
    """Retrieve the appropriate header processor for a given file based on its extension.

    Args:
        path: The path to the file for which to find a processor.

    Returns:
       An instance of a registered HeaderProcessor if a matching processor is found, or `None` if
       no processor is registered for the file's extension.
    """
    from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

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

    # Get the file type based on file name
    file_type: FileType | None = None

    # Look up the
    for file_type_name, processor in hp_registry.items():
        logger.trace("Resolving '%s' type to '%s'", path, file_type_name)
        file_type = ft_registry.get(file_type_name)
        if not file_type:
            logger.warning(
                "No FileType found for registered processor '%s'",
                processor.__class__.__name__,
            )
            continue

        logger.trace("Checking %s against %s", path, file_type.name)
        if file_type.matches(path):
            logger.debug("File type '%s' detected for file: %s", file_type.name, path)
            if processor:
                return processor

    if file_type:
        logger.warning(
            "File '%s' is resolved to file type '%s' but has no regsitered header processor",
            path,
            file_type.name,
        )
    else:
        logger.warning("File '%s' cannot be resolved to a registered file type", path)
    return None


_PROCESSORS_LOADED = False  # Module-level flag


# Dynamically import all modules in the processors/ directory
def register_all_processors() -> None:
    """Import all processor modules in the current package (Idempotent)."""
    global _PROCESSORS_LOADED

    if _PROCESSORS_LOADED:
        return

    package_dir: Path = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if not module_info.ispkg:
            # Import the module to ensure it registers its processor
            logger.debug("Loading %s.%s", __name__, module_info.name)
            importlib.import_module(f"{__name__}.{module_info.name}")
