# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/registry/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Registry metadata types."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


def _empty_header_policy() -> dict[str, object]:
    """Return an empty header-policy mapping with a precise type for Pyright."""
    return {}


@dataclass(frozen=True)
class FileTypeMeta:
    """Stable, serializable metadata about a registered FileType."""

    name: str
    description: str = ""
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    skip_processing: bool = False
    content_matcher: bool = False
    header_policy: dict[str, object] = field(default_factory=_empty_header_policy)


@dataclass(frozen=True)
class ProcessorMeta:
    """Stable, serializable metadata about a registered processor instance."""

    name: str
    description: str = ""
    line_prefix: str = ""
    line_suffix: str = ""
    block_prefix: str = ""
    block_suffix: str = ""
