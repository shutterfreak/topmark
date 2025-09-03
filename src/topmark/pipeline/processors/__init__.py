# topmark:header:start
#
#   file         : __init__.py
#   file_relpath : src/topmark/pipeline/processors/__init__.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Auto-import all processor modules in the current package."""

import importlib
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from topmark.filetypes.base import FileType


logger = get_logger(__name__)


def get_processor_for_file(path: Path) -> HeaderProcessor | None:
    """Retrieve the appropriate header processor for a given file based on its extension.

    Args:
        path: The path to the file for which to find a processor.

    Returns:
        An instance of a registered HeaderProcessor if a matching processor is found,
        or None if no processor is registered for the file's extension.
    """
    from topmark.filetypes.instances import get_file_type_registry
    from topmark.filetypes.registry import get_header_processor_registry

    file_type_registry = get_file_type_registry()
    header_processor_registry = get_header_processor_registry()

    logger.debug("Looking up file type for file '%s'", path)
    logger.debug(
        "  %3d registered file types: %s",
        len(file_type_registry),
        ", ".join(sorted(file_type_registry.keys())),
    )
    header_processor_list = sorted(
        set(processor.__class__.__name__ for processor in header_processor_registry.values()),
    )
    logger.debug(
        "  %3d registered header processors: %s",
        len(header_processor_list),
        ", ".join(header_processor_list),
    )
    logger.trace("header_processor_registry: %s", header_processor_registry)

    # Get the file type based on file name
    file_type: FileType | None = None

    # Look up the
    for file_type_name, processor in header_processor_registry.items():
        logger.trace("Resolving '%s' type to '%s'", path, file_type_name)
        file_type = file_type_registry.get(file_type_name)
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


# Dynamically import all modules in the processors/ directory
def register_all_processors() -> None:
    """Import all processor modules in the current package."""
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if not module_info.ispkg:
            # Import the module to ensure it registers its processor
            importlib.import_module(f"{__name__}.{module_info.name}")
