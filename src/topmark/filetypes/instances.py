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

Builds the runtime registry of [`topmark.filetypes.base.FileType`][] objects
from built-in groups and optionally from plugin entry points. The registry is
constructed lazily on first access and cached thereafter.

Notes:
    * Built-ins are imported lazily from topical modules.
    * Plugins are discovered via the ``topmark.filetypes`` entry point group.
    * The returned mapping is a plain ``dict`` but should be treated as
      immutable by callers. Overlay mutations must go through
      ``topmark.registry``.
"""

from __future__ import annotations

from collections.abc import Iterable as IterABC
from functools import lru_cache
from importlib import import_module
from importlib.metadata import EntryPoints, entry_points
from typing import TYPE_CHECKING, Any, Final, Iterable, Sequence, cast

from topmark.config.logging import TopmarkLogger, get_logger

from .base import FileType

if TYPE_CHECKING:
    from types import ModuleType

logger: TopmarkLogger = get_logger(__name__)

_BUILTIN_MODULES: Final[tuple[str, ...]] = (
    "topmark.filetypes.builtins.core_langs",
    "topmark.filetypes.builtins.scripting",
    "topmark.filetypes.builtins.data",
    "topmark.filetypes.builtins.web",
    "topmark.filetypes.builtins.ops",
    "topmark.filetypes.builtins.docs",
)

ENTRYPOINT_GROUP: Final[str] = "topmark.filetypes"


def _iter_builtin_filetypes() -> Iterable[FileType]:
    """Yield built-in FileType objects from topical modules (lazy import)."""
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


def _iter_plugin_filetypes() -> Iterable[FileType]:
    """Yield FileType objects provided by external plugins (entry points)."""
    try:
        eps = entry_points()
    except Exception:
        logger.exception("Failed to read entry points")
        return

    # Python 3.10+ API: EntryPoints.select is available and typed
    candidates: EntryPoints = eps.select(group=ENTRYPOINT_GROUP)

    for ep in candidates:
        try:
            provider: Any = ep.load()
            provided: Any = provider() if callable(provider) else provider
            if not isinstance(provided, IterABC):
                logger.warning(
                    "Entry point %s did not return an iterable of FileType objects: %r",
                    getattr(ep, "name", ep),
                    provided,
                )
                continue
            for obj in cast("IterABC[object]", provided):
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


def _dedupe_by_name(items: Iterable[FileType]) -> list[FileType]:
    """Deduplicate by FileType.name, preserving first occurrence order."""
    seen: set[str] = set()
    acc: list[FileType] = []
    for ft in items:
        if ft.name in seen:
            logger.warning("Duplicate FileType name detected: %s (keeping first)", ft.name)
            continue
        seen.add(ft.name)
        acc.append(ft)
    return acc


def _aggregate_all_filetypes() -> list[FileType]:
    """Aggregate built-ins plus any plugin-provided file types (deduped)."""
    ordered: list[FileType] = list(_iter_builtin_filetypes())
    ordered.extend(list(_iter_plugin_filetypes()))
    return _dedupe_by_name(ordered)


def _generate_registry(filetypes: Iterable[FileType]) -> dict[str, FileType]:
    """Generate a registry mapping file type names to their definitions."""
    registry: dict[str, FileType] = {}
    for ft in filetypes:
        if ft.name in registry:
            raise ValueError(f"Duplicate FileType name: {ft.name}")
        registry[ft.name] = ft
    return registry


@lru_cache(maxsize=1)
def get_file_type_registry() -> dict[str, FileType]:
    """Return (and cache) the FileType registry (lazy; import-time light)."""
    all_types: list[FileType] = _aggregate_all_filetypes()
    registry: dict[str, FileType] = _generate_registry(all_types)
    logger.debug("Loaded %d file types", len(registry))
    return registry
