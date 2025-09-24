# topmark:header:start
#
#   project      : TopMark
#   file         : instances.py
#   file_relpath : src/topmark/filetypes/instances.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File type instances and registry for TopMark.

This module defines concrete singleton instances of FileType used throughout
TopMark for file recognition and header processing. It also builds a registry
mapping file type names to their definitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger

from .builtins.core_langs import FILETYPES as CORE_LANGS
from .builtins.data import FILETYPES as DATA
from .builtins.docs import FILETYPES as DOCS
from .builtins.ops import FILETYPES as OPS
from .builtins.scripting import FILETYPES as SCRIPTING
from .builtins.web import FILETYPES as WEB

if TYPE_CHECKING:
    from .base import FileType

logger: TopmarkLogger = get_logger(__name__)

# Note: some FileTypes may set skip_processing=True to recognize-but-skip
# (e.g., JSON, LICENSE, py.typed).


# Heuristic content matchers


# Alphabetical list of all supported file types (singleton instances).
file_types: list[FileType] = [
    *CORE_LANGS,
    *SCRIPTING,
    *DATA,
    *WEB,
    *OPS,
    *DOCS,
]


def _generate_registry() -> dict[str, FileType]:
    """Generate a registry mapping file type names to their definitions.

    This function checks for duplicate or missing file type names
    and builds a dictionary keyed by `FileType.name`.

    Returns:
        dict[str, FileType]: A dictionary of file type name → FileType instance.

    Raises:
        ValueError: If any FileType has a missing or duplicate name.
    """
    registry: dict[str, FileType] = {}
    errors = 0
    for t in file_types:
        if not t.name:
            logger.error("FileType has empty name: %r", t)
            errors += 1
            continue
        if t.name in registry:
            logger.error("Duplicate FileType name: '%s'", t.name)
            errors += 1
            continue
        registry[t.name] = t
    if errors > 0:
        raise ValueError("The File Type registry contains invalid entries. Please fix them.")
    return registry


#: Registry of all file types, keyed by name.
_file_type_registry: dict[str, FileType] = _generate_registry()


def get_file_type_registry() -> dict[str, FileType]:
    """Return the file type registry.

    Returns:
        dict[str, FileType]: The file type registry as dict of file type names
            and FileType instances.
    """
    return _file_type_registry
