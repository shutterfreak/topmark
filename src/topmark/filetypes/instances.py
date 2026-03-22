# topmark:header:start
#
#   project      : TopMark
#   file         : instances.py
#   file_relpath : src/topmark/filetypes/instances.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Built-in and plugin-provided file type declarations for the base registry.

This module aggregates [`FileType`][topmark.filetypes.model.FileType]
definitions from TopMark's built-in file type modules and from the
``topmark.filetypes`` entry point group. The resulting base registry is built
lazily on first access and cached for reuse.

Notes:
    * Built-in file type modules are imported lazily.
    * Plugin file types are discovered through the [`topmark.filetypes`][topmark.filetypes]
      entry point group.
    * The returned base registry is a plain ``dict`` and should be treated as
      immutable by callers.
    * This module exposes the **base** registry only (built-ins + entry
      points). For the effective composed view used by the public registry
      facade, use
      [`topmark.registry.filetypes.FileTypeRegistry.as_mapping`][topmark.registry.filetypes.FileTypeRegistry.as_mapping].
    * Overlay mutations belong in [`topmark.registry`][topmark.registry], not
      in this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from importlib import import_module
from importlib.metadata import EntryPoints
from importlib.metadata import entry_points
from typing import TYPE_CHECKING
from typing import Any
from typing import Final
from typing import cast

from topmark.core.logging import get_logger
from topmark.filetypes.model import FileType

if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Sequence
    from types import ModuleType

    from topmark.core.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)

_BUILTIN_MODULES: Final[tuple[str, ...]] = (
    "topmark.filetypes.builtins.core_langs",
    "topmark.filetypes.builtins.scripting",
    "topmark.filetypes.builtins.data",
    "topmark.filetypes.builtins.web",
    "topmark.filetypes.builtins.ops",
    "topmark.filetypes.builtins.docs",
)

_ENTRYPOINT_GROUP: Final = "topmark.filetypes"


def _iter_builtin_filetypes() -> Iterable[FileType]:
    """Yield built-in `FileType` objects from the configured built-in modules.

    Yields:
        Built-in `FileType` instances discovered from the modules listed in
        `_BUILTIN_MODULES`.
    """
    for modname in _BUILTIN_MODULES:
        try:
            mod: ModuleType = import_module(modname)
            filetypes: Any = getattr(mod, "FILETYPES", None)
            if not isinstance(filetypes, list):
                logger.warning("Module %s has no FILETYPES list; skipping", modname)
                continue
            # Iterate as generic objects to keep types precise for Pyright
            for obj in cast("Sequence[object]", filetypes):
                if isinstance(obj, FileType):
                    yield obj
                else:
                    logger.warning("Non-FileType entry in %s.FILETYPES: %r", modname, obj)
        except Exception:
            logger.exception("Failed to import built-in filetypes from %s", modname)


def _iter_plugin_filetypes() -> Generator[FileType, None, None]:
    """Yield `FileType` objects provided by plugin entry points.

    Yields:
        Plugin-provided `FileType` instances loaded from the
        ``topmark.filetypes`` entry point group.
    """
    try:
        eps = entry_points()
    except Exception:
        logger.exception("Failed to read entry points")
        return

    # Python 3.10+ API: EntryPoints.select is available and typed
    candidates: EntryPoints = eps.select(group=_ENTRYPOINT_GROUP)

    for ep in candidates:
        try:
            provider: Any = ep.load()
            provided: Any = provider() if callable(provider) else provider
            if not isinstance(provided, Iterable):
                logger.warning(
                    "Entry point %s did not return an iterable of FileType objects: %r",
                    getattr(ep, "name", ep),
                    provided,
                )
                continue
            for obj in cast("Iterable[object]", provided):
                if isinstance(obj, FileType):
                    yield obj
                else:
                    logger.warning(
                        "Entry point %s provided non-FileType: %r",
                        getattr(ep, "name", ep),
                        obj,
                    )
        except Exception:
            logger.exception(
                "Failed loading filetypes from entry point %s", getattr(ep, "name", ep)
            )


# TODO: make namespace-aware + define override behavior (last wins?)
def _dedupe_by_local_key(items: Iterable[FileType]) -> list[FileType]:
    """Deduplicate file types by local key while preserving first occurrence.

    Args:
        items: File type instances in declaration order.

    Returns:
        List of file types with duplicate ``local_key`` values removed, keeping
        the first occurrence.
    """
    seen: set[str] = set()
    acc: list[FileType] = []
    for ft in items:
        if ft.local_key in seen:
            logger.warning(
                "Duplicate FileType local_key detected: %s (keeping first)", ft.local_key
            )
            continue
        seen.add(ft.local_key)
        acc.append(ft)
    return acc


def _aggregate_all_filetypes() -> list[FileType]:
    """Collect all built-in and plugin file types into one ordered sequence.

    Returns:
        Deduplicated list containing built-in file types followed by plugin
        file types.
    """
    ordered: list[FileType] = list(_iter_builtin_filetypes())
    ordered.extend(list(_iter_plugin_filetypes()))
    return _dedupe_by_local_key(ordered)


def _generate_registry(filetypes: Iterable[FileType]) -> dict[str, FileType]:
    """Generate a file type registry keyed by local key.

    Args:
        filetypes: File type definitions to index.

    Returns:
        Mapping of ``FileType.local_key`` to `FileType`.

    Raises:
        ValueError: If duplicate file type local keys are encountered.
    """
    registry: dict[str, FileType] = {}
    for ft in filetypes:
        if ft.local_key in registry:
            raise ValueError(f"Duplicate FileType local_key: {ft.local_key}")
        registry[ft.local_key] = ft
    return registry


@lru_cache(maxsize=1)
def get_base_file_type_registry() -> dict[str, FileType]:
    """Return and cache the base file type registry.

    The base registry contains built-in and plugin-provided file types keyed by
    ``FileType.local_key``.

    Returns:
        Cached mapping of file type local key to `FileType`.

    Notes:
        For the effective composed registry (including overlay mutations used by
        tests and advanced callers), use
        [`topmark.registry.filetypes.FileTypeRegistry.as_mapping`][topmark.registry.filetypes.FileTypeRegistry.as_mapping].
    """
    all_types: list[FileType] = _aggregate_all_filetypes()
    registry: dict[str, FileType] = _generate_registry(all_types)
    logger.debug("Loaded %d file types", len(registry))
    return registry
