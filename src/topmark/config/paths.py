# topmark:header:start
#
#   project      : TopMark
#   file         : paths.py
#   file_relpath : src/topmark/config/paths.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure helpers for path normalization and PatternSource construction.

These utilities centralize the path resolution rules used by config loading and
CLI overrides. They do **no I/O** beyond ``Path.resolve()`` and have no imports
from the rest of TopMark (except logging/types), which makes them safe to use
across modules.

Key behaviors:
    - ``abs_path_from(base, raw)``: resolve ``raw`` against ``base`` when
      relative; always returns an absolute, resolved :class:`pathlib.Path`.
    - ``ps_from_config(raw, config_dir)``: create a :class:`PatternSource` for a
      path declared *inside a config file*, anchoring to that file's directory.
    - ``ps_from_cli(raw, cwd)``: same, but for CLI-declared paths, anchoring to
      the invocation CWD.
    - ``extend_ps(dst, items, mk, kind, base)``: batch-normalize a sequence of
      raw entries into ``dst`` using the provided factory.

Policy recap:
    * Globs are evaluated later, relative to ``relative_to``.
    * Files that *contain* patterns (``*_from``) are normalized immediately, and
      each carries a ``base`` (usually ``path.parent``) for consistent matching.
"""

from __future__ import annotations

from pathlib import Path

# For runtime type checks, prefer collections.abc
from typing import TYPE_CHECKING, Callable

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.config.types import PatternSource

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike

logger: TopmarkLogger = get_logger(__name__)


# Internal helpers for normalization
def abs_path_from(base: Path, raw: str | PathLike[str]) -> Path:
    """Return an absolute Path for *raw* using *base* if *raw* is relative."""
    s = str(raw)
    p = Path(s)
    return (base / p).resolve() if not p.is_absolute() else p.resolve()


def ps_from_config(raw: str, config_dir: Path) -> PatternSource:
    """Create PatternSource from a config-file-declared path using that file's directory."""
    p: Path = abs_path_from(config_dir, raw)
    return PatternSource(path=p, base=p.parent)


def ps_from_cli(raw: str, cwd: Path) -> PatternSource:
    """Create PatternSource from a CLI-declared path using CWD (invocation site)."""
    p: Path = abs_path_from(cwd, raw)
    return PatternSource(path=p, base=p.parent)


def extend_ps(
    dst: list[PatternSource],
    items: Iterable[str],
    mk: Callable[[str, Path], PatternSource],
    kind: str,
    base: Path,
) -> None:
    """Append pattern sources created from ``items`` to ``dst``.

    Args:
        dst (list[PatternSource]): Destination list to extend in-place.
        items (Iterable[str]): Raw pattern declarations to normalize; skipped if falsy.
        mk (Callable[[str, Path], PatternSource]): Factory that materializes a
            ``PatternSource`` given the raw entry and resolution base.
        kind (str): Human-readable label used for debug logging.
        base (Path): Directory against which relative entries are resolved.
    """
    for raw in items or []:
        ps: PatternSource = mk(raw, base)
        dst.append(ps)
        logger.debug(
            "Normalized %s '%s' against %s -> %s (base=%s)", kind, raw, base, ps.path, ps.base
        )
