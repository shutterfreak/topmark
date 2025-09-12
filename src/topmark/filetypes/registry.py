# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : src/topmark/filetypes/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Registry of HeaderProcessors for TopMark file types.

This module provides a decorator to register HeaderProcessor implementations
for specific file types, using the centralized file_type_registry.

Each HeaderProcessor is associated with a FileType by name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.filetypes.instances import get_file_type_registry

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.pipeline.processors.base import HeaderProcessor

logger = get_logger(__name__)


_registry: dict[str, HeaderProcessor] = {}


def register_filetype(
    name: str,
) -> Callable[[type[HeaderProcessor]], type[HeaderProcessor]]:
    """Class decorator to register a HeaderProcessor for a specific file type.

    Args:
        name (str): Name of the file type as defined in file_type_registry.

    Returns:
        Callable[[type[HeaderProcessor]], type[HeaderProcessor]]: A decorator that
            registers the class as a HeaderProcessor.

    Raises:
        ValueError: If the file type name is unknown or already registered.
    """
    file_type_registry = get_file_type_registry()
    if name not in file_type_registry:
        raise ValueError(f"Unknown file type: {name}")

    file_type = file_type_registry[name]

    def decorator(cls: type[HeaderProcessor]) -> type[HeaderProcessor]:
        """Decorator function that registers the processor class with the given extension.

        Each HeaderProcessor is instantiated and bound to a specific FileType at registration time.
        This instance-level registration ensures that processor.file_type is set correctly,
        even if multiple file types reuse the same processor class.
        See also resolver.py for where this linkage is relied upon.

        Args:
            cls (type[HeaderProcessor]): The class to register as a header processor.

        Raises:
            ValueError: If a `FileType` is already registered to a `HeaderProcessor`.

        Returns:
            type[HeaderProcessor]: The decorated HeaderProcessor instance.
        """
        logger.debug("Registering processor %s for file type: %s", cls.__name__, file_type.name)
        if file_type.name in _registry:
            raise ValueError(f"File type '{file_type.name}' already has a registered processor.")
        instance = cls()
        instance.file_type = file_type
        _registry[file_type.name] = instance
        return cls

    return decorator


def get_header_processor_registry() -> dict[str, HeaderProcessor]:
    """Return the registry of file type names to HeaderProcessor instances."""
    return _registry
