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

from topmark.registry.identity import make_qualified_key


def _empty_header_policy() -> dict[str, object]:
    """Return an empty header-policy mapping with a precise type for Pyright."""
    return {}


@dataclass(frozen=True)
class FileTypeMeta:
    """Stable, serializable metadata about a registered FileType."""

    namespace: str
    local_key: str

    @property
    def qualified_key(self) -> str:
        """Return the qualified identity key for this file type instance.

        Format: ``"<namespace>:<local_key>"``.
        """
        return make_qualified_key(self.namespace, self.local_key)

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

    namespace: str
    local_key: str

    @property
    def qualified_key(self) -> str:
        """Return the qualified identity key for this file type instance.

        Format: ``"<namespace>:<local_key>"``.
        """
        return make_qualified_key(self.namespace, self.local_key)

    description: str = ""

    block_prefix: str = ""
    block_suffix: str = ""

    line_indent: str = ""
    line_prefix: str = ""
    line_suffix: str = ""
