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

Notes:
    This module maintains the *base* processor registry populated by
    decorators during import/discovery. For the effective, user-facing
    composed view (base + overlays − removals), use
    [`topmark.registry.processors.HeaderProcessorRegistry.as_mapping`][].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.filetypes.base import FileType
from topmark.pipeline.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from topmark.config.logging import TopmarkLogger
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor

logger: TopmarkLogger = get_logger(__name__)

_registry: dict[str, HeaderProcessor] = {}


def register_filetype(
    name: str,
) -> Callable[[type[HeaderProcessor]], type[HeaderProcessor]]:
    """Class decorator to register a HeaderProcessor for a specific file type.

    Args:
        name: File type identifier under which the processor is registered.

    Returns:
        A decorator that registers the class as a HeaderProcessor.

    Raises:
        ValueError: If the file type name is unknown or already registered.
    """
    # Validate against the *effective* registry (composed base + overlays).
    from topmark.registry import FileTypeRegistry

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()
    if name not in ft_registry:
        raise ValueError(f"Unknown file type: {name}")

    file_type: FileType = ft_registry[name]

    def decorator(cls: type[HeaderProcessor]) -> type[HeaderProcessor]:
        """Decorator function that registers the processor class with the given extension.

        Each HeaderProcessor is instantiated and bound to a specific FileType at registration time.
        This instance-level registration ensures that processor.file_type is set correctly,
        even if multiple file types reuse the same processor class.
        See also resolver.py for where this linkage is relied upon.

        Args:
            cls: The class to register as a header processor.

        Raises:
            ValueError: If a `FileType` is already registered to a `HeaderProcessor`.

        Returns:
            The decorated HeaderProcessor class.
        """
        logger.debug("Registering processor %s for file type: %s", cls.__name__, file_type.name)
        if file_type.name in _registry:
            existing: HeaderProcessor = _registry[file_type.name]
            # If it's already an instance of this exact class, skip silently
            if isinstance(existing, cls):
                logger.info(
                    "Skipping duplicate registration of %s to %s.",
                    file_type.name,
                    cls.__name__,
                )
                return cls

            # If it's a DIFFERENT class, then we have a genuine conflict
            raise ValueError(
                f"File type '{file_type.name}' already has a registered processor "
                f"({type(existing).__name__}). Cannot overwrite with {cls.__name__}."
            )

        instance: HeaderProcessor = cls()
        instance.file_type = file_type
        _registry[file_type.name] = instance
        return cls

    return decorator


def get_base_header_processor_registry() -> dict[str, HeaderProcessor]:
    """Return the base mapping of file type names to HeaderProcessor instances.

    Notes:
        For the effective, user-facing composed view (including overlays), use
        [`topmark.registry.processors.HeaderProcessorRegistry.as_mapping`][].
    """
    return _registry
